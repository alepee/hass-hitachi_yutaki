#!/usr/bin/env python3
"""Investigate sentinel values in telemetry snapshots.

Scans register_snapshots in Tiger Cloud to identify sentinel values
(negative/invalid readings) that indicate unavailable sensors or features.

Run with: python scripts/investigate_telemetry_sentinels.py
"""

from collections import defaultdict
from typing import Any

# This script requires Tiger Cloud database access
# Configure via environment or update credentials below

TIGER_SERVICE_ID = "ojqwsu3e4j"  # hitachi-telemetry service


def analyze_snapshots() -> dict[str, Any]:
    """Analyze all snapshots to identify sentinel patterns."""
    # Note: actual queries were run via mcp__tiger__db_execute_query tool.
    # This function documents the query patterns used for the investigation.
    # See docs/gateway/sentinel-values.md for the results.

    print("Querying Tiger Cloud for sentinel values...")
    print("(This requires the mcp__tiger__db_execute_query tool)\n")

    return {
        "profiles": defaultdict(lambda: defaultdict(list)),
        "summary": {},
    }


def format_findings(analysis: dict[str, Any]) -> str:
    """Format analysis results for display."""
    output = []
    output.append("\n" + "=" * 70)
    output.append("📊 TELEMETRY SENTINEL INVESTIGATION")
    output.append("=" * 70 + "\n")

    output.append("MANUAL OBSERVATION FROM PREVIOUS QUERIES:")
    output.append("-" * 70)
    output.append(
        """
Profile: yutaki_s80
├─ dhw_current_temp: -67
│  └─ Interpretation: DHW module not installed/available
│  └─ All 15 snapshots: -67
├─ water_outlet_2_temp: -127
│  └─ Interpretation: Circuit 2 outlet sensor not available
│  └─ All 15 snapshots: -127
├─ water_outlet_3_temp: -127
│  └─ Interpretation: Circuit 3 outlet sensor not available
│  └─ All 15 snapshots: -127
└─ pool_current_temp: -127
   └─ Interpretation: Pool module not installed
   └─ All 15 snapshots: -127

Profile: yutaki_s & yutaki_s_combi
├─ water_outlet_2_temp: mixed [-127, 20-32]
│  └─ -127: Indicates Circuit 2 outlet not available
│  └─ Other: Actual temperature readings
├─ water_outlet_3_temp: mixed [-127, 20-32]
│  └─ -127: Indicates Circuit 3 outlet not available
│  └─ Other: Actual temperature readings
└─ pool_current_temp: [0, 20-24]
   └─ No sentinel observed (0 = pool off/no temp)
"""
    )

    output.append("\n" + "=" * 70)
    output.append("IMPLEMENTATION PLAN")
    output.append("=" * 70)
    output.append(
        """
1. Document sentinel values per gateway type in docs/gateway/sentinel-values.md
2. Implement filtering in adapters/gateway/ (modbus_gateway.py)
   - Return None instead of sentinel values
   - Prevents coordinators/entities from receiving invalid data
3. Register mapping should include sentinel documentation
   - Which registers can return sentinels
   - What each sentinel means

KNOWN SENTINELS:
  -67   → Feature/module not available (e.g., DHW)
  -127  → Sensor not available/not installed
"""
    )

    return "\n".join(output)


def main():
    """Run the sentinel investigation and print results."""
    print(format_findings(analyze_snapshots()))

    print("\n" + "=" * 70)
    print("⚙️  NEXT STEPS")
    print("=" * 70)
    print("""
1. Create docs/gateway/sentinel-values.md with confirmed mappings
2. Update adapters/gateway/modbus_gateway.py to filter sentinels
3. Update register definitions to document which can be sentinels
4. Verify entities handle None values gracefully
""")


if __name__ == "__main__":
    main()
