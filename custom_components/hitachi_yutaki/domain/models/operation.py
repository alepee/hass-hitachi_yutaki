"""Operation mode constants for the domain layer."""

MODE_HEATING: str = "heating"
MODE_COOLING: str = "cooling"
MODE_DHW: str = "dhw"
MODE_POOL: str = "pool"

# Modes that always represent heating operations regardless of ΔT
HEATING_ONLY_MODES: frozenset[str] = frozenset({MODE_DHW, MODE_POOL})
