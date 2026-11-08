# Troubleshooting

## Gateway shows "Desynchronized" or "Not Ready"

The integration displays a warning when the gateway reports a "not ready" state. This covers three cases: the "desynchronized" state, which the gateway reports when it has had no communication with the heat pump for more than 180 seconds; the "initializing" state (data initialization at startup or after a power cycle), which is not tied to the 180 second window; and a gateway that answers Modbus but returns `0xFFFF` for its state and every other register, meaning it receives no data at all from the heat pump (repair issue "Hitachi gateway receives no heat pump data"). When any of them is reported, register reads are paused because the data is not guaranteed to be fresh or correct — it could be stale values from before communication was lost, or initial gateway values (e.g., empty registers from startup).

**Possible causes:**

### Part of the system is off or disconnected

The gateway only relays what the heat pump sends over H-LINK. Check that the whole system is powered on and connected: indoor unit, outdoor unit and gateway, with the H-LINK cable in place. A heat pump switched off at its breaker while the gateway stays powered is the typical "no heat pump data" case.

### Wrong H-LINK terminals

The ATW-MBS-02 must be connected to the **H-LINK terminals** on the heat pump PCB. The H-LINK line is a non-polarity twisted pair (see [ATW-MBS-02 datasheet](gateway/atw-mbs-02.md)). Some PCBs also expose Remote Controller terminals that look similar but are not meant for the Modbus gateway. Connecting to the wrong pair causes a permanent communication alarm. Terminal numbering varies by unit, so refer to the Hitachi installation manual for your model to identify the correct H-LINK pair.

**Symptoms:** the gateway is always reported as desynchronized, the scanner may detect the wrong gateway type, some register values appear shifted or incoherent.

**Fix:** check the wiring on the indoor unit PCB and move the H-LINK cable to the H-LINK terminals per your unit's installation manual.

### Unsuitable H-LINK cable

Hitachi specifies a shielded twisted pair cable (0.75 mm² section), grounded on one side only. Installers sometimes use standard unshielded cable, which can cause packet loss on the H-LINK bus — especially over longer runs or in electrically noisy environments (near the compressor, inverter, etc.).

**Symptoms:** intermittent desynchronization warnings, unstable sensor readings, communication errors that resolve on their own.

**Fix:** replace the H-LINK cable with a shielded twisted pair (0.75 mm²), grounded on one side only. Keep the cable as short as possible and away from power cables.

### Recent power cycle

After a power cycle of the gateway or the heat pump, the H-LINK bus needs a few minutes to synchronize. During this time, the integration reports the gateway as "initializing" or "desynchronized." A setup or reload that lands in this window is deferred: Home Assistant shows the entry as "Retrying setup" and tries again on its own, with an increasing delay, until H-LINK is synchronized. The integration waits for a synchronized read because the heat pump capabilities it carries decide which devices and entities are created. Setup is also deferred if the gateway returns an invalid system configuration (`0xFFFF`), which happens while the bus is unstable.

**Fix:** wait 3-5 minutes after a restart. If the issue persists beyond that, check the wiring.

## Outdoor sensors unavailable, alarm 03

Alarm 03 means the indoor unit has lost contact with the outdoor unit (power supply or communication cable between the two units). The gateway is fine: it keeps talking to the indoor unit, which reports `0` for everything it would normally relay from the outdoor unit. While the alarm lasts, the integration shows those readings (outdoor temperature, compressor discharge and evaporator temperatures, outdoor expansion valve, frequency, current) as unavailable rather than a false 0, and raises a repair issue. A non-zero outdoor temperature from an auxiliary sensor wired to the indoor unit is still shown.

**Fix:** check the outdoor unit's power supply and the cable between the two units, then contact your installer if the alarm persists. The repair issue and the sensors come back on their own once the unit no longer reports the alarm.

## Yutaki M ignores the room temperature sent by Home Assistant

The External room sensor switch is on, the LCD controller shows the room temperature and the room setpoint written by Home Assistant, but the unit never starts heating on them (and never stops either): it behaves as if the room value did not exist.

### Indoor unit firmware too old (ATW-YMM-01)

On first-generation Yutaki M units, whose indoor control board is the **ATW-YMM-01**, regulation on a room temperature received over Modbus needs board firmware **H-0162 or later** (confirmed by Hitachi UK, [discussion #521](https://github.com/alepee/hass-hitachi_yutaki/discussions/521)). Boards shipped around 2017 can still run **H-0144**: the gateway accepts the room registers and the LCD displays them, but the unit never generates a heating demand from them. Basic Modbus control and monitoring work normally, which makes the cause easy to miss.

Known ATW-YMM-01 releases: H-0144 (original), H-0162 (minimum for Modbus room regulation), H-0216, H-0322 (June 2024). The newer **ATW-YMM-02** board has its own numbering, so these thresholds do not apply to it (H-0286 is known to work with Modbus room regulation).

**Check:** open the **Control Unit** device in Home Assistant: its firmware field reads `PCB H-xxxx / LCD H-xxxx`, the `PCB` part being the indoor board firmware. The LCD controller shows the same number under Menu → About → System Information ("Indoor PCB firmware").

**Fix:** the ATW-YMM-01 firmware can be updated in the field. Contact Hitachi support or your installer to have the board flashed to a recent release. Hitachi also recommends the PC-ARFH1E controller with this board rather than the PC-ARFH2E.

If the firmware is recent enough, check the unit's own configuration instead (room thermostat declared, central control mode, Demand ON/OFF input): see [Room regulation](reference/entities.md#room-regulation).
