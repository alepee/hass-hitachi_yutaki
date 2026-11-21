"""Replay the telemetry archive through the integration's own CyclingMonitor.

Validates the per-cycle heat balance of #512 with the exact code the
integration runs (no second implementation): every unit's polls are fed to a
``CyclingMonitor``, and each stored day prints its diagnosis next to the
detector's verdict.

Input: per-day CSV extracts of the metrics archive, one row per poll, with the
columns ``hash``, ``device``, ``time``, ``operation_state``,
``is_compressor_running``, ``compressor_frequency``, ``is_defrosting``,
``water_inlet_temp``, ``water_outlet_temp``, ``water_target_temp``,
``water_flow`` and, when available, ``secondary_compressor_frequency``.

Usage (from the repository root, with the dev virtualenv):
    python backend/analysis/replay_cycling_diagnosis.py data/days_cycling/*.csv
"""

from __future__ import annotations

from collections import defaultdict
import csv
from datetime import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from custom_components.hitachi_yutaki.adapters.storage.in_memory import (  # noqa: E402
    InMemoryStorage,
)
from custom_components.hitachi_yutaki.domain.models.cycling import (  # noqa: E402
    CyclingInput,
)
from custom_components.hitachi_yutaki.domain.services.cycling import (  # noqa: E402
    HISTORY_DAYS,
    CyclingMonitor,
)

HEAT = "operation_state_heat"
THERMO_OFF = "operation_state_heat_thermo_off"


def _f(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _b(value: str | None) -> bool | None:
    if value in (None, ""):
        return None
    return value in ("true", "True", "1")


def _input(row: dict[str, str]) -> CyclingInput:
    state = row["operation_state"]
    running = _b(row["is_compressor_running"])
    if running is None:
        freq = _f(row["compressor_frequency"])
        running = bool(freq and freq > 0) if freq is not None else None
    sec = _f(row.get("secondary_compressor_frequency"))
    return CyclingInput(
        operation_mode="heating" if state.startswith(HEAT) else None,
        compressor_running=running,
        data_reliable=not _b(row["is_defrosting"]),
        thermo_off=state == THERMO_OFF,
        water_inlet_temp=_f(row["water_inlet_temp"]),
        water_outlet_temp=_f(row["water_outlet_temp"]),
        water_target_temp=_f(row["water_target_temp"]),
        water_flow=_f(row["water_flow"]),
        compressor_frequency=_f(row["compressor_frequency"]),
        secondary_compressor_running=(sec > 0) if sec is not None else None,
    )


def main() -> None:
    """Print one JSON line per unit-day with a stored aggregate."""
    rows: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for path in sys.argv[1:]:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                rows[(row["hash"], row["device"])].append(row)

    for (h, d), unit_rows in sorted(rows.items()):
        unit_rows.sort(key=lambda r: r["time"])
        monitor = CyclingMonitor(InMemoryStorage(max_len=HISTORY_DAYS))
        for row in unit_rows:
            monitor.update(_input(row), timestamp=datetime.fromisoformat(row["time"]))
        monitor._flush_day()  # noqa: SLF001 - close the last replayed day
        for agg in monitor.serialize()["aggregates"]:
            diag = agg["diagnosis"]
            out = {
                "unit": f"{h[:6]}/{d[:4]}",
                "day": agg["day"],
                "cycles": agg["cycles"],
                "faulted": agg["faulted"],
            }
            if diag:
                out |= {
                    k: (round(v, 2) if isinstance(v, float) else v)
                    for k, v in diag.items()
                }
            print(json.dumps(out))
        status = monitor.get_status()
        print(
            json.dumps(
                {
                    "unit": f"{h[:6]}/{d[:4]}",
                    "status": status.status,
                    "diagnosis_days": status.diagnosis_days,
                }
            )
        )


if __name__ == "__main__":
    main()
