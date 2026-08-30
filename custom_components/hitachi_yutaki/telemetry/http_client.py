"""HTTP telemetry client — sends data to the Cloudflare Worker endpoint."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from typing import Any

import aiohttp

from ..const import TELEMETRY_ENDPOINT
from .models import InstallationInfo, MetricsBatch, RegisterSnapshot, SendResult

_LOGGER = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = (5, 15, 45)  # seconds between retries
REQUEST_TIMEOUT = 10  # seconds

# HTTP status meaning "the decompressed body exceeds the endpoint's limit".
# The batch itself is the problem, so the caller must drop it rather than
# retry it (#395).
_HTTP_PAYLOAD_TOO_LARGE = 413

# HTTP status meaning "one payload of this type was already accepted for this
# unit inside the endpoint's rate-limit window".
_HTTP_RATE_LIMITED = 429


class HttpTelemetryClient:
    """Sends telemetry data as gzipped JSON to the ingestion endpoint.

    Retries with exponential backoff on transient failures.
    Never raises: logs warnings and returns a non-success SendResult on error.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        instance_hash: str,
        endpoint: str = TELEMETRY_ENDPOINT,
        label: str = "",
    ) -> None:
        """Initialize the HTTP telemetry client.

        `label` is the config entry title. It prefixes every log line so a
        multi-gateway installation can tell which entry failed (#395).
        """
        self._session = session
        self._instance_hash = instance_hash
        self._endpoint = endpoint
        self._prefix = f"[{label}] " if label else ""

    async def send_installation(self, info: InstallationInfo) -> SendResult:
        """Send installation info payload."""
        return await self._send(info.to_dict())

    async def send_metrics(self, batch: MetricsBatch) -> SendResult:
        """Send a metrics batch payload."""
        return await self._send(batch.to_dict())

    async def send_snapshot(self, snapshot: RegisterSnapshot) -> SendResult:
        """Send a register snapshot payload."""
        return await self._send(snapshot.to_dict())

    async def _send(self, payload: dict[str, Any]) -> SendResult:
        """Send a JSON payload with gzip compression and retry logic.

        Returns SUCCESS on 2xx, PAYLOAD_TOO_LARGE on 413, PROBABLY_DELIVERED
        on a 429 that this call's own earlier attempt provoked, and FAILED
        otherwise.
        """
        body = gzip.compress(json.dumps(payload).encode())
        headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "X-Instance-Hash": self._instance_hash,
        }
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        # True once an attempt was sent but its outcome was never seen, i.e. a
        # timeout or a dropped connection. Such an attempt may well have been
        # stored by the endpoint.
        sent_unobserved = False

        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.post(
                    self._endpoint,
                    data=body,
                    headers=headers,
                    timeout=timeout,
                ) as resp:
                    if 200 <= resp.status < 300:
                        return SendResult.SUCCESS

                    # The endpoint commits its rate-limit slot only after the
                    # payload is durably archived, and the window is shorter
                    # than the flush cycle. So a 429 following an attempt of
                    # ours whose response never arrived says that same attempt
                    # landed. Re-queueing here would archive the points twice
                    # (#395); report the near-certainty instead.
                    if resp.status == _HTTP_RATE_LIMITED and sent_unobserved:
                        _LOGGER.info(
                            "%sTelemetry retry hit the rate limit our own "
                            "unanswered attempt armed, treating the batch as "
                            "delivered",
                            self._prefix,
                        )
                        return SendResult.PROBABLY_DELIVERED

                    # Client errors (4xx) are not retryable. All are logged at
                    # WARNING, including 429: with per-unit identities a rate
                    # limit means something is genuinely wrong, and hiding it
                    # at DEBUG is what made #395 undiagnosable for the reporter.
                    if 400 <= resp.status < 500:
                        _LOGGER.warning(
                            "%sTelemetry rejected (HTTP %s): %s",
                            self._prefix,
                            resp.status,
                            await resp.text(),
                        )
                        if resp.status == _HTTP_PAYLOAD_TOO_LARGE:
                            return SendResult.PAYLOAD_TOO_LARGE
                        return SendResult.FAILED

                    # Server errors (5xx) — retry
                    _LOGGER.debug(
                        "%sTelemetry server error (HTTP %s), attempt %d/%d",
                        self._prefix,
                        resp.status,
                        attempt + 1,
                        MAX_RETRIES,
                    )

            except TimeoutError:
                sent_unobserved = True
                _LOGGER.debug(
                    "%sTelemetry request timed out, attempt %d/%d",
                    self._prefix,
                    attempt + 1,
                    MAX_RETRIES,
                )
            except aiohttp.ClientError as err:
                sent_unobserved = True
                _LOGGER.debug(
                    "%sTelemetry request failed (%s), attempt %d/%d",
                    self._prefix,
                    err,
                    attempt + 1,
                    MAX_RETRIES,
                )

            # Wait before retry (except after last attempt)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])

        _LOGGER.warning(
            "%sTelemetry send failed after %d attempts", self._prefix, MAX_RETRIES
        )
        return SendResult.FAILED
