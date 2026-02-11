"""Compressor timing sensor for Hitachi Yutaki."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType

from ....adapters.storage.in_memory import InMemoryStorage
from ....adapters.storage.recorder_rehydrate import async_replay_compressor_states
from ....coordinator import HitachiYutakiDataCoordinator
from ....domain.services.timing import CompressorHistory, CompressorTimingService
from .base import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

_LOGGER = logging.getLogger(__name__)

# This is a placeholder for a future configuration option
COMPRESSOR_HISTORY_SIZE = 100
# Look back a few hours in the Recorder history to rebuild compressor cycles.
COMPRESSOR_HISTORY_LOOKBACK = timedelta(hours=6)


class HitachiYutakiTimingSensor(HitachiYutakiSensor):
    """Sensor for compressor timing measurements."""

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the timing sensor."""
        super().__init__(coordinator, description, device_info)

        storage = InMemoryStorage(max_len=COMPRESSOR_HISTORY_SIZE)
        history = CompressorHistory(
            storage=storage, max_history=COMPRESSOR_HISTORY_SIZE
        )
        self._timing_service = CompressorTimingService(history=history)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        await self._async_rehydrate_compressor_history()

    async def _async_rehydrate_compressor_history(self) -> None:
        """Replay Recorder data to rebuild compressor timing statistics."""
        entity_key = (
            "secondary_compressor_running"
            if "secondary" in self.entity_description.key
            else "compressor_running"
        )
        entity_id = self._resolve_entity_id("binary_sensor", entity_key)
        if not entity_id:
            _LOGGER.debug(
                "Skipping compressor history replay for %s, entity %s missing",
                self.entity_id,
                entity_key,
            )
            return

        try:
            states = await async_replay_compressor_states(
                hass=self.hass,
                entity_id=entity_id,
                window=COMPRESSOR_HISTORY_LOOKBACK,
                max_states=COMPRESSOR_HISTORY_SIZE,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to replay compressor Recorder history for %s", self.entity_id
            )
            return

        if not states:
            _LOGGER.debug("No compressor Recorder history found for %s", self.entity_id)
            return

        self._timing_service.preload_states(states)
        _LOGGER.debug(
            "Rehydrated %s compressor states for %s",
            len(states),
            self.entity_id,
        )

    async def async_update_timing(self) -> None:
        """Update timing values from history."""
        frequency = self.coordinator.data.get(
            "secondary_compressor_frequency"
            if "secondary" in self.entity_description.key
            else "compressor_frequency"
        )
        self._timing_service.update(frequency)

    @property
    def native_value(self) -> StateType:
        """Return the timing sensor value."""
        if self.coordinator.data is None:
            return None

        timing = self._timing_service.get_timing()
        key = self.entity_description.key
        if "cycle_time" in key:
            return timing.cycle_time
        elif "runtime" in key:
            return timing.runtime
        elif "resttime" in key:
            return timing.resttime

        return None
