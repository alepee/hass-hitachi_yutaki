"""A gateway reboot inside a read must not publish another unit's data (#476).

End to end, with the real HC-A(16/64)MB client and transport on a mocked
pymodbus client: the gateway reboots between two polls less than a minute
apart, a unit missing at re-enumeration shifts the others, and the client
reconnects on its own in the middle of the read. The second poll must notice
the new connection and check the unit before publishing anything.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ConnectionException
import pytest

from custom_components.hitachi_yutaki.api.modbus.hc_a_mb import HcAMbApiClient
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.transport import ModbusTransport
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import UpdateFailed

EMPTY = [0, 255, 255, 255]
# Dump A from #476: 2x Yutaki S, 2x Yutampo R32; this entry's unit (5, 6) in slot 2.
DUMP_A = [1, 0, 0, 0, 1, 1, 1, 1, 1, 5, 6, 2, 1, 7, 8, 3] + EMPTY * 12
# Unit (0, 0) absent at re-enumeration: slot 2 now holds unit (7, 8).
SHIFTED = [1, 1, 1, 0, 1, 5, 6, 1, 1, 7, 8, 2] + EMPTY * 13


def _result(registers: list[int]) -> MagicMock:
    result = MagicMock()
    result.isError.return_value = False
    result.registers = registers
    return result


class FakeGateway:
    """A pymodbus client whose gateway can reboot under it."""

    def __init__(self) -> None:
        """Serve DUMP_A on an open socket."""
        self.table = DUMP_A
        self.drop_next_read = False
        self.client = MagicMock()
        self.client.is_socket_open.return_value = True
        self.client.connect.side_effect = self._connect
        self.client.socket = object()
        self.client.read_input_registers.side_effect = self._read_table
        self.client.read_holding_registers.side_effect = self._read_holding

    def _connect(self) -> bool:
        self.client.socket = object()
        return True

    def _read_table(self, address: int, count: int, **_kwargs) -> MagicMock:
        start = address - 200
        return _result(self.table[start : start + count])

    def _read_holding(self, address: int, count: int = 1, **_kwargs) -> MagicMock:
        if self.drop_next_read:
            self.drop_next_read = False
            raise ConnectionException("connection reset by rebooting gateway")
        return _result([0] * count)

    def reboot(self) -> None:
        """Re-enumerate the units, shifted, and drop the open connection."""
        self.table = SHIFTED
        self.drop_next_read = True


@pytest.fixture
def gateway() -> FakeGateway:
    """Return the fake gateway."""
    return FakeGateway()


@pytest.fixture
def coordinator(gateway):
    """Return a coordinator polling the unit (5, 6) bound to slot 2."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda f, *a: f(*a))
    hass.async_create_task.side_effect = lambda coroutine: coroutine.close()
    transport = ModbusTransport(hass, "127.0.0.1", 502, 1)
    transport._client = gateway.client
    client = HcAMbApiClient(
        hass,
        "test",
        "127.0.0.1",
        502,
        1,
        register_map=HcAMbRegisterMap(unit_id=2),
        transport=transport,
    )
    client._unit_identity = (5, 6)

    entry = MagicMock()
    entry.entry_id = "entry"
    # Telemetry is off: drop the one-time send instead of leaving its
    # coroutine unawaited in a mock.
    entry.async_create_background_task.side_effect = (
        lambda _hass, coroutine, name=None: coroutine.close()
    )
    entry.data = {CONF_SCAN_INTERVAL: 5}
    profile = MagicMock()
    profile.extra_register_keys = []
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        coord = HitachiYutakiDataCoordinator(hass, entry, client, profile)
    coord.telemetry_collector = TelemetryCollector(level=TelemetryLevel.OFF)
    coord.telemetry_client = NoopTelemetryClient()
    return coord


@pytest.mark.asyncio
async def test_gateway_reboot_inside_a_read_does_not_publish_another_unit(
    coordinator, gateway
):
    """The reconnection is caught and the moved unit detected, not published."""
    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir"),
        patch("custom_components.hitachi_yutaki.api.modbus.ir"),
        patch(
            "custom_components.hitachi_yutaki.api.modbus.transport.ModbusTcpClient",
            return_value=gateway.client,
        ),
    ):
        assert (await coordinator._async_update_data())["is_available"] is True

        # Seconds later, well inside the periodic check interval.
        gateway.reboot()
        with pytest.raises(UpdateFailed, match="unit moved"):
            await coordinator._async_update_data()

    coordinator.hass.config_entries.async_schedule_reload.assert_called_once_with(
        "entry"
    )
