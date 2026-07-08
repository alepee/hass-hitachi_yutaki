"""Refrigerant-loss domain service (stub)."""

from __future__ import annotations


class RefrigerantLossService:
    """Stub service that reports refrigerant-loss diagnostic state."""

    def get_state(self) -> str:
        """Return the current diagnostic state (always 'warming up' for now)."""
        return "warming up"
