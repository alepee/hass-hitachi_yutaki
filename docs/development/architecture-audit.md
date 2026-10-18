# Architecture boundary remediation

## Scope and baseline

The audit covered all ten architectural axes in `AGENT.md` and
`docs/architecture.md`. The baseline is commit
`5b12877ddc9999daed4f95feca90e41e0903130d` (`2.2.0-beta.10`). The HC-A unit
binding refactor in #476, historical config-entry migrations, and unrelated
style issues were excluded.

Each finding was checked against its surrounding function and existing
abstractions. A separate GPT-6 Astra agent challenged the findings before
implementation. Implementations are split between three Astra agents with
disjoint file ownership; a fourth agent reviews the combined change independently.

## Initial findings and evidence

Paths in this table are relative to `custom_components/hitachi_yutaki/`.
Line numbers identify the baseline, before the fixes.

| # | Finding and initial evidence | Impact | Remediation strategy |
|---|---|---|---|
| 1 | `config_flow.py:373` ignores `ReadResult`; lines 376-379 compare deserialized `system_state` strings to numbers. A not-ready fresh client reaches `invalid_slave` at line 431. | Real risk | Consume the API readiness result and keep gateway state interpretation behind the API boundary. |
| 2 | `entities/control_unit/selects.py:43,63` always offer AUTO. The HC-A map has no writable AUTO mode; `api/modbus/__init__.py:667` excludes it and `entities/base/select.py:108` ignores write failure. | Real risk | Describe writable modes through the client contract and reject unsuccessful entity commands. |
| 3 | `coordinator.py:375` emits `max_circuits = 2 if circuit2 else 1`, although the DHW-only profile declares zero at `profiles/yutampo_r32.py:61`. | Real risk | Use the profile's hardware limit; do not substitute configured circuits for the hardware capability. |
| 4 | `entities/base/climate.py:172` derives activity from selected mode and compressor state. A powered circuit in Heat with `operation_state_dhw_on` is reported as HEATING. | Real risk | Resolve actual circuit activity in the domain and translate that verdict to Home Assistant state. |
| 5 | `adapters/derived_metrics.py:585` uses an absolute thermal calculator during replay, unlike the directional live calculators. At 35 degrees inlet, 30 outlet, and 1 cubic metre/hour, live heating is 0 kW and replay is 5.8125 kW. Replay also rejects zero current at `adapters/storage/recorder_rehydrate.py:139`, even with measured electrical power. | Real risk | Share the pure measurement admission/calculation between live and historical inputs; keep Recorder retrieval in the adapter. |
| 6 | Domain services call wall-clock `time()` directly: `thermal/accumulator.py:208`, `cop.py:203`, `defrost_guard.py:100,112`, `refrigerant.py:140`. At 10 kW, clock values 100 then 90 produce negative accumulated energy, -0.027778 kWh. | Real risk | Inject elapsed-time and calendar dependencies, use monotonic time for durations, and prevent negative integration. |
| 7 | `entities/base/sensor/base.py:171` dispatches alarm and operation-state attributes by sensor name despite the existing `attributes_fn` callback. | Hygiene | Move feature-specific attributes into the control-unit descriptions. |
| 8 | `api/base.py:70` exposes `register_map: Any`; coordinator, flow and entities inspect Modbus register groups, register presence and raw HVAC values. `adapters/derived_metrics.py:335` additionally decodes raw mode values for an unused `COPInput.hvac_action`. | Hygiene | Expose logical keys, readable/writable capabilities and supported modes; hide maps behind the concrete API and remove unused mode inference. |
| 9 | `config_flow.py:8,403,433`, `__init__.py:523,705` and `const.py:153` own pymodbus exceptions, transport-derived fallback identity, configuration URL and compatibility logic. | Hygiene | Put transport-specific metadata and identity in providers, normalize errors in the API, and move pymodbus compatibility into its implementation. |
| 10 | `adapters/derived_metrics.py:303,317` owns energy integration, interruption bounds and cost accumulation instead of delegating them. | Hygiene | Extract a pure energy/cost accumulator; the adapter retrieves HA inputs and restores/persists state. |
| 11 | `coordinator.py:572,575,623` applies alert persistence and refrigerant age thresholds. Cycling already provides its persistent verdict and owns expiry. | Hygiene | Produce a domain alert verdict, including persistence and age, then translate it to HA repair issues. |

## Guardrails

- Preserve config-entry identities and HC-A unit binding established in #476.
- Keep mode global and circuit power independent. With two configured circuits,
  a circuit entity must never change the global operating mode.
- Read sensor values through logical data keys backed by STATUS registers.
- Keep domain imports limited to the standard library and the domain itself.
- Keep external power-meter values historical during Recorder replay; do not
  stamp a live meter value onto old measurements or double-count a whole-unit
  meter on two-compressor models.
- Preserve telemetry payload fields, consent, and the worker contract. This
  change does not require a Worker deployment.
- Retain maintenance-detector consent, persistence and off-season semantics.

## Axes without confirmed violations

The initial audit found no direct sensor register access or CONTROL-backed
sensor violation (axis 7), no cross-circuit global-mode write in the existing
multicircuit guard (axis 8), and no mismatch between Python payload fields and
Worker validation or telemetry-entity attribute access (axis 9).

Domain imports were already standard-library-only. Model-name comparisons
outside profiles were wire decoding in API maps, not model-specific business
branches. Finding 3 concerns overriding a declared profile capability.

## Implemented ownership and regression evidence

| # | Implemented owner / abstraction | Regression evidence |
|---|---|---|
| 1 | `ModbusConfigProvider.async_validate_connection` returns `ConnectionValidation`; the flow does not decode gateway state. | `tests/api/config_providers/test_modbus.py` and `tests/test_config_flow.py`: all three maps, unhealthy readiness and nonblocking pre-2016 state 1. |
| 2 | `HitachiApiClient.supported_unit_modes` and `can_write` describe writable commands. The select surfaces unsuccessful writes as service errors. | `tests/entities/base/test_select.py`: unsupported Auto, read-only mode, write failure and successful refresh. |
| 3 | The coordinator serializes `profile.max_circuits` as the hardware capability. | `test_max_circuits_is_hardware_limit_in_both_payloads`: limits 0/1/2 independently of configured circuits, in installation and fleet ping. |
| 4 | `adapters/circuit.py` normalizes API observations; `domain/services/circuit.py` resolves `CircuitActivity`; the entity maps it to HA. | `tests/domain/test_circuit.py` and `tests/entities/base/test_climate.py`: DHW/pool idle, heat/cool/auto, defrost and multicircuit command isolation. |
| 5 | `build_cop_measurement` is shared by live updates and `COPService.build_measurement` for replay. Recorder normalizes historical states and groups simultaneous changes before admission. | `test_live_replay_identical_samples`: eleven sign/mode/current/meter/S80/defrost scenarios; `test_async_rehydrate_selects_mode_specific_builder` verifies production wiring. |
| 6 | `Clock` separates elapsed and calendar dependencies; `HomeAssistantClock` uses monotonic time and HA's timezone. Domain services accept injection or explicit replay timestamps. | `test_clock_injection.py`: negative duration, local midnight, civil rollback, DST, COP/refrigerant cadence and cycling debounce; `test_clock.py`: HA timezone. |
| 7 | Alarm and operation-state attributes use control-unit description callbacks. The generic base executes only `attributes_fn`. | `test_sensor_dispatch.py`: no-data behavior, code zero, generic callbacks and absence of dispatch by sensor key. |
| 8 | The port exposes `base_keys`, `gateway_keys`, `supports_key`, `can_write` and `supported_unit_modes`. The concrete Modbus client retains its internal map. Unused HVAC inference and the unused COP input field are removed. | `test_capability_contract.py`, `test_poll_uses_client_keys_without_a_register_map`, and `test_cop_uses_operation_state_independently_of_unit_mode`. |
| 9 | Providers own fallback identity, optional configuration URL, gateway endpoint equality and sensitive configuration keys. Pymodbus compatibility is in `api/modbus/compat.py`. | Provider, compatibility, diagnostics and setup identity tests preserve existing fallback IDs, redact provider-declared fields and accept an absent configuration URL. |
| 10 | `ElectricalEnergyAccumulator` owns bounded kWh and tariff accumulation. The adapter retrieves inputs and forwards restored counters. | `test_gap_tolerance_and_nonnegative_energy`, `test_tariffs_missing_price_negative_price_and_restoration`, and existing derived-metric restoration tests. |
| 11 | Pure maintenance policies return `MaintenanceAlert(persistent, stale)`; the coordinator presents HA repair issues. | `test_maintenance.py` and coordinator tests cover persistence, recovery, stale off-season evidence, cycling-owned expiry and consent. |

## Verification process

Three implementation agents ran their assigned targeted suites: 299 API/setup
tests, 163 entity/coordinator tests, and 230 domain/adapter tests. These counts
overlap and must not be added as a total suite count.

The coordinator runs the complete suite with locked dependencies, Ruff lint and
format checks, translation consistency, domain type checking and whitespace
validation. A fourth Astra agent independently reviews the combined production,
test and documentation diff before the pull request is opened.

The final independent-review verdict, full-suite result, PR reference and hosted
CI checks are recorded below after verification.

### Initial combined validation (before review corrections)

- Locked environment: Python 3.13.16, Home Assistant 2026.2.3, Ruff 0.16.10.
- Complete suite: **898 passed in 41.93 seconds**.
- Ruff lint: passed. Ruff format: all 225 Python files already formatted.
- Translation consistency: all four translations match the 420 English keys.
- Domain `ty` check: passed. `git diff --check`: passed.
- No integration tests contacted a physical gateway. Hardware behavior is
  covered through real register-map implementations and mocked transport.

### Independent review and follow-up

The first independent review requested one correction: Recorder events were
counted as fresh thermal samples even when only an external power meter changed.
With defrost ending at 100 seconds and meter updates at 101, 102 and 103 seconds,
replay accepted a COP sample at 103 seconds while live polling waited until 115.
The original synchronous replay fixture could not expose that discrepancy.

`DefrostGuard` now distinguishes fresh thermal observations from other events.
Other events still advance timeout checks but cannot prove thermal stability.
Replay only counts a complete inlet/outlet observation as a thermal sample.
When Recorder omits unchanged temperatures, recovery remains conservative until
the timeout rather than inventing stable readings from cached values.
`test_meter_events_do_not_end_defrost_recovery` uses actual HA `State` objects
and asynchronous meter histories; both cases failed before the correction and
pass after it. Complete thermal records produce live/replay samples at 0, 115
and 400 seconds. Sparse thermal records conservatively replay only 0 and 400.

The reviewer also identified an unsupported direct-domain input: mixed naive
and timezone-aware timestamps could partially mutate COP history before a
`TypeError`. Production Recorder timestamps already normalize to UTC. The
domain now rejects inconsistent timestamp awareness with `ValueError` before
changing COP or timing buffers. Four regression cases verify atomic rejection
with and without existing history.

The follow-up targeted suite passes **45 tests**. A complete suite and focused
independent re-review are run again after these changes.

The next review found a related edge case: an outlet-only observation with an
incompatible delta-T was ignored and preserved two earlier stable readings.
An actual change-only Recorder history then accepted a sample at 120 seconds
instead of the live 130 seconds. The domain now lets incomplete observations
invalidate stability while reserving positive stability increments for fresh
complete thermal observations. The regression
`test_partial_temperature_record_invalidates_recovery` failed before that fix
and passes after it. The defrost/replay suite passes **29 tests**.

A later independent review found that Recorder replay grouped events by exact
timestamp. Home Assistant stamps each entity's state when that entity writes it,
so the inlet and outlet readings of one poll land microseconds apart and never
share a timestamp. Replay therefore never saw a complete thermal observation,
recovery after defrost always waited for its 300-second timeout, and samples
could be admitted on a partially applied poll. The fixtures hid this by giving
every entity of a poll the same timestamp.

Replay now groups events into poll windows: events within 0.5 seconds of a
window's first event belong to the same poll (below the 1-second shortest scan
interval, far above the write skew between entities). The parity fixtures stamp
each entity write a few microseconds apart, as Home Assistant does; ten of the
fifteen parity tests failed with exact-timestamp grouping and pass with poll
windows. `test_poll_windows_merge_one_poll_and_split_consecutive_polls` pins the
window boundary. The complete suite passes **906 tests**.

### Final local result and review verdict

After the recovery and timestamp corrections, the complete suite passes
**905 tests in 28.59 seconds**. Ruff lint/format, domain type checking and
whitespace validation pass. Default gateway metadata is also centralized in the
API registry; historical migrations remain unchanged.

The independent Astra reviewer returned **APPROVE** after reproducing the
130-second recovery, confirming that meter events cannot prove stability and
that timeout and resumed-defrost handling still work. The reviewer also
confirmed the atomic rejection of incompatible timestamps and approved the
final registry-default cleanup. No unresolved review finding remains.

## Pull request and hosted verification

Pull request: [#480, enforce API and domain architecture boundaries](https://github.com/alepee/hass-hitachi_yutaki/pull/480).

The implementation commit is `92dabe0`. The repository workflows validate
HA 2025.1.0/Python 3.13 and the locked current HA on Python 3.13 and 3.14,
plus Ruff/translation lint, domain type checking, HACS and hassfest.
The [PR checks](https://github.com/alepee/hass-hitachi_yutaki/pull/480/checks)
provide the authoritative run results for the latest head, including any
documentation-only update that records this reference.
