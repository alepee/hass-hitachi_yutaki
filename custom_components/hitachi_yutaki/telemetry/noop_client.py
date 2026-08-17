"""No-op telemetry client — used when telemetry is disabled (Off level)."""

from __future__ import annotations

from .models import InstallationInfo, MetricsBatch, RegisterSnapshot, SendResult


class NoopTelemetryClient:
    """Telemetry client that does nothing.

    Same interface as HttpTelemetryClient but all methods return
    immediately. Zero overhead when telemetry is Off.
    """

    async def send_installation(self, info: InstallationInfo) -> SendResult:
        """No-op: accept and discard installation info."""
        return SendResult.SUCCESS

    async def send_metrics(self, batch: MetricsBatch) -> SendResult:
        """No-op: accept and discard metrics batch."""
        return SendResult.SUCCESS

    async def send_snapshot(self, snapshot: RegisterSnapshot) -> SendResult:
        """No-op: accept and discard register snapshot."""
        return SendResult.SUCCESS
