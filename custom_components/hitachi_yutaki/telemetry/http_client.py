"""HTTP telemetry client — sends data to the Cloudflare Worker endpoint."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from typing import Any

import aiohttp

from .models import DailyStats, InstallationInfo, MetricsBatch, RegisterSnapshot

_LOGGER = logging.getLogger(__name__)

# Default endpoint (Cloudflare Worker)
DEFAULT_ENDPOINT = "https://hitachi-telemetry.antoine-04c.workers.dev/v1/ingest"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = (5, 15, 45)  # seconds between retries
REQUEST_TIMEOUT = 10  # seconds


class HttpTelemetryClient:
    """Sends telemetry data as gzipped JSON to the ingestion endpoint.

    Retries with exponential backoff on transient failures.
    Never raises — logs warnings and returns False on error.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        instance_hash: str,
        endpoint: str = DEFAULT_ENDPOINT,
    ) -> None:
        """Initialize the HTTP telemetry client."""
        self._session = session
        self._instance_hash = instance_hash
        self._endpoint = endpoint

    async def send_installation(self, info: InstallationInfo) -> bool:
        """Send installation info payload."""
        return await self._send(info.to_dict())

    async def send_metrics(self, batch: MetricsBatch) -> bool:
        """Send a metrics batch payload."""
        return await self._send(batch.to_dict())

    async def send_daily_stats(self, stats: DailyStats) -> bool:
        """Send daily stats payload."""
        return await self._send(stats.to_dict())

    async def send_snapshot(self, snapshot: RegisterSnapshot) -> bool:
        """Send a register snapshot payload."""
        return await self._send(snapshot.to_dict())

    async def _send(self, payload: dict[str, Any]) -> bool:
        """Send a JSON payload with gzip compression and retry logic.

        Returns True on 2xx, False on any error.
        """
        body = gzip.compress(json.dumps(payload).encode())
        headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "X-Instance-Hash": self._instance_hash,
        }
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.post(
                    self._endpoint,
                    data=body,
                    headers=headers,
                    timeout=timeout,
                ) as resp:
                    if 200 <= resp.status < 300:
                        return True

                    # Client errors (4xx) are not retryable
                    if 400 <= resp.status < 500:
                        _LOGGER.warning(
                            "Telemetry rejected (HTTP %s): %s",
                            resp.status,
                            await resp.text(),
                        )
                        return False

                    # Server errors (5xx) — retry
                    _LOGGER.debug(
                        "Telemetry server error (HTTP %s), attempt %d/%d",
                        resp.status,
                        attempt + 1,
                        MAX_RETRIES,
                    )

            except TimeoutError:
                _LOGGER.debug(
                    "Telemetry request timed out, attempt %d/%d",
                    attempt + 1,
                    MAX_RETRIES,
                )
            except aiohttp.ClientError as err:
                _LOGGER.debug(
                    "Telemetry request failed (%s), attempt %d/%d",
                    err,
                    attempt + 1,
                    MAX_RETRIES,
                )

            # Wait before retry (except after last attempt)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])

        _LOGGER.warning("Telemetry send failed after %d attempts", MAX_RETRIES)
        return False
