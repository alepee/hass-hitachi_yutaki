"""Base classes for Hitachi API."""

from abc import ABC, abstractmethod
from typing import Any

from custom_components.hitachi_yutaki.const import CIRCUIT_IDS, CIRCUIT_MODES


class HitachiApiClient(ABC):
    """Abstract class for a Hitachi API client."""

    @property
    @abstractmethod
    def register_map(self) -> Any:
        """Return the register map for the gateway."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the API."""

    @abstractmethod
    async def close(self) -> bool:
        """Close the connection to the API."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Return True if the client is connected to the API."""

    @property
    @abstractmethod
    def capabilities(self) -> dict:
        """Return the capabilities of the gateway."""

    @abstractmethod
    async def get_model_key(self) -> str:
        """Return the model of the heat pump."""

    @abstractmethod
    async def async_get_unique_id(self) -> str | None:
        """Get a unique hardware identifier for this gateway.

        Reads hardware-specific registers to build a stable identifier
        that persists across reboots and IP changes.

        Returns:
            A string identifier (e.g., "3846-103-56") or None if unavailable.

        Note:
            Connection must be established before calling this method.

        """

    @abstractmethod
    async def read_value(self, key: str) -> int | None:
        """Read a value from the API."""

    @abstractmethod
    async def write_value(self, key: str, value: int) -> bool:
        """Write a value to the API."""

    @abstractmethod
    async def read_values(self, keys_to_read: list[str]) -> None:
        """Fetch data from the heat pump for the given keys."""

    @property
    @abstractmethod
    def has_dhw(self) -> bool:
        """Return True if DHW is configured."""

    @abstractmethod
    def has_circuit(self, circuit_id: CIRCUIT_IDS, mode: CIRCUIT_MODES) -> bool:
        """Return True if circuit is configured."""

    @property
    @abstractmethod
    def has_pool(self) -> bool:
        """Return True if pool heating is configured."""

    @abstractmethod
    def decode_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Decode raw config data into a dictionary of boolean flags."""

    @property
    @abstractmethod
    def is_defrosting(self) -> bool:
        """Return True if the unit is in defrost mode."""

    @property
    @abstractmethod
    def is_solar_active(self) -> bool:
        """Return True if solar system is active."""

    @property
    @abstractmethod
    def is_pump1_running(self) -> bool:
        """Return True if pump 1 is running."""

    @property
    @abstractmethod
    def is_pump2_running(self) -> bool:
        """Return True if pump 2 is running."""

    @property
    @abstractmethod
    def is_pump3_running(self) -> bool:
        """Return True if pump 3 is running."""

    @property
    @abstractmethod
    def is_compressor_running(self) -> bool:
        """Return True if compressor is running."""

    @property
    @abstractmethod
    def is_boiler_active(self) -> bool:
        """Return True if backup boiler is active."""

    @property
    @abstractmethod
    def is_dhw_heater_active(self) -> bool:
        """Return True if DHW electric heater is active."""

    @property
    @abstractmethod
    def is_space_heater_active(self) -> bool:
        """Return True if space heating electric heater is active."""

    @property
    @abstractmethod
    def is_smart_function_active(self) -> bool:
        """Return True if smart grid function is active."""

    @property
    @abstractmethod
    def is_primary_compressor_running(self) -> bool:
        """Return True if primary compressor is running."""

    @property
    @abstractmethod
    def is_secondary_compressor_running(self) -> bool:
        """Return True if secondary compressor is running."""

    @property
    @abstractmethod
    def is_antilegionella_active(self) -> bool:
        """Return True if anti-legionella cycle is running."""

    # Unit control - Getters
    @abstractmethod
    def get_unit_power(self) -> bool | None:
        """Get the main unit power state."""

    @abstractmethod
    def get_unit_mode(self):
        """Get the current unit mode (returns HVACMode: COOL/HEAT/AUTO)."""

    # Unit control - Setters
    @abstractmethod
    async def set_unit_power(self, enabled: bool) -> bool:
        """Enable/disable the main heat pump unit."""

    @abstractmethod
    async def set_unit_mode(self, mode) -> bool:
        """Set the unit operation mode (HVACMode: COOL/HEAT/AUTO)."""

    # Circuit control - Getters
    @abstractmethod
    def get_circuit_power(self, circuit_id: CIRCUIT_IDS) -> bool | None:
        """Get circuit power state."""

    @abstractmethod
    def get_circuit_current_temperature(self, circuit_id: CIRCUIT_IDS) -> float | None:
        """Get current temperature for a circuit (in °C)."""

    @abstractmethod
    def get_circuit_target_temperature(self, circuit_id: CIRCUIT_IDS) -> float | None:
        """Get target temperature for a circuit (in °C)."""

    @abstractmethod
    def get_circuit_eco_mode(self, circuit_id: CIRCUIT_IDS) -> bool | None:
        """Get ECO mode state for a circuit (True=ECO, False=COMFORT)."""

    @abstractmethod
    def get_circuit_thermostat(self, circuit_id: CIRCUIT_IDS) -> bool | None:
        """Get Modbus thermostat state for a circuit."""

    @abstractmethod
    def get_circuit_otc_method_heating(self, circuit_id: CIRCUIT_IDS) -> int | None:
        """Get OTC calculation method for heating."""

    @abstractmethod
    def get_circuit_otc_method_cooling(self, circuit_id: CIRCUIT_IDS) -> int | None:
        """Get OTC calculation method for cooling."""

    @abstractmethod
    def get_circuit_max_flow_temp_heating(
        self, circuit_id: CIRCUIT_IDS
    ) -> float | None:
        """Get maximum heating water temperature for OTC (in °C)."""

    @abstractmethod
    def get_circuit_max_flow_temp_cooling(
        self, circuit_id: CIRCUIT_IDS
    ) -> float | None:
        """Get maximum cooling water temperature for OTC (in °C)."""

    @abstractmethod
    def get_circuit_heat_eco_offset(self, circuit_id: CIRCUIT_IDS) -> int | None:
        """Get temperature offset for ECO heating mode (in °C)."""

    @abstractmethod
    def get_circuit_cool_eco_offset(self, circuit_id: CIRCUIT_IDS) -> int | None:
        """Get temperature offset for ECO cooling mode (in °C)."""

    # Circuit control - Setters
    @abstractmethod
    async def set_circuit_power(self, circuit_id: CIRCUIT_IDS, enabled: bool) -> bool:
        """Enable/disable a heating/cooling circuit."""

    @abstractmethod
    async def set_circuit_target_temperature(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set target temperature for a circuit (in °C)."""

    @abstractmethod
    async def set_circuit_eco_mode(
        self, circuit_id: CIRCUIT_IDS, enabled: bool
    ) -> bool:
        """Enable/disable ECO mode for a circuit."""

    @abstractmethod
    async def set_circuit_thermostat(
        self, circuit_id: CIRCUIT_IDS, enabled: bool
    ) -> bool:
        """Enable/disable Modbus thermostat for a circuit."""

    @abstractmethod
    async def set_circuit_otc_method_heating(
        self, circuit_id: CIRCUIT_IDS, method: int
    ) -> bool:
        """Set OTC calculation method for heating (0=disabled, 1=points, 2=gradient, 3=fix)."""

    @abstractmethod
    async def set_circuit_otc_method_cooling(
        self, circuit_id: CIRCUIT_IDS, method: int
    ) -> bool:
        """Set OTC calculation method for cooling (0=disabled, 1=points, 2=fix)."""

    @abstractmethod
    async def set_circuit_max_flow_temp_heating(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set maximum heating water temperature for OTC (in °C)."""

    @abstractmethod
    async def set_circuit_max_flow_temp_cooling(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set maximum cooling water temperature for OTC (in °C)."""

    @abstractmethod
    async def set_circuit_heat_eco_offset(
        self, circuit_id: CIRCUIT_IDS, offset: int
    ) -> bool:
        """Set temperature offset for ECO heating mode (in °C)."""

    @abstractmethod
    async def set_circuit_cool_eco_offset(
        self, circuit_id: CIRCUIT_IDS, offset: int
    ) -> bool:
        """Set temperature offset for ECO cooling mode (in °C)."""

    # DHW control - Getters
    @abstractmethod
    def get_dhw_power(self) -> bool | None:
        """Get DHW power state."""

    @abstractmethod
    def get_dhw_current_temperature(self) -> float | None:
        """Get current DHW temperature (in °C)."""

    @abstractmethod
    def get_dhw_target_temperature(self) -> float | None:
        """Get DHW target temperature (in °C)."""

    @abstractmethod
    def get_dhw_high_demand(self) -> bool | None:
        """Get DHW high demand mode state."""

    @abstractmethod
    def get_dhw_boost(self) -> bool | None:
        """Get DHW boost mode state."""

    @abstractmethod
    def get_dhw_antilegionella_temperature(self) -> float | None:
        """Get anti-legionella target temperature (in °C)."""

    # DHW control - Setters
    @abstractmethod
    async def set_dhw_power(self, enabled: bool) -> bool:
        """Enable/disable domestic hot water production."""

    @abstractmethod
    async def set_dhw_target_temperature(self, temperature: float) -> bool:
        """Set DHW target temperature (in °C)."""

    @abstractmethod
    async def set_dhw_high_demand(self, enabled: bool) -> bool:
        """Enable/disable DHW high demand mode."""

    @abstractmethod
    async def set_dhw_boost(self, enabled: bool) -> bool:
        """Enable/disable DHW boost mode."""

    @abstractmethod
    async def start_dhw_antilegionella(self) -> bool:
        """Start anti-legionella treatment cycle."""

    @abstractmethod
    async def set_dhw_antilegionella_temperature(self, temperature: float) -> bool:
        """Set anti-legionella target temperature (in °C)."""

    # Pool control - Getters
    @abstractmethod
    def get_pool_power(self) -> bool | None:
        """Get pool heating power state."""

    @abstractmethod
    def get_pool_current_temperature(self) -> float | None:
        """Get current pool temperature (in °C)."""

    @abstractmethod
    def get_pool_target_temperature(self) -> float | None:
        """Get pool target temperature (in °C)."""

    # Pool control - Setters
    @abstractmethod
    async def set_pool_power(self, enabled: bool) -> bool:
        """Enable/disable pool heating."""

    @abstractmethod
    async def set_pool_target_temperature(self, temperature: float) -> bool:
        """Set pool target temperature (in °C)."""
