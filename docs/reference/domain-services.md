# Domain Services Reference

Domain services contain the pure business logic of the integration. They live in
`custom_components/hitachi_yutaki/domain/services/` and have **zero** Home Assistant
dependencies -- only stdlib imports. This makes them testable without mocks or a
running HA instance. See [Architecture](../architecture.md) for how this layer fits
into the hexagonal design.

## Time dependency

The `domain/ports/clock.py` protocol separates monotonic elapsed seconds from
timezone-aware local civil time. `adapters/clock.py` implements it using HA's
configured timezone. Services receive that clock or explicit historical
timestamps; they do not read the system clock themselves. Monotonic durations
keep integration and recovery timers stable across wall-clock adjustments.

---

## COP Calculation

**File:** `domain/services/cop.py`

Computes the Coefficient of Performance by integrating thermal and electrical power
measurements over a sliding time window (default 30 minutes).

### Key classes

| Class | Role |
|---|---|
| `COPService` | Orchestrator -- accepts `COPInput`, delegates to calculators, stores results in the accumulator. |
| `EnergyAccumulator` | Stores `PowerMeasurement` samples and computes COP via trapezoidal integration. |

### Input

`COPInput` carries: water inlet/outlet temperatures, water flow, compressor
current/frequency, optional secondary compressor data, and operation mode.

### Quality levels

| Level | Condition |
|---|---|
| `no_data` | No measurements stored |
| `insufficient_data` | < 5 measurements **or** time span < 5 min |
| `preliminary` | < 15 measurements **or** time span < 15 min |
| `optimal` | >= 15 measurements **and** time span >= 15 min |

### COP formula

```
COP = total_thermal_energy / total_electrical_energy
```

Both energies are computed with trapezoidal integration over the measurement window.
Valid range: 0.5 -- 8.0. Measurements are taken at most once per 60 seconds.

### Dependencies (ports)

`ThermalPowerCalculator` and `ElectricalPowerCalculator` are injected as protocols.
A `Storage[PowerMeasurement]` backend holds the sliding window.
The clock supplies the live measurement interval and timestamps. Historical
inputs use explicit timestamps.

### Live and historical admission

`build_cop_measurement` owns the shared pure validation and calculation rules.
`COPService.build_measurement` applies the configured mode filter and calculators
to a historical input without mutating live state. The Recorder adapter
normalizes each historical snapshot and passes it through that same path.
Directional thermal calculators remain directional during replay. A measured
whole-unit electrical power reading has priority, including when compressor
current is zero, and secondary currents are summed before a fallback estimate.
History buffers reject a mixture of naive and timezone-aware timestamps before
mutation; the production Recorder path supplies UTC-aware timestamps.

---

## Thermal Energy

**Directory:** `domain/services/thermal/`

Tracks real-time thermal power and accumulates energy for both heating and cooling,
keeping them strictly separated.

### Key classes

| Class | Role |
|---|---|
| `ThermalPowerService` | Entry point -- validates inputs, calls calculators, delegates to accumulator. |
| `ThermalEnergyAccumulator` | Maintains daily and total energy counters for heating and cooling independently. |

### Heating vs cooling separation

The sign of the water temperature delta determines the mode:

- **Heating:** outlet > inlet (positive delta T)
- **Cooling:** outlet < inlet (negative delta T)

DHW and pool modes are **always** classified as heating, regardless of delta T. This
prevents transient negative deltas during mode switches from being counted as cooling.

### Thermal power formula

```
Q = flow_kg_per_s * 4.185 * delta_T
```

Where `flow_kg_per_s = water_flow_m3h * 0.277778` and `delta_T = outlet - inlet`.
Functions `calculate_thermal_power_heating` and `calculate_thermal_power_cooling`
return the positive magnitude for their respective mode, or zero.

### Post-cycle lock

After the compressor stops, thermal inertia keeps delta T non-zero for a while.
The accumulator activates a **post-cycle lock** once the power in the last active
mode drops to zero. While locked, power for that mode is forced to zero. The lock
releases when the compressor restarts.

### Energy counters

- **Daily energy** -- resets automatically at midnight (date change detection).
- **Total energy** -- persistent across HA restarts via restore methods.
- Integration uses trapezoidal averaging between consecutive measurements.

---

## Defrost Guard

**File:** `domain/services/defrost_guard.py`

Filters out unreliable sensor data during heat pump defrost cycles so that COP
and thermal calculations are not polluted by inverted temperature readings.

### State machine

```
NORMAL ──(is_defrosting=True)──> DEFROST
DEFROST ──(is_defrosting=False)──> RECOVERY
RECOVERY ──(stable readings)──> NORMAL
RECOVERY ──(is_defrosting=True)──> DEFROST   (defrost restarts)
```

### Recovery exit conditions

The guard leaves RECOVERY and returns to NORMAL when **either**:

1. **Stable readings** -- 3 consecutive readings where delta T sign matches the
   pre-defrost sign (with a 0.5 C deadband), or
2. **Timeout** -- 5 minutes (300 s) elapsed since entering RECOVERY.

### Usage

```python
guard.update(is_defrosting=True, delta_t=current_delta_t)
if guard.is_data_reliable:
    # safe to feed data into COP / thermal services
```

Construct the guard with an injected clock, or pass an explicit elapsed
`timestamp` to `update`. Its timeout uses elapsed time rather than civil dates.
Historical electrical events may advance timeout checks but do not count as
fresh stable thermal readings. If Recorder omits complete temperature
observations, replay conservatively waits for the recovery timeout.

---

## Compressor Timing

**File:** `domain/services/timing.py`

Tracks compressor on/off transitions and derives typical (median) cycle, runtime,
and rest durations for diagnostics.

### Key classes

| Class | Role |
|---|---|
| `CompressorTimingService` | Accepts compressor frequency updates and delegates to history. |
| `CompressorHistory` | Records state transitions, computes medians from the last N events. |

### Output

`CompressorTimingResult` with three optional fields (all in minutes):

- `cycle_time` -- median full cycle (start to next start)
- `runtime` -- median compressor on duration
- `resttime` -- median compressor off duration

An off period longer than `STANDBY_THRESHOLD_MIN` (60 min) is a standby (no
demand, night setback), not the rest phase of a cycle: the restart that ends it
records neither a cycle nor a rest time, the next cycle is measured from it.

Historical states are preloaded from the Recorder (48 h lookback, enough to refill
the 100-cycle window) so the values do not depend on when Home Assistant last
restarted.

## Electrical Energy and Cost

**File:** `domain/services/electrical_energy.py`

`ElectricalEnergyAccumulator` integrates electrical kW into kWh and accumulates
cost using the optional price for the current poll. Its gap bound is the larger
of three configured scan intervals and 30 seconds. Negative elapsed durations
contribute no energy. Missing prices preserve energy accumulation while leaving
cost unchanged. Restore methods seed existing counters without integrating HA
downtime; the adapter owns HA state retrieval and persistence.

## Circuit Activity

**File:** `domain/services/circuit.py`

`resolve_circuit_activity` receives normalized circuit power, compressor,
defrost and operation-mode observations. Actual operation state has priority
over the selected global mode: DHW and pool production leave a powered
space-conditioning circuit idle. The adapter supplies observations and the
entity only maps `CircuitActivity` to HA's `HVACAction`.

## Room Target Keeper

**File:** `domain/services/room_target.py`

`RoomTargetKeeper` remembers each circuit's last valid room target (the
register's documented 5.0-35.0 °C range) and whether its External room sensor
flag was on, and decides when to write them back (#511). Two resets were
reproduced in the field: a controller board power cycle zeroes the target while
the flag stays on, a gateway reset lowers the flag while the target survives.
`observe(circuit_id, enabled, target, now, *, keep_enabled, after_gap)` returns
a `RoomRestore(target, enable)`: the stored target when the flag is on (or
about to be raised), the reading is out of range and a valid target was seen
before; `enable=True` when `keep_enabled` (the user's opt-in), the flag reads
off, it was last seen on and the drop showed up on the first good poll after a
failure (`after_gap`). A flag lowered while the gateway stayed reachable was
lowered by Home Assistant and is simply remembered off. The flag is never
raised on a target of 0: the target comes back first, in the same decision.
Unread values decide nothing.

A restore is confirmed only by a reading taken `CONFIRM_AFTER_S` (60 s) after
the write, longer than the gateway client's 30 s pending-write shadow, so the
echo of its own write never counts. After `MAX_RESTORE_ATTEMPTS` (3)
unconfirmed restores the circuit is reported by `failed_circuits()` or
`failed_flag_circuits()` and left alone until the register reads right again. A
deliberate user change is just a newer valid target. The coordinator reads the
registers after a successful poll only, writes the target then raises the flag
through the same seeding path as the switch, raises the
`room_target_restore_failed_{entry_id}` and
`external_room_sensor_restore_failed_{entry_id}` repair issues and persists
`serialize()` in a `Store` (`hitachi_yutaki_room_target_{entry_id}`), loaded
before the first poll.

## Maintenance Warning Policy

**File:** `domain/services/maintenance.py`

`refrigerant_alert_policy` requires the configured persistent alert streak and
marks aged evidence as stale without clearing a frozen off-season warning.
`cycling_alert_policy` consumes the cycling monitor's persistent verdict; that
monitor already owns expiry. Their `MaintenanceAlert` output is independent of
HA issue severity, translations and presentation, which remain infrastructure.

---

## Compressor Short-Cycling Detection

**File:** `domain/services/cycling.py`

Detects a compressor that starts and stops too often in space heating. Advisory only.
Full rationale, thresholds and fleet calibration: [Cycling monitoring](cycling-monitoring.md).

### Key class

| Class | Role |
|---|---|
| `CyclingMonitor` | Debounced transition tracking, per-day aggregation, absolute-threshold verdict |

### Design note

This service is the reference implementation of the **absolute threshold per regime**
pattern: no learned baseline, because short cycling is a *stable state* rather than a
drift and a baseline would learn the fault. See
[Preventive maintenance](preventive-maintenance.md) for when to pick which pattern.

---

## Refrigerant Anomaly Detection

**File:** `domain/services/refrigerant.py`

Continuously detects the early signature of a **slow refrigerant charge loss**. Advisory
only — complements, does not replace, the mandatory F-Gas leak-tightness inspection. Full
rationale and user-facing behaviour: [Refrigerant monitoring](refrigerant-monitoring.md).

### Key class

| Class | Role |
|---|---|
| `RefrigerantMonitor` | Gates and reduces per-poll signals into one robust daily aggregate, freezes a baseline, and classifies drift against it. |

### Signals and gas-line superheat

Gas-line superheat `SH = Tg − Te` (THMg gas-pipe thermistor, register 1206; a ~40-60 K
condensing-side lift in heating, not a suction superheat) (`compressor_tg_gas_temp` −
`compressor_te_evaporator_temp`), outdoor expansion-valve opening `EVO`, evaporating
temperature `Te` and outdoor temperature. Gated on `supports_extended_compressor_sensors`
(needs `Tg`/`EVO`; excludes the Yutampo R32). The `SH` plausibility bounds are supplied
per-profile (`gas_superheat_plausible_range`).

### States

| Level | Condition |
|---|---|
| `learning` | Fewer than `BASELINE_DAYS` (14) valid days — baseline not frozen |
| `ok` | Baseline frozen, no significant drift |
| `watch` | Superheat drift ≥ `SUPERHEAT_WATCH_K` from baseline |
| `alert` | Superheat ≥ `SUPERHEAT_ALERT_K` **and** temperature-matched EVO ≥ `EVO_ALERT_PCT` |

### Design notes

- **Daily aggregation:** samples (gated on heating mode, defrost-guard reliability, a steady
  frequency band, plausibility and a 60 s throttle) are reduced to one median-per-day
  `DailyAggregate`, held in an injected `Storage[DailyAggregate]` bounded to `HISTORY_DAYS`.
- **Seasonality:** superheat is a *regulated* quantity (robust to weather) and is the
  primary signal; `EVO` is compared only across days within `TEMP_MATCH_K` of the baseline
  outdoor temperature; `Te` is informational.
- **Persistence:** `serialize()`/`restore()` round-trip the baseline, aggregates and alert
  streak; the adapter persists them via a Home Assistant `Store`. `restore()` validates the
  full payload before touching any state: a malformed snapshot raises `ValueError` and leaves
  the monitor unchanged (atomic restore), so a corrupt `Store` file can never half-load.
  `reset()` clears everything (exposed as the reset button).
- **Time:** like COP, uses `time()` for the throttle and accepts an optional `timestamp` for
  replay/tests.

---

## Electrical Power

**File:** `domain/services/electrical.py`

Estimates electrical power consumption from compressor current with a priority
chain for input data.

> **Scope:** when no measured power is available, the estimate covers the
> **compressor only**. It does not account for the electric backup/immersion
> heater, circulation pumps, fan, or standby loads, and assumes a fixed
> `cos(phi) = 0.9` and default voltage. On Yutampo/DHW-only units, where the
> electric heater carries much of the load, this can under-report by an order of
> magnitude. A configured `measured_power` (Power Sensor option) bypasses the
> estimate entirely (priority 1).

> **Zero current is not a short-circuit.** The adapter calls the calculator on
> every poll, including when the compressor reports 0 A, because the
> measured-power branch does not use the current. This is what lets a Power
> Sensor report standby draw, and what makes it usable at all wherever the
> gateway itself reports a constant 0 A (an HC-A(16/64)MB serves no current for
> a unit read at a secondary refrigerant cycle, even with the compressor
> demonstrably running, #403). With no Power Sensor configured the result is
> unchanged (`U × 0 × cosφ = 0`).

### Priority

1. `measured_power` (direct kW reading, if available)
2. `voltage * current` (measured voltage from Modbus)
3. Default voltage (400 V three-phase / 230 V single-phase)

### Formulas

```
Three-phase:  P = V * I * cos(phi) * sqrt(3) / 1000   [kW]
Single-phase: P = V * I * cos(phi) / 1000              [kW]
```

Constants: `cos(phi) = 0.9`, `sqrt(3) = 1.732`.

---

## Ports

**Directory:** `domain/ports/`

Ports define the contracts that adapters must implement. All are Python Protocols
or abstract base classes.

### ThermalPowerCalculator

```python
class ThermalPowerCalculator(Protocol):
    def __call__(self, inlet: float, outlet: float, flow: float) -> float: ...
```

### ElectricalPowerCalculator

```python
class ElectricalPowerCalculator(Protocol):
    def __call__(self, current: float) -> float: ...
```

### DataProvider

```python
class DataProvider(Protocol):
    def get_water_inlet_temp(self) -> float | None: ...
    def get_water_outlet_temp(self) -> float | None: ...
    def get_water_flow(self) -> float | None: ...
    def get_compressor_current(self) -> float | None: ...
    def get_compressor_frequency(self) -> float | None: ...
    def get_secondary_compressor_current(self) -> float | None: ...
    def get_secondary_compressor_frequency(self) -> float | None: ...
```

### StateProvider

```python
class StateProvider(Protocol):
    def get_float_from_entity(self, config_key: str) -> float | None: ...
```

### Storage\[T\]

```python
class Storage[T](ABC):
    def append(self, item: T) -> None: ...
    def popleft(self) -> T: ...
    def get_all(self) -> list[T]: ...
    def __len__(self) -> int: ...
```

---

## Integration Diagram

```mermaid
graph TD
    PORTS(["domain/ports/<br>Protocols and ABCs define contracts"])

    TP["ThermalPower-<br>Calculator"]
    EP["ElectricalPower-<br>Calculator"]
    ST["Storage T"]

    ATC["adapters/calculators/<br>concrete impls"]
    AEC["adapters/calculators/<br>concrete impls"]
    AST["adapters/storage/<br>InMemoryStorage"]

    SVC(["domain/services/"])

    COP["COP<br>Service"]
    THS["Thermal<br>Service"]
    DFG["Defrost<br>Guard"]
    TIM["Timing<br>Service"]
    ELE["Electrical<br>function"]

    ENT(["entities/&lt;business-domain&gt;/<br>HA entity classes call services for values"])

    PORTS --> TP & EP & ST
    TP --> ATC
    EP --> AEC
    ST --> AST
    ATC & AEC & AST --> SVC
    SVC --> COP & THS & DFG & TIM & ELE
    COP & THS & DFG & TIM & ELE --> ENT
```

Domain services receive their dependencies through constructor injection. Adapters
implement the port protocols and are wired at setup time. Entity classes consume
service outputs but never contain business logic themselves.
