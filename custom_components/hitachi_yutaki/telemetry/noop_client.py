"""No-op telemetry client — used when telemetry is disabled (Off level)."""

from __future__ import annotations

from .models import DailyStats, InstallationInfo, MetricsBatch, RegisterSnapshot


class NoopTelemetryClient:
    """Telemetry client that does nothing.

    Same interface as HttpTelemetryClient but all methods return
    immediately. Zero overhead when telemetry is Off.
    """

    async def send_installation(self, info: InstallationInfo) -> bool:
        """No-op: accept and discard installation info."""
        return True

    async def send_metrics(self, batch: MetricsBatch) -> bool:
        """No-op: accept and discard metrics batch."""
        return True

    async def send_daily_stats(self, stats: DailyStats) -> bool:
        """No-op: accept and discard daily stats."""
        return True

    async def send_snapshot(self, snapshot: RegisterSnapshot) -> bool:
        """No-op: accept and discard register snapshot."""
        return True
