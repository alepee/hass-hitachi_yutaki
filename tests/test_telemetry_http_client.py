"""Tests for telemetry HTTP client."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import gzip
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.hitachi_yutaki.telemetry.http_client import (
    MAX_RETRIES,
    HttpTelemetryClient,
)
from custom_components.hitachi_yutaki.telemetry.models import (
    InstallationInfo,
    MetricsBatch,
    RegisterSnapshot,
    SendResult,
)


def _make_client(
    session: aiohttp.ClientSession | None = None,
    instance_hash: str = "abc123",
    endpoint: str = "https://test.example.com/v1/ingest",
    label: str = "",
) -> HttpTelemetryClient:
    """Create a client with optional mock session."""
    return HttpTelemetryClient(
        session=session or MagicMock(spec=aiohttp.ClientSession),
        instance_hash=instance_hash,
        endpoint=endpoint,
        label=label,
    )


def _mock_response(status: int = 202, text: str = "Accepted") -> AsyncMock:
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    return resp


def _mock_session(response: AsyncMock) -> MagicMock:
    """Create a mock session whose post() returns the given response."""
    session = MagicMock(spec=aiohttp.ClientSession)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(return_value=ctx)
    return session


def _make_installation() -> InstallationInfo:
    """Create a sample InstallationInfo."""
    return InstallationInfo(
        instance_hash="abc123",
        device_hash="b" * 64,
        profile="yutaki_s80",
        gateway_type="modbus_atw_mbs_02",
        ha_version="2025.3.1",
        integration_version="2.0.1",
        power_supply="single",
        has_dhw=True,
        has_pool=False,
        has_cooling=True,
        max_circuits=2,
        has_secondary_compressor=True,
    )


class TestHttpClientSuccess:
    """Tests for successful sends."""

    @pytest.mark.asyncio
    async def test_send_installation_success(self):
        """Verify installation info is sent successfully on 202."""
        resp = _mock_response(202)
        session = _mock_session(resp)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.SUCCESS
        session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_metrics_success(self):
        """Verify metrics batch is sent successfully."""
        resp = _mock_response(202)
        session = _mock_session(resp)
        client = _make_client(session=session)

        batch = MetricsBatch(
            instance_hash="abc123",
            device_hash="b" * 64,
            points=[{"time": datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC)}],
        )
        result = await client.send_metrics(batch)
        assert result is SendResult.SUCCESS

    @pytest.mark.asyncio
    async def test_send_snapshot_success(self):
        """Verify register snapshot is sent successfully."""
        resp = _mock_response(202)
        session = _mock_session(resp)
        client = _make_client(session=session)

        snapshot = RegisterSnapshot(
            instance_hash="abc123",
            device_hash="b" * 64,
            time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
            profile="yutaki_s80",
            gateway_type="modbus_atw_mbs_02",
            registers={"outdoor_temp": 55},
        )
        result = await client.send_snapshot(snapshot)
        assert result is SendResult.SUCCESS

    @pytest.mark.asyncio
    async def test_200_is_success(self):
        """Verify any 2xx status is treated as success."""
        resp = _mock_response(200)
        session = _mock_session(resp)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())
        assert result is SendResult.SUCCESS


class TestHttpClientPayload:
    """Tests for payload format."""

    @pytest.mark.asyncio
    async def test_payload_is_gzipped_json(self):
        """Verify the POST body is valid gzip-compressed JSON."""
        resp = _mock_response(202)
        session = _mock_session(resp)
        client = _make_client(session=session)

        await client.send_installation(_make_installation())

        call_kwargs = session.post.call_args
        body = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        # Decompress and parse
        decompressed = gzip.decompress(body)
        payload = json.loads(decompressed)
        assert payload["type"] == "installation"
        assert payload["instance_hash"] == "abc123"

    @pytest.mark.asyncio
    async def test_headers_set_correctly(self):
        """Verify Content-Type, Content-Encoding and X-Instance-Hash headers."""
        resp = _mock_response(202)
        session = _mock_session(resp)
        client = _make_client(session=session, instance_hash="hash42")

        await client.send_installation(_make_installation())

        call_kwargs = session.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Content-Type"] == "application/json"
        assert headers["Content-Encoding"] == "gzip"
        assert headers["X-Instance-Hash"] == "hash42"

    @pytest.mark.asyncio
    async def test_posts_to_configured_endpoint(self):
        """Verify the request is sent to the configured endpoint URL."""
        resp = _mock_response(202)
        session = _mock_session(resp)
        client = _make_client(
            session=session, endpoint="https://custom.endpoint/v1/ingest"
        )

        await client.send_installation(_make_installation())

        call_args = session.post.call_args
        url = call_args.args[0] if call_args.args else call_args[0][0]
        assert url == "https://custom.endpoint/v1/ingest"


class TestHttpClientErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_4xx_returns_false_no_retry(self):
        """Verify 4xx client errors return False without retrying."""
        resp = _mock_response(400, "Bad Request")
        session = _mock_session(resp)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.FAILED
        # Should NOT retry on 4xx — called only once
        assert session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_413_is_reported_as_payload_too_large(self):
        """A 413 is a verdict on the batch, not a transient failure (#395).

        The caller needs the distinction to drop the points instead of
        re-queueing them into an ever-larger, permanently rejected batch.
        """
        resp = _mock_response(413, "payload too large")
        session = _mock_session(resp)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.PAYLOAD_TOO_LARGE
        assert not result
        assert session.post.call_count == 1

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_5xx_retries_then_fails(self):
        """Verify 5xx server errors trigger retries up to MAX_RETRIES."""
        resp = _mock_response(500, "Internal Server Error")
        session = _mock_session(resp)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.FAILED
        assert session.post.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_timeout_retries_then_fails(self):
        """Verify timeouts trigger retries up to MAX_RETRIES."""
        session = MagicMock(spec=aiohttp.ClientSession)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError)
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.FAILED
        assert session.post.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_connection_error_retries_then_fails(self):
        """Verify connection errors trigger retries up to MAX_RETRIES."""
        session = MagicMock(spec=aiohttp.ClientSession)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientError("Connection refused")
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.FAILED
        assert session.post.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_5xx_then_success_on_retry(self):
        """Verify a successful retry after an initial 5xx error."""
        resp_fail = _mock_response(500)
        resp_ok = _mock_response(202)

        session = MagicMock(spec=aiohttp.ClientSession)
        ctx_fail = AsyncMock()
        ctx_fail.__aenter__ = AsyncMock(return_value=resp_fail)
        ctx_fail.__aexit__ = AsyncMock(return_value=False)
        ctx_ok = AsyncMock()
        ctx_ok.__aenter__ = AsyncMock(return_value=resp_ok)
        ctx_ok.__aexit__ = AsyncMock(return_value=False)

        session.post = MagicMock(side_effect=[ctx_fail, ctx_ok])
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.SUCCESS
        assert session.post.call_count == 2


class TestDiagnosability:
    """Failures must name their cause and their config entry (#395)."""

    async def test_429_is_logged_at_warning(self, caplog):
        """A 429 must be visible: it was DEBUG, which made #395 undiagnosable."""
        client = _make_client(
            _mock_session(_mock_response(429, "Rate limit exceeded")), label="PAC 1"
        )
        with caplog.at_level(logging.DEBUG):
            assert (
                await client.send_installation(_make_installation())
                is SendResult.FAILED
            )
        rejections = [r for r in caplog.records if "Telemetry rejected" in r.message]
        assert len(rejections) == 1
        assert rejections[0].levelno == logging.WARNING
        assert "429" in caplog.text

    async def test_log_line_carries_the_entry_label(self, caplog):
        """Multi-gateway installs must be able to tell their entries apart."""
        client = _make_client(
            _mock_session(_mock_response(429, "Rate limit exceeded")), label="ECS 2"
        )
        with caplog.at_level(logging.WARNING):
            await client.send_installation(_make_installation())
        assert "[ECS 2]" in caplog.text

    async def test_label_is_optional(self, caplog):
        """Without a label the message has no stray prefix."""
        client = _make_client(_mock_session(_mock_response(400, "Bad payload")))
        with caplog.at_level(logging.WARNING):
            await client.send_installation(_make_installation())
        assert "[]" not in caplog.text
        assert "Telemetry rejected (HTTP 400)" in caplog.text


class TestSelfInflictedRateLimit:
    """A 429 we provoked ourselves is not a delivery failure (#395).

    The endpoint commits its rate-limit slot only once the payload is durably
    archived, and the window is shorter than the flush cycle. So a 429 that
    follows an attempt of ours whose response never arrived proves that same
    attempt landed. Reporting FAILED there makes the caller re-queue points
    the archive already holds, and they get written a second time.
    """

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_timeout_then_429_reports_probably_delivered(self):
        """The classic race: the 202 is lost, the retry hits our own window."""
        session = MagicMock(spec=aiohttp.ClientSession)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=[TimeoutError(), _mock_response(429, "Rate limit exceeded")]
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.PROBABLY_DELIVERED
        assert session.post.call_count == 2

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_connection_error_then_429_reports_probably_delivered(self):
        """A dropped connection leaves the same doubt as a timeout."""
        session = MagicMock(spec=aiohttp.ClientSession)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=[
                aiohttp.ClientError("connection reset"),
                _mock_response(429, "Rate limit exceeded"),
            ]
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.PROBABLY_DELIVERED

    @pytest.mark.asyncio
    async def test_a_first_attempt_429_still_fails(self):
        """Without an unanswered attempt of ours, a 429 means what it says."""
        client = _make_client(_mock_session(_mock_response(429, "Rate limited")))

        result = await client.send_installation(_make_installation())

        assert result is SendResult.FAILED

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_server_error_then_429_still_fails(self):
        """A 502 is an observed rejection: nothing was archived, so retry."""
        session = MagicMock(spec=aiohttp.ClientSession)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=[
                _mock_response(502, "R2 archive unavailable"),
                _mock_response(429, "Rate limit exceeded"),
            ]
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.FAILED

    @pytest.mark.asyncio
    @patch(
        "custom_components.hitachi_yutaki.telemetry.http_client.RETRY_DELAYS", (0, 0, 0)
    )
    async def test_timeout_then_413_is_still_payload_too_large(self):
        """The size verdict outranks the doubt about the earlier attempt."""
        session = MagicMock(spec=aiohttp.ClientSession)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=[TimeoutError(), _mock_response(413, "payload too large")]
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session=session)

        result = await client.send_installation(_make_installation())

        assert result is SendResult.PAYLOAD_TOO_LARGE

    def test_probably_delivered_is_falsy(self):
        """Strong evidence is not a confirmed 2xx."""
        assert not SendResult.PROBABLY_DELIVERED
