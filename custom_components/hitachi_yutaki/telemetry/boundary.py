"""What of a poll may enter a telemetry payload.

Metrics points and the register snapshot are both cut from the enriched poll
data, which also carries values that describe the household rather than the
heat pump. This module is the one place that decides which poll keys never
leave the instance, so the two payloads cannot drift apart and a new private
value is excluded by adding it here, not by patching each sender.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Coordinator bookkeeping about the poll itself, not a measurement.
INTERNAL_KEYS = frozenset({"is_available"})

# The user's own economics, derived from their electricity price entity: the
# current tariff and the accumulated cost. Neither says anything about the
# heat pump that `electrical_energy_consumed` does not, and the telemetry
# documentation promises no such data.
PRIVATE_KEYS = frozenset({"_current_price", "electricity_cost"})

NEVER_SENT = INTERNAL_KEYS | PRIVATE_KEYS


def shareable(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of a poll's data without the keys that are never sent."""
    return {key: value for key, value in data.items() if key not in NEVER_SENT}
