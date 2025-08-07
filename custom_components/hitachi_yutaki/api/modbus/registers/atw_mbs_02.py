"""ATW-MBS-02 register map (initial, 1:1 migration from const.py).

For now, we aggregate the const.py REGISTER_* dictionaries into a single logical
key space so the coordinator can keep using the same keys in self.data.
"""
from __future__ import annotations

from typing import Dict

from . import HitachiRegisterMap


class AtwMbs02RegisterMap(HitachiRegisterMap):
    def __init__(self) -> None:
        # Imported 1:1 from const.py to keep behavior identical
        self._control = {
            # Control registers
            "unit_power": 1000,
            "unit_mode": 1001,
            "circuit1_power": 1002,
            "circuit1_otc_calculation_method_heating": 1003,
            "circuit1_otc_calculation_method_cooling": 1004,
            "circuit1_max_flow_temp_heating_otc": 1005,
            "circuit1_max_flow_temp_cooling_otc": 1006,
            "circuit1_eco_mode": 1007,
            "circuit1_heat_eco_offset": 1008,
            "circuit1_cool_eco_offset": 1009,
            "circuit1_thermostat": 1010,
            "circuit1_target_temp": 1011,
            "circuit1_current_temp": 1012,
            "circuit2_power": 1013,
            "circuit2_otc_calculation_method_heating": 1014,
            "circuit2_otc_calculation_method_cooling": 1015,
            "circuit2_max_flow_temp_heating_otc": 1016,
            "circuit2_max_flow_temp_cooling_otc": 1017,
            "circuit2_eco_mode": 1018,
            "circuit2_heat_eco_offset": 1019,
            "circuit2_cool_eco_offset": 1020,
            "circuit2_thermostat": 1021,
            "circuit2_target_temp": 1022,
            "circuit2_current_temp": 1023,
            "dhw_power": 1024,
            "dhw_target_temp": 1025,
            "dhw_boost": 1026,
            "dhw_high_demand": 1027,
            "pool_power": 1028,
            "pool_target_temp": 1029,
            "dhw_antilegionella": 1030,
            "dhw_antilegionella_temp": 1031,
        }
        # Sensor registers
        self._sensor = {
            "operation_state": 1090,
            "outdoor_temp": 1091,
            "water_inlet_temp": 1092,
            "water_outlet_temp": 1093,
            "water_target_temp": 1219,
            "water_flow": 1220,
            "pump_speed": 1221,
            "dhw_current_temp": 1080,
            "pool_current_temp": 1083,
            "compressor_tg_gas_temp": 1206,
            "compressor_ti_liquid_temp": 1207,
            "compressor_td_discharge_temp": 1208,
            "compressor_te_evaporator_temp": 1209,
            "compressor_evi_indoor_expansion_valve_opening": 1210,
            "compressor_evo_outdoor_expansion_valve_opening": 1211,
            "compressor_frequency": 1212,
            "compressor_current": 1214,
            "power_consumption": 1098,
            "alarm_code": 1223,
            "dhw_antilegionella_status": 1030,
        }
        # R134a specific (S80 only)
        self._r134a = {
            "r134a_discharge_temp": 1224,
            "r134a_suction_temp": 1225,
            "r134a_discharge_pressure": 1226,
            "r134a_suction_pressure": 1227,
            "r134a_compressor_frequency": 1228,
            "r134a_valve_opening": 1229,
            "r134a_compressor_current": 1230,
            "r134a_retry_code": 1231,
            "r134a_hp_pressure": 1150,
            "r134a_lp_pressure": 1151,
        }
        # Basic config/status registers that coordinator also reads
        self._config = {
            "unit_model": 1218,
            "system_config": 1089,
            "system_status": 1222,
            "system_state": 1094,
            "central_control_mode": 1088,
        }
        # Global index for quick lookup
        self._map: Dict[str, int] = {**self._control, **self._sensor, **self._r134a, **self._config}

    def address_for_key(self, key: str) -> int:
        try:
            return self._map[key]
        except KeyError:
            raise KeyError(f"Unknown logical key: {key}")

    def keys(self):
        return self._map.keys()

    def control_keys(self):
        return self._control.keys()

    def sensor_keys(self):
        return self._sensor.keys()

    def r134a_keys(self):
        return self._r134a.keys()

    def config_keys(self):
        return self._config.keys()

