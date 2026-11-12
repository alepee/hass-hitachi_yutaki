"""The documented value lists shared by every gateway map."""

from __future__ import annotations

from .....const import OTCCalculationMethod
from .enum_codec import EnumCodec, choice
from .prefixed import Prefixed

# 0 / 1 registers: run/stop, enable flags, eco/comfort.
SWITCH = choice(0, 1)
# "LCD Central Mode": 0 local, 1 air, 2 water, 3 full.
CENTRAL_CONTROL_MODE = choice(0, 1, 2, 3)

SYSTEM_STATE = EnumCodec(
    {0: "synchronized", 1: "desynchronized", 2: "initializing"}, unknown="unknown"
)

OPERATION_STATE = EnumCodec(
    {
        raw: f"operation_state_{name}"
        for raw, name in enumerate(
            (
                "off",
                "cool_demand_off",
                "cool_thermo_off",
                "cool_thermo_on",
                "heat_demand_off",
                "heat_thermo_off",
                "heat_thermo_on",
                "dhw_off",
                "dhw_on",
                "pool_off",
                "pool_on",
                "alarm",
            )
        )
    },
    unknown="operation_state_unknown",
)

ALARM_CODE = Prefixed("alarm_code_")

OTC_METHOD_HEATING = EnumCodec(
    {
        0: OTCCalculationMethod.DISABLED,
        1: OTCCalculationMethod.POINTS,
        2: OTCCalculationMethod.GRADIENT,
        3: OTCCalculationMethod.FIX,
    }
)
# Cooling has no Gradient option: 0 disabled, 1 points, 2 fix.
OTC_METHOD_COOLING = EnumCodec(
    {
        0: OTCCalculationMethod.DISABLED,
        1: OTCCalculationMethod.POINTS,
        2: OTCCalculationMethod.FIX,
    }
)

# Unit model ids shared by every gateway; each map accepts its own subset.
UNIT_MODELS = {
    0: "yutaki_s",
    1: "yutaki_s_combi",
    2: "yutaki_s80",
    3: "yutaki_m",
    4: "yutaki_sc_lite",
    5: "yutampo_r32",
    6: "ycc",
}


def unit_model(*ids: int) -> EnumCodec:
    """Return the unit model codec of a gateway documenting ``ids``."""
    return EnumCodec({i: UNIT_MODELS[i] for i in ids}, unknown="unknown")
