# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Config flow: a second unit on the same HC-A(16/64)MB gateway was wrongly rejected as "already configured" when it shared the same model as an existing unit. The hardware identifier read for the `unique_id` (input registers 0-2) is gateway-wide, so every unit on one gateway produced the same `unique_id`; two identical models therefore collided (two different models only avoided it by coincidence). The `unique_id` is now suffixed with the per-unit H-LINK address (`unit_id`) on both the hardware-id and IP-fallback paths, so physically distinct units — even of the same model — no longer collide. Existing config entries keep their stored `unique_id` and are unaffected. Upgrade note: entries created before this version keep the old (unsuffixed) `unique_id`, so the duplicate guard will not recognise them if you *re-add the same already-configured unit* through the setup flow without removing the old entry first — remove the old entry first, or delete the resulting duplicate. New and re-created entries are fully deduplicated (#370).
- HC-A(8/16/64)MB: read each unit's outdoor-unit registers (Primary Compressor discharge `Td`, evaporator `Te`, current, frequency and outdoor expansion valve `EVO`) from the correct refrigerant-cycle block. The outdoor block is keyed on the **outdoor refrigerant cycle** (`30000 + Cycle × 100 + offset`, datasheet PMML0351 rev.6 §5.2.3), but the map read it at a fixed base `30000`, so on a gateway hosting several independent systems every unit reported cycle-0's compressor data. The cycle is arbitrary and is **not** the `unit_id` (on the reporter's hardware units 0/1/2 map to cycles 0/5/7), so it is now detected from the gateway unit table (input register `200 + unit_id × 4 + 1`, `0xFF` meaning "no unit"), persisted at config time under `outdoor_cycle`, and used to address the outdoor block. Existing installations self-heal on the next setup: the cycle is detected from the gateway and stored automatically, with no need to re-add the unit. When the cycle cannot be read the map falls back to cycle 0, preserving the previous behaviour (#353).

## [2.1.6] - 2026-07-21

### Added
- ATW-MBS-02 (Before Line-up 2016): ECO mode support. Unlike the 2016+ line-up where ECO is controlled per circuit, pre-2016 units expose a single global "Space mode" toggle (address 1027, read/write on the same address) and a single global ECO offset (STATUS 1090 / CONTROL 1030, range 1~10) shared by all circuits. They surface as a new ECO Mode switch and Eco Offset number on the Control Unit device, created only when the active register map defines these registers (#253).

### Fixed
- CI/tooling: raised `requires-python` from `>=3.13` to `>=3.13.2`, which collapses a stale `uv.lock` resolution fork. Because `>=3.13` allowed 3.13.0/3.13.1, the resolver forked to an ancient `homeassistant 2024.1.5` (which we never support -- our floor is 2025.1.0) that pinned `orjson==3.9.9`; that sdist fails to build under recent `uv`, so any lockfile-regenerating dependency PR broke on the lint/test jobs. The lock is now single-version.
- Yutampo R32: stop creating entities for hardware a DHW-only unit does not have. The ATW-MBS-02 gateway reports a constant `0` (not a sentinel) for the space-heating water circuit (`water_inlet/outlet/2/3/target_temp`, `water_flow`, `pump_speed`, pump 1/2/3), the heating thermal meters (`thermal_power_heating`, `thermal_energy_heating_daily/total`) and the extended compressor sensors (gas `Tg` / liquid `Ti` temperatures, indoor/outdoor expansion valve openings), so those readings could not be filtered by value and surfaced as permanently `unavailable`/`0` entities. These are now gated on two new profile capabilities — `supports_water_circuit` and `supports_extended_compressor_sensors` — both `False` for the Yutampo R32 (confirmed against the anonymized telemetry fleet). The core compressor sensors (frequency, current, discharge `Td`, evaporator `Te`) and the DHW entities are unaffected (#365).
- Compressor timing: `Compressor rest time` (and run/cycle time) could report a negative value. When Recorder-replayed states (local wall-clock) interleaved with live `datetime.now()` readings across a clock/DST shift, an off→on transition could compute a negative duration and average it in. Negative durations are now discarded while the state transition is still recorded (#365).

### Changed
- Yutampo R32 upgrade note (release note action required): existing Yutampo installations already have the now-removed water-circuit and extended-compressor entities registered. Home Assistant does not delete them automatically, so after upgrading they linger in the entity registry as restored `unavailable` entries. Affected users should delete them manually (Settings > Devices & Services > the entity > Delete) to clear dead references in dashboards, the Energy configuration and automations. New installations are unaffected (#365).
- CI/tooling: Dependabot now ignores `zeroconf`, a transitive dependency pinned exactly by Home Assistant (`==0.148.0`); bumping it independently forces the resolver to backtrack HA and can never merge.
- Docs: refreshed the HC-A(8/16/64)MB datasheet to the official PMML0351 rev.6 (04/2026) and corrected the outdoor-unit register addressing in `docs/gateway/hc-a-mb.md`. The outdoor block is keyed on the **outdoor unit refrigerant cycle** (`30000 + (Cycle × 100) + offset`), not the indoor `Modbus_Id` — the previous `5000 + (Modbus_Id × 200)` formula was wrong (groundwork for #353).

## [2.1.5] - 2026-06-30

### Added
- Logging: the gateway now logs an explicit recovery line (with the real not-ready duration) when its `system_state` transitions back from initializing/desynchronized to synchronized. Previously the recovery was silent in the Modbus layer, so the full outage window (and its true length) was not visible in the logs; only the "not ready" detection and the periodic "still not ready" reminders were. This makes it possible to measure the actual desync windows directly from Home Assistant's logs (#356).

## [2.1.4] - 2026-06-03

### Added
- Telemetry backend: `backend/grafana/koppen-zones.geojson`, a simplified Köppen-Geiger climate-zone polygon set (29 classes, polar `EF`/`ET` excluded, keyed by `CODE`/`name`) for a climate-zone choropleth panel on the fleet-inventory Grafana dashboard. Active zones are painted with their canonical Köppen family colours (the install count shows in the tooltip and as a per-zone label); zones with no installs stay a neutral, theme-aware grey. Provenance and the `mapshaper` regeneration command are documented in the dashboard design doc.

### Fixed
- COP: fix electrical power double-counting on S80 units when a whole-unit power meter (`power_entity`) is configured. The derived-metrics calculator was called once per compressor and the results summed; with a power meter each call returns the *total* unit power, so the sum was ~2x the real consumption and COP was roughly halved. Electrical power is now computed with a single calculator call using the summed compressor current, which is correct for both the measured-power path (whole unit returned once) and the I×U estimate (`U×(I1+I2) == U×I1 + U×I2`) (#316).
- COP: fix incorrect COP reconstruction on restart for installations using a whole-unit power meter. During Recorder rehydration every replayed point was stamped with a single live `power_entity` reading captured at startup, instead of each point's own historical value. Rehydration now fetches the historical `power_entity` (and `voltage_entity`) from the Recorder and reconstructs the electrical power per point at its own timestamp (falling back to the per-point I×U estimate when no power meter is configured), matching how historical water temperatures are already replayed (#316).
- Setup: when the first refresh is tolerated through `gateway_not_ready` (#303/#307), the gateway's live `system_config` is unavailable (register data is empty), so live capability flags all read `False`. Setup now keeps using the persisted `system_config` (#308) in that case instead of the empty live data. This fixes two regressions: (1) COP services seeded from the persisted capabilities are no longer destroyed by a spurious live-vs-persisted mismatch re-init, and (2) DHW, Pool and Circuit 1/2 devices are now registered from the persisted capabilities instead of silently disappearing until a later reload hits a successful poll. When the first refresh succeeds, live capabilities remain authoritative and behaviour is unchanged (#317).
- ATW-MBS-02 (Before Line-up 2016): the "Room Thermostat available" flag is a single global register (address 1029), not a per-circuit control as on the 2016 line-up. The pre-2016 map previously defined `circuit2_thermostat` at the same address 1029 as `circuit1_thermostat`, so toggling circuit 2 silently rewrote the global flag (and shadowed circuit 1). The duplicate `circuit2_thermostat` key has been removed; the flag is now modelled once as `circuit1_thermostat` (#318).
- COP: the measurement-interval timer was advanced before sensor inputs were validated. A transient `None` on water inlet/outlet temperature, water flow or compressor current advanced the timer then returned early, so the next complete poll arriving within the measurement interval was rejected by the interval gate. This dropped valid measurements and degraded COP accuracy/quality. The timer now advances only after a complete, valid measurement is attempted (#319).
- Sensors that report a `0xFFFF` sensor-error (e.g. outdoor, water inlet/target temperatures, water flow, compressor temperatures/pressures) now correctly become unavailable instead of retaining their last good value forever. Previously, a register that went to `0xFFFF` with no configured fallback deserialized to `None` and was silently kept in the data cache; the entity kept reporting a frozen reading. A post-deserialization `None` (after any fallback attempt) now clears the stored value, consistent with the existing sentinel-filtered handling (#320).
- Climate: the HVAC action (heating/cooling indicator on the thermostat card) now resolves correctly when the unit operating mode is `auto`. Previously the card showed "unknown" while the heat pump was actively running, because only explicit `heat`/`cool` modes were mapped. The running direction is now derived from the STATUS `operation_state` register (`heat_thermo_on`/`cool_thermo_on`); `off`/`defrosting`/`idle` behaviour is unchanged (#321).
- Switch entities: a failed Modbus write no longer leaves the UI showing the wrong state. The base switch now honours the boolean success flag returned by `set_fn`: on failure it logs a warning and requests a refresh so the entity reverts to the real device state, instead of unconditionally applying an optimistic value. Toggling a switch before the first successful poll (`coordinator.data` is `None`) no longer raises `TypeError`, since state is re-synced via `async_request_refresh()` rather than a subscript-assign into `coordinator.data` (#322).
- Options flow: allow clearing a previously-configured optional external sensor (voltage, power, energy, water inlet/outlet temperature, electricity price). Clearing a selector left the field omitted from the submitted input, and the schema's `default=` re-applied the old value, so a configured sensor could never be unset. The sensors step now pre-fills via `suggested_value` and cleared optional sensor keys are reconciled out of the merged entry data (#323).
- Telemetry backend (Cloudflare Worker): a transient R2 outage no longer consumes the per-instance rate-limit slot. The Worker now performs a read-only rate-limit check before archiving and only commits the 60s marker *after* a successful R2 write. Previously, the marker was set before archiving, so when R2 returned a 502 the client's retry within the next minute was rejected with 429, turning a recoverable outage into guaranteed telemetry loss for that `(instance_hash, type)`. Deploy with `cd backend/worker && npx wrangler deploy` (#324).
- Reconfigure flow: the gateway variant selector now defaults to the variant already stored in the config entry when auto-detection fails, instead of resetting to no selection and forcing the user to re-pick it (#325).

## [2.1.3] - 2026-05-29

### Fixed
- Options/reconfigure flow: fill missing translations in `translations/en.json`, `translations/fr.json`, `translations/nl.json` and `translations/ro.json` so the connection step shows translated error messages and field labels (`name`, `scan_interval`) instead of raw keys like `gateway_not_ready`. Both ATW-MBS-02 and HC-A(16/64)MB connection steps now mirror the initial setup flow (#302).
- Setup: tolerate a transient `gateway_not_ready` (Modbus TCP up, H-LINK still initializing after a gateway power-cycle) during entry setup/reload. Previously a duplicate `async_config_entry_first_refresh()` call re-raised `ConfigEntryNotReady` and produced a "Setup failed, will retry" banner even though the gateway was simply in its H-LINK initialization window. Setup now completes; entities are `unavailable` until the next successful poll. Genuine connection failures (TCP unreachable, other Modbus errors) still raise `ConfigEntryNotReady` so HA's standard retry mechanism applies (#303).

### Changed
- Config flow: preserve user-typed values (host, port, slave, name, scan interval, gateway variant) when a provider step fails validation (`cannot_connect`, `gateway_not_ready`, `invalid_slave`, ...). Applies to both initial setup and reconfigure/options flows, for ATW-MBS-02 and HC-A(16/64)MB providers. Previously, fields were reset to defaults on every retry (#304).
- Persist the gateway `system_config` (capability bitfield) in the config entry data on every successful refresh. At setup time, COP services for cooling, DHW and pool are now initialised from this persisted value *before* the first refresh, so they survive a reload that hits `gateway_not_ready` during the gateway's H-LINK init window. Existing installations get the value populated on their next successful poll; until then the previous (post-refresh) behaviour applies as a fallback (#308).

## [2.1.2] - 2026-05-28

### Fixed
- Config flow: surface a clear `gateway_not_ready` error (with H-LINK troubleshooting hints) instead of crashing with `TypeError` when the gateway reports an unhealthy `system_state` (initializing or desynchronized) during integration setup. Affects both ATW-MBS-02 and HC-A(16/64)MB providers. Regression introduced in 2.1.0-beta.2 (#260): the new short-circuit in `read_values` was not propagated to the config providers (#300, #301).

### Changed
- `ReadResult` enum and `read_values` now document the contract explicitly: callers MUST check the return value before consuming `read_value()` output, since `GATEWAY_NOT_READY` short-circuits before populating internal data.
- `decode_config` defensively coerces a missing/None `system_config` to `0` instead of raising, so an upstream contract violation degrades to "no modules detected" rather than crashing.

## [2.1.1] - 2026-05-25

### Added
- Telemetry backend: fleet-inventory dashboard. The Worker now mirrors each `installation` payload into Cloudflare Workers Analytics Engine (dataset `hitachi_installations`), feeding a Grafana dashboard that shows active integration/HA versions, heat-pump profiles, gateway types, and configuration flags (cooling, DHW, pool, S80, circuits, power supply) plus per-installation drill-down by anonymous hash. R2 remains the single permanent archive. The integration re-sends the (anonymous) installation payload once per day so the dashboard's 90-day window reflects the active fleet.

### Changed
- Telemetry backend: Cloudflare R2 is now the single source of truth. The Worker no longer dual-writes to TimescaleDB / TigerData; the `pg` driver, `db.ts` module, and Hyperdrive binding have been removed. R2 partitioning (`metrics/year=YYYY/month=MM/day=DD/`) is unchanged. Notebooks should consume the JSON archive directly via DuckDB + httpfs.
- Dev tooling: bump `ruff` from 0.15.11 to 0.15.14 (#287, #294, #297)

### Fixed
- ATW-MBS-02: read R/W registers from STATUS addresses instead of CONTROL. The CONTROL range only reflects what was last commanded; STATUS reflects what the unit is actually using. This fixes silent divergences when the unit internally overrides a setpoint (anti-legionella cycle, OTC adjustment, central-control conflict). Affects both Line-up 2016 (29 keys) and Before Line-up 2016 (19 keys) maps. Writes still target CONTROL via the existing `write_address` mechanism, mirroring the HC-A(16/64)MB pattern. Likely root cause of the DHW reference temperature jumping reported in #293 (#295)
- Telemetry backend: parallelize TigerData and R2 writes via `Promise.allSettled` so that an R2 archive is performed even when the TigerData insert fails. Previously the R2 archive was only attempted after a successful database write, which meant payloads received during a TigerData outage were lost. The endpoint now returns `202` when at least one sink succeeds, and `502 Bad Gateway` only when both upstream sinks fail (#284)

## [2.1.0] - 2026-04-24

This release adds support for pre-2016 ATW-MBS-02 gateways (Gen 1 Yutaki S/S Combi), an opt-in anonymous telemetry system to grow realistic test fixtures across all heat pump models, and an electricity cost estimation feature. Internally, derived metrics (COP, thermal/electrical power, compressor timing) are now centralized in a single adapter, fixing COP accuracy for S80 cascade installations.

### Added
- Support for Before Line-up 2016 ATW-MBS-02 gateway — Gen 1 Yutaki S and S Combi units with full read/write support (#248)
- Gateway variant system — config flow asks for hardware generation with auto-detection after connection
- Interactive model decoder tool to identify hardware generation (`docs/tools/model-decoder.html`)
- Scanner auto-detection and annotation for before-2016 units
- Model nomenclature reference documentation (`docs/reference/model-nomenclature.md`)
- Config entry migration v2.4 — adds `gateway_variant` field to existing entries
- Anonymous telemetry system (Off / On) — helps build realistic test fixtures for all heat pump models ([Discussion #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200))
- Telemetry consent step in config flow (options) and repair flow for existing users
- Telemetry diagnostic sensor (`sensor.telemetry_status`) with send tracking attributes
- Backend: Cloudflare Worker (ingestion proxy), TigerData migrations, R2 cold archive
- DHW demand mode diagnostic sensor (standard/high demand) read from STATUS register — disabled by default (#255)
- Electricity cost estimation sensor — configure an electricity price entity to track cumulative energy costs (#273)
- Repair flow to onboard existing users to the electricity cost feature (#273)
- `electrical_power` sensor (kW) derived from external power entity or Modbus register (#273)
- Currency-aware descriptions in config/options/repair flows using `{currency}` placeholder (#273)

### Changed
- Refactor config flow to provider-based orchestrator — each gateway declares its own configuration steps via `GatewayConfigProvider` protocol, eliminating all gateway-specific conditionals from `config_flow.py`
- **DerivedMetricsAdapter** — COP, thermal power, electrical power, and compressor timing are now computed centrally in `adapters/derived_metrics.py` before entities and telemetry consume the data. COP now uses the external power entity when configured.
- **Dict-based telemetry** — `MetricPoint` dataclass (60+ fields) replaced with plain dicts. Adding a new data key to telemetry requires zero code changes. Client-side daily stats aggregation removed (server-side TimescaleDB continuous aggregate is the source of truth).
- Entities COP, thermal, and timing simplified from complex subclasses (~590 lines) to simple `value_fn` readers
- `power_consumption` sensor now reads from `DerivedMetricsAdapter` like all other derived sensors (#273)
- Entity recategorization: sensors vs diagnostic (#273)
- Reorganize gateway tests to mirror source structure (`tests/api/modbus/`)
- Grafana dashboard queries migrated to JSONB with `time_bucket` sampling for performance

### Fixed
- Cooling OTC compensation method showing "Unknown" and not settable on ATW-MBS-02 (#239)
- Entities depending on missing registers (eco mode, DHW boost/high demand) are now hidden automatically on gateways that lack them
- Gateway sync state sensor showing raw integer instead of translated string during initializing/desynchronized states (#254)
- Entities remaining "available" with stale data when gateway is stuck in initializing state (#254)
- Log spam reduced from ~685 identical warnings to periodic reminders every 5 minutes during extended gateway sync issues (#254)
- Adaptive polling backoff (5s → 10s → ... → 300s max) when gateway is not ready, reducing unnecessary Modbus traffic (#254)
- COP telemetry was wrong for S80 cascade (8.2 avg vs 1.32 in HA) — now uses same calculation path as HA entities
- Gateway sentinel filtering — Modbus sentinel values (-127, -67) for absent sensors are now filtered at the gateway layer instead of propagating to entities and telemetry (#272)
- Module gating — unconfigured modules (DHW, pool, circuit 2) no longer leak default register values into data and telemetry (#272)
- Remove hardcoded `-127` checks from hydraulic entity conditions (#272)
- Restore accumulated electricity cost on restart (#273)

### Removed
- `MetricPoint`, `DailyStats` dataclasses and client-side aggregator
- `HitachiYutakiCOPSensor`, `HitachiYutakiThermalSensor`, `HitachiYutakiTimingSensor` subclasses
- `power_consumption` sensor `source` attribute — energy source selection is now internal to the adapter (#273)

## [2.0.2] - 2026-03-09

### Fixed
- Remove incorrect tenths conversion on pool target temperature (#233)
- Remove phantom secondary compressor pressure registers at non-existent addresses 1150/1151 (#225)
- Scan interval not editable in reconfiguration flow (options flow missing the field)

### Changed
- Migrated runtime data storage from `hass.data[DOMAIN]` to `ConfigEntry.runtime_data` (modern HA pattern)
- Restructured documentation: unified `docs/` directory, all English, centralized architecture docs
- Slimmed `CLAUDE.md` to rules and conventions only (details moved to `docs/`)
- Slimmed `CONTRIBUTING.md` with pointers to `docs/development/`

### Added
- Water Outlet 2 (Two2) and Water Outlet 3 (Two3) temperature sensors for systems with buffer tanks (#161)
- Local brand assets for HA 2026.3+ brand proxy API
- Base entity module (`entity.py`) for common-modules quality standard
- Documentation for `set_room_temperature` service action
- Quality scale tracking file (`quality_scale.yaml`) for Bronze tier
- Config flow test suite: 12 tests covering user, gateway_config, profile, power, validation, options flow
- `docs/architecture.md`: unified architecture reference (merged 5 sources)
- `docs/development/`: getting started, adding entities, Modbus registers, profiles guides
- `docs/reference/`: entity patterns, domain services, quality scale references
- GitHub issue templates (bug report, feature request) and PR template
- MIT LICENSE file
- CI: test against Python 3.13 and 3.14

### Removed
- `documentation/` directory (content migrated to `docs/`)
- In-code READMEs (`domain/`, `adapters/`, `entities/`) absorbed into `docs/`
- Root `TODO-hc-a-mb-registers.md` (content in gateway docs)

## [2.0.1] - 2026-02-23

### Added
- `CONTRIBUTING.md` with contributor workflow documentation

### Changed
- Config flow: removed unused `dev_mode` option from advanced settings
- Config flow: moved Modbus Device ID from advanced step to gateway configuration step
- Config flow: namespaced Modbus connection keys with `modbus_` prefix (`modbus_host`, `modbus_port`, `modbus_device_id`) to prepare for future non-Modbus gateway support
- Automatic config entry migration (v2.1 → v2.2) renames stored connection keys for existing installations
- Dev tooling: bump `ruff` from 0.13.3 to 0.15.2

### Fixed
- HC-A(16/64)MB outdoor compressor registers mapped to wrong address block (5000+offset instead of 30000+offset), causing discharge temp, evaporator temp, current, frequency, and EVO opening to show as unavailable ([#96](https://github.com/alepee/hass-hitachi_yutaki/issues/96))
- DHW/pool COP calculation used circuit outlet register (1094) instead of HP-level outlet register (1201) — when the 3-way valve redirects to the tank, the circuit register becomes stale, causing zero thermal power and no COP during DHW runs ([#205](https://github.com/alepee/hass-hitachi_yutaki/issues/205))
- Electrical power unit conversion now uses HA's `PowerConverter` instead of a naive `> 50` heuristic ([#182](https://github.com/alepee/hass-hitachi_yutaki/issues/182)) — a heat pump in standby consuming < 50 W was incorrectly interpreted as kW, causing wildly inaccurate COP values
- Dutch (nl) translations updated

## [2.0.0] - 2026-02-12

A major rewrite of the integration with hexagonal architecture, multi-gateway support, and significantly improved accuracy for thermal and COP calculations.

### Highlights

- **Multi-gateway support**: HC-A(16/64)MB alongside ATW-MBS-02
- **Hexagonal architecture**: pure domain layer, testable without Home Assistant
- **Accurate thermal energy**: separate heating/cooling tracking, defrost filtering
- **Seamless migration**: automatic entity migration from v1.9.x with preserved history

### Added
- **HC-A(16/64)MB gateway support** — New Modbus gateway type alongside ATW-MBS-02. Both HC-A16MB and HC-A64MB are protocol-identical (same registers, same features — only the capacity differs: 16 vs 64 indoor units). Introduces a register abstraction layer (`HitachiRegisterMap` ABC) enabling polymorphic gateway support with separate read/write address ranges, unit_id-based address computation, and gateway-specific deserialization
- **Outdoor unit registers for HC-A(16/64)MB gateway** ([#96](https://github.com/alepee/hass-hitachi_yutaki/issues/96)) — Compressor frequency, current, discharge/liquid/gas/evaporator temperatures, and expansion valve openings now available on HC-A-MB gateways
- **New heat pump profiles** — YCC and Yutaki SC Lite profiles for models only available via HC-A(16/64)MB gateway
- **External energy sensor (`energy_entity`)** — New optional configuration to replace the Modbus power consumption register with an external lifetime energy sensor (`device_class=energy`, kWh, `TOTAL_INCREASING`). The `power_consumption` entity exposes a `source` attribute for transparency
- **`set_room_temperature` service** — New entity platform service to write measured room temperature to the heat pump via climate entities, enabling automations when the Modbus thermostat is enabled
- **Operation state numeric attribute** ([#187](https://github.com/alepee/hass-hitachi_yutaki/issues/187)) — Raw Modbus numeric value (0-11) exposed as a `code` attribute for simpler automation logic
- **Conditional circuit climate modes** ([#186](https://github.com/alepee/hass-hitachi_yutaki/issues/186)) — Two-circuit setups expose only `off`/`heat_cool` (power toggle); single-circuit retains full `heat`/`cool`/`auto`/`off` control
- **Complete hexagonal architecture** — Domain layer with pure business logic (zero HA dependencies), adapters layer bridging domain with Home Assistant, 100% testable domain layer
- **Domain-driven entity organization** — Business domain structure (circuit, compressor, control_unit, dhw, gateway, hydraulic, performance, pool, power, thermal) with builder pattern for all entity types
- **Robust Modbus connection recovery** — Exponential backoff retry logic with automatic reconnection on network interruptions ([#118](https://github.com/alepee/hass-hitachi_yutaki/issues/118))
- **Enhanced heat pump profile system** — Explicit hardware capabilities per model (`dhw_min_temp`, `dhw_max_temp`, `max_circuits`, `supports_cooling`, `max_water_outlet_temp`, `supports_high_temperature`)
- **Smart profile auto-detection** — Decentralized detection logic with improved Yutampo R32 and S Combi detection
- **Recorder-based data rehydration** — COP and compressor timing sensors automatically reconstruct history from HA Recorder on startup, eliminating data loss after restarts
- **Separate thermal energy sensors for heating and cooling**:
  - `thermal_power_heating` / `thermal_power_cooling`: Real-time power output
  - `thermal_energy_heating_daily` / `thermal_energy_cooling_daily`: Daily energy (resets at midnight)
  - `thermal_energy_heating_total` / `thermal_energy_cooling_total`: Total cumulative energy
- **Post-cycle thermal inertia tracking** — Thermal energy from system inertia correctly counted after compressor stops
- **Automatic entity migration** — Seamless upgrade from v1.9.x to 2.0.0 with preserved entity history and IDs
- **Functional repair flow** — Dedicated `repairs.py` for 1.9.x → 2.0.0 migration with automatic integration reload
- **Hardware-based unique_id** ([#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)) — Config entries use gateway hardware identifier (Modbus Input Registers 0-2) instead of IP+slave, preventing duplicates and surviving DHCP changes
- **Annotated Modbus register scanner** — New `scripts/scan_gateway.py` tool with `make scan` target for diagnosing register values across all gateway types, with human-readable annotations and scan reference documentation

### Changed
- **Minimum Home Assistant version** raised to 2025.1.0 to align with `WaterHeaterEntityDescription` component signature
- **Minimum Python version** raised to 3.13
- **CI tests against min and latest HA versions** via matrix (HA 2025.1.0 and latest)
- **Complete platform refactoring** to domain-driven architecture — all platform files act as pure orchestrators
- **Entity organization** moved from technical grouping to business domain grouping
- **Modbus register organization** by logical device for improved clarity
- **Alarm sensor** displays descriptions as state with numeric codes as attributes
- **Storage strategy** — COP and compressor data relies on HA Recorder instead of custom storage
- **Thermal service** split into modular package: `calculators.py`, `accumulator.py`, `service.py`, `constants.py`
- **Thermal energy classification uses operation mode** ([#196](https://github.com/alepee/hass-hitachi_yutaki/discussions/196)) — DHW and pool cycles now force heating classification regardless of ΔT sign, preventing transient negative deltas from being incorrectly counted as cooling energy
- **Sensor subclasses extracted into dedicated package** — `entities/base/sensor.py` split into `entities/base/sensor/` package with specialized subclasses (COP, thermal, timing) for better maintainability
- **Register map factory** extracted into `api/__init__.py`, eliminating duplication
- **⚠️ BREAKING: Thermal energy calculation logic** ([#123](https://github.com/alepee/hass-hitachi_yutaki/issues/123)):
  - Correctly separates heating (ΔT > 0) from cooling (ΔT < 0)
  - Defrost cycles are now filtered (not counted as energy production)
  - Post-cycle lock mechanism prevents counting noise after compressor stops
  - Results in accurate COP calculations (previously inflated by defrost)

### Deprecated
- **⚠️ Old thermal energy sensors** (disabled by default, still available for backward compatibility):
  - `thermal_power` → use `thermal_power_heating` instead
  - `daily_thermal_energy` → use `thermal_energy_heating_daily` instead
  - `total_thermal_energy` → use `thermal_energy_heating_total` instead
  - **Migration required**: Update your Energy Dashboard and automations to use the new sensors

### Removed
- Legacy technical modules and monolithic entity files in favor of domain-specific builders
- Direct entity instantiation replaced with builder pattern
- Legacy services directory
- Redundant climate number entities (target_temp, current_temp) — now handled by climate entity

### Fixed
- **Anti-legionella temperature range** ([#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)) — DHW anti-legionella target temperature now uses profile-based min/max instead of hardcoded values, respecting each model's actual capabilities
- **COP DHW identical to COP Heating** ([#191](https://github.com/alepee/hass-hitachi_yutaki/issues/191)) — COP sensors now use `operation_state` to differentiate heating, DHW, cooling, and pool cycles
- **Anti-legionella binary sensor** ([#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)) — Read from STATUS registers instead of CONTROL registers
- **Cooling capability detection** ([#177](https://github.com/alepee/hass-hitachi_yutaki/issues/177)) — Fixed system_config bitmask order regression from v1.9.x
- **OTC cooling serialization for HC-A(16/64)MB** — Correct mapping (Disabled=0, Points=1, Fix=2)
- **Recorder database access warning** — Use recorder executor for database operations
- **Pressure sensor error handling** — `0xFFFF` sentinel check in both gateway register maps
- **Config flow translations** — Added missing translations for gateway/profile selection (EN and FR)
- **Profile detection robustness** — Yutampo R32 `detect()` no longer returns `None` when `has_dhw` is missing
- **Temperature deserialization** — Properly differentiates between tenths and signed 16-bit values
- **Sensor reading accuracy** for secondary compressor current and pressure sensors
- **Unit power switch** "Unknown" state due to inconsistent condition checks
- **COP measurement period** — Fixed negative time span values
- **Legacy entities** — Automatic migration with preserved history

## [1.9.3] - 2025-10-06

### Fixed
- Fixed aberrant COP (Coefficient of Performance) values by implementing comprehensive data validation and intelligent unit detection for power sensors
- Added robust validation for all input parameters: temperature ranges (-10°C to 80°C), water flow rates (0.1 to 10.0 m³/h), temperature differences (0.5 to 30 K), power ranges (0.1 to 50.0 kW thermal, 0.1 to 20.0 kW electrical), and final COP values (0.5 to 8.0)
- Implemented automatic power unit detection (W vs kW) using `unit_of_measurement` attribute with intelligent fallback detection based on value ranges
- Added validation for energy accumulation to prevent calculation errors in COP measurements
- Enhanced debug logging for unit detection, validation failures, and COP calculations

### Changed
- Improved COP calculation accuracy by rejecting invalid data instead of producing incorrect values
- Enhanced support for external power and voltage sensors with automatic unit detection
- Updated power unit handling to seamlessly support both W and kW sensors
- Options flow: avoid providing `default=None` to entity selectors to prevent the UI error "Entity None is neither a valid entity ID nor a valid UUID" when opening Options. ([#109](https://github.com/alepee/hass-hitachi_yutaki/issues/109))
- Options flow: stop storing the `config_entry` on the options flow instance to comply with Home Assistant deprecation and silence the warning that will become an error in 2025.12. ([#109](https://github.com/alepee/hass-hitachi_yutaki/issues/109))
 - CI: update GitHub Actions `actions/setup-python` to v6
 - Dev tooling: bump `ruff` to 0.13.3

## [1.9.2] - 2025-09-05

### Fixed
- Fixed pymodbus compatibility issue with Home Assistant 2025.9.0+ by implementing automatic version detection for the device/slave parameter. The integration now works with both pymodbus < 3.10.0 (using `slave` parameter) and pymodbus >= 3.10.0 (using `device_id` parameter), ensuring compatibility across all Home Assistant versions. ([#97](https://github.com/alepee/hass-hitachi_yutaki/issues/97))

## [1.9.1] - 2025-07-22

### Changed
- Improved error handling in the data update coordinator to consistently create a repair issue in Home Assistant for any Modbus or network communication error.

### Fixed
- Resolved an issue where a loss of IP connectivity to the Modbus gateway could cause the integration to crash or behave unexpectedly. The integration now correctly handles network errors (`OSError`), ensuring that all entities become `unavailable` and properly recover once the connection is restored. ([#76](https://github.com/alepee/hass-hitachi_yutaki/issues/76))

## [1.9.0] - 2025-07-07

### Added
- New sensor to monitor the gateway's synchronization state (`Synchronized`, `Desynchronized`, `Initializing`).
- Pre-flight check during setup and updates to verify gateway synchronization status. This creates a persistent notification ("Repair") if the gateway is desynchronized, guiding the user to resolve the issue.

### Changed
- Improved startup resilience. The integration now caches the heat pump's configuration during the first successful setup. This ensures that all devices and entities are registered during subsequent Home Assistant startups, even if the heat pump is temporarily offline.

### Fixed
- Resolved a critical issue where all integration entities would disappear if the heat pump was offline when Home Assistant started. Entities will now appear as `unavailable` until the connection is restored.

## [1.8.2] - 2025-06-26

### Fixed
- Corrected the HACS installation link in `README.md` to ensure it redirects correctly.

### Changed
- Updated development dependencies, including `ruff` to v0.12.0.

## [1.8.1] - 2025-05-12

### Added
- New "Anti-legionella Cycle" button entity to manually start a high temperature anti-legionella treatment cycle.
- New binary sensor entity (`antilegionella_cycle`) indicating if an anti-legionella cycle is currently running.

### Changed
- Removed unused or redundant Domestic Hot Water (DHW) entities: DHW current temperature sensor, DHW target temperature number, DHW power switch, high demand switch, and periodic anti-legionella switch.
- Improved English and French translations for new entities and advanced configuration (water inlet/outlet temperature entities).

## [1.8.0] - 2025-05-11

### Changed
- The integration now allows configuration with central control modes Air (1), Water (2), or Total (3). Only Local (0) is forbidden.
- Error messages and documentation updated to reflect this change.
- The documentation now recommends using Air (1) mode for most installations.
- Support for Hitachi Yutampo R32 machines (requires 'Total' (3) mode).
- Bump ruff from 0.11.2 to 0.11.8 ([#50](https://github.com/alepee/hass-hitachi_yutaki/pull/50))
- Updated development dependencies and minor fixes.

## [1.7.1] - 2025-03-27

### Changed
- Replaced standard DHW preset with heat pump mode
- Migrated from Pylint to Ruff for code linting
- Updated development dependencies (Ruff to 0.11.2, pre-commit to 4.2.0)

### Added
- Added ffmpeg dependency to development environment

## [1.7.0] - 2025-03-19

### Added
- Implemented WaterHeaterEntity for Domestic Hot Water (DHW) control
- Better integration with Home Assistant UI for water heater controls
- Support for standard operation modes: off, standard, and high demand

## [1.6.1] - 2025-03-10

### Fixed
- Fixed issue with multiple heat pumps not generating unique entity IDs
- Added config entry ID to all entity unique IDs to ensure uniqueness across multiple instances

## [1.6.0] - 2025-02-06

### Added
- New thermal energy monitoring sensors:
  - Real-time thermal power output (kW)
  - Daily thermal energy production with midnight auto-reset (kWh)
  - Total cumulative thermal energy production (kWh)
- Detailed monitoring attributes:
  - Temperature differential and water flow tracking
  - Average power calculation over measurement periods
  - Precise measurement timing with compressor state tracking
- Full translations for all new features in French and English

## [1.5.2] - 2025-01-16

### Changed
- Optimized default sensor visibility based on configuration and relevance for standard users

## [1.5.1] - 2025-01-16

### Fixed
- Compatibility with latest pymodbus API

## [1.5.0] - 2025-01-16

### Added
- Improved logging for COP calculation and system state monitoring

### Changed
- Updated pymodbus dependency to match Home Assistant's version
- Optimized COP calculation parameters for better accuracy

## [1.5.0-b7] - 2025-01-12

### Added
- Added quality indicators for COP measurements (no_data, insufficient_data, preliminary, optimal)
- Added translations for COP quality indicators in French and English

### Fixed
- Fixed sample size and interval for more accurate COP calculation

## [1.5.0-b6] - 2025-01-06

### Fixed
- Fixed COP calculation by applying water flow conversion (raw value was used instead of m³/h)

## [1.5.0-b5] - 2025-01-03
### Fixed
- Fixed COP calculation by removing incorrect water flow division
- Added more detailed debug logging for thermal power calculation

## [1.5.0-b4] - 2025-01-02

### Added
- Added runtime and rest time sensors for both compressors
- Added detailed logging for power calculations
- Added debug information for thermal power calculation
- Added comprehensive logging for COP measurements and accumulation

### Changed
- Moved cycle time sensors to compressor devices for better organization
- Optimized COP calculation with more detailed debug information
- Simplified sensor code by moving value validation to conversion methods

### Fixed
- Fixed temperature conversion for special values (0xFFFF)
- Fixed water flow value scaling
- Fixed double conversion issue for temperature and pressure sensors
- Fixed connectivity sensor state calculation

### Added
- Added detailed logging for power calculations
- Added debug information for thermal power calculation
- Added comprehensive logging for COP measurements and accumulation

## [1.5.0-b3] - 2024-12-19

### Added
- Added external temperature entities configuration for more accurate COP calculations
- Added support for two COP calculation methods:
  - Moving median over 10 measurements when using external temperature sensors
  - Energy accumulation over 15 minutes when using internal sensors

### Changed
- Modified configuration flow to include temperature entity selection
- Improved COP calculation accuracy with external temperature sensors
- Refactored sensor code to reduce complexity and improve maintainability

### Documentation
- Updated configuration documentation with new temperature entity options
- Added explanation of COP calculation methods in the documentation

## [1.5.0-b2] - 2024-12-18

### Added
- Added power meter entity configuration option for more accurate COP calculations
- Added support for external power meter in sensor calculations

### Changed
- Modified configuration flow to include power meter entity selection
- Updated COP calculations to use power meter readings when available
- Enhanced power consumption accuracy with direct power meter readings

### Documentation
- Updated README with power meter configuration instructions
- Added power meter entity option in configuration documentation

## [1.5.0-b1] - 2024-12-14

### Added
- Added voltage entity configuration option for more accurate power calculations
- Introduced new configuration schemas for gateway, power supply and advanced settings
- Added support for custom voltage entity in sensor calculations

### Changed
- Modified configuration flow to include voltage entity selection
- Updated power consumption calculations to use voltage entity when available
- Enhanced system configuration flexibility with new voltage setup options

## [1.5.0-b0] - 2024-12-13

### Added
- New COP (Coefficient of Performance) sensor with real-time calculation
- Power supply type configuration (single-phase/three-phase)
- Enhanced power calculations for S80 models with dual compressor support

### Changed
- Improved power consumption calculations with smoothing algorithm
- Updated configuration options to include power supply type
- Enhanced accuracy of energy measurements

## [1.4.2] - 2024-12-11

### Changed
- Improved operation state sensor with more descriptive state values

## [1.4.1] - 2024-12-11

### Changed
- Downgraded pymodbus dependency to 3.6.9 to match Home Assistant's modbus integration

## [1.4.0] - 2024-12-11

### Added
- New diagnostic sensor "Operation State" showing detailed heat pump operation mode
- New diagnostic sensor "Compressor Cycle Time" measuring average time between compressor starts

### Changed
- Updated French and English translations for new sensors

## [1.3.4] - 2024-12-05

### Changed
- Removed unnecessary dependency to Home Assistant's modbus integration since we only use pymodbus library

## [1.3.3] - 2024-12-05

### Fixed
- Changed temperature conversion to use integers instead of floats as documented by Hitachi
- Fixed Pylint warnings by implementing missing abstract methods in ClimateEntity

## [1.3.2] - 2024-11-29

### Fixed
- Fixed unique_id generation in switch and number entities to prevent mismatched entities

## [1.3.1] - 2024-11-29

### Fixed
- Fixed register key double prefixing issue in switch and number entities causing some controls to fail

## [1.3.0] - 2024-11-29

### Removed
- Removed climate entity for DHW control in favor of more appropriate water heater entity type

## [1.2.0] - 2024-11-29

### Added
- Added new compressor diagnostic sensors:
  - Gas Temperature (TG)
  - Liquid Temperature (TI)
  - Discharge Temperature (TD)
  - Evaporator Temperature (TE)
  - Indoor Expansion Valve Opening (EVI)
  - Outdoor Expansion Valve Opening (EVO)

## [1.1.1] - 2024-11-29

### Fixed
- Fixed alarm code descriptions not loading

## [1.1.0] - 2024-11-28

### Added
- Added detailed error descriptions for all alarm codes
- Improved alarm code sensor to display both code and description

## [1.0.0] - 2024-11-05

### Added
- Initial release of the Hitachi Yutaki integration
- Basic configuration flow with connection validation
- Multi-language support (English and French)
- Automatic model detection and feature discovery
- Support for Yutaki S, S Combi, S80, and M models
- Climate control features:
  - Power control per circuit
  - Operation mode selection (Heat/Cool/Auto)
  - Target temperature adjustment
  - Comfort/Eco presets
  - Outdoor Temperature Compensation (OTC)
- DHW (Domestic Hot Water) control:
  - Power control
  - Target temperature adjustment
  - Boost mode
  - Anti-legionella function
  - High demand mode
- Pool heating control (if configured)
- Monitoring features:
  - Temperature sensors (outdoor, water inlet/outlet, circuits, DHW)
  - Component status (compressors, pumps, heaters)
  - Compressor frequencies and currents
  - Power consumption
  - Alarm codes
- Advanced configuration options:
  - Circuit-specific settings
  - Thermostat configuration
  - OTC calculation methods
  - ECO mode offsets
- Special features for S80 model:
  - Secondary compressor monitoring
  - R134a circuit sensors

### Changed
- N/A (Initial release)

### Deprecated
- N/A (Initial release)

### Removed
- N/A (Initial release)

### Fixed
- N/A (Initial release)

### Security
- Validation of Modbus connection parameters
- Proper error handling for Modbus communication
