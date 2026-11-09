# Home Assistant Quality Scale -- Assessment

**Date**: 2026-03-02
**Version**: 2.1.5
**Branch**: main
**Reference**: https://developers.home-assistant.io/docs/core/integration-quality-scale/

> **Note**: The Quality Scale is designed for core Home Assistant integrations.
> Custom integrations are classified as "Custom" and cannot be officially scored.
> This assessment serves as an internal quality reference.

---

## Overall result

| Tier | Score | Status |
|------|-------|--------|
| Bronze | 18/18 | Reached |
| Silver | 6/10 | Not reached |
| Gold | 9/21 | Not reached |
| Platinum | 1/3 | Not reached |

**Current level: Bronze** (all rules met)

---

## Bronze (18 rules)

### Rules met (18/18)

| Rule | Detail |
|------|--------|
| `config-flow` | Complete multi-step UI flow (4 steps) |
| `test-before-configure` | Modbus connection validated in the config flow |
| `test-before-setup` | `ConfigEntryNotReady` when the connection fails at startup |
| `unique-config-entry` | Hardware `unique_id` from Modbus input registers |
| `entity-unique-id` | Format `{entry_id}_{key}`, with an optional `{register_prefix}` segment (`{entry_id}_{register_prefix}_{key}`) |
| `has-entity-name` | `has_entity_name = True` on every base class except the switch (`HitachiYutakiSwitch`) |
| `entity-event-setup` | HA lifecycle followed through CoordinatorEntity |
| `dependency-transparency` | `requirements` declared in manifest.json |
| `common-modules` | Shared modules: `entities/base/`, `domain/services/`, `adapters/` |
| `action-setup` | Exempt: entity service `set_room_temperature` through `platform.async_register_entity_service` (no integration-level action) |
| `appropriate-polling` | DataUpdateCoordinator with a configurable interval |
| `docs-high-level-description` | Present in README.md |
| `docs-installation-instructions` | Present in README.md |
| `docs-actions` | Service documented in services.yaml |
| `brands` | Logo and icon in `brand/` |
| `config-flow-test-coverage` | 18 tests covering the config flow and the options flow (`tests/test_config_flow.py`) |
| `runtime-data` | `ConfigEntry.runtime_data` with the `HitachiYutakiConfigEntry` type alias |
| `docs-removal-instructions` | "Uninstall" section in README.md |

---

## Silver (10 rules)

### Rules met (6)

| Rule | Detail |
|------|--------|
| `config-entry-unloading` | Complete `async_unload_entry` (API closed, hass.data cleaned up) |
| `integration-owner` | `@alepee` in manifest.json |
| `entity-unavailable` | `last_update_success` on every entity |
| `action-exceptions` | Exceptions raised in services |
| `docs-configuration-parameters` | Parameters described in README |
| `docs-installation-parameters` | Installation parameters described in README |

### Rules not met (4)

| Rule | Detail | Effort |
|------|--------|--------|
| `log-when-unavailable` | Logs on every error instead of once; no log when the connection comes back | Low |
| `parallel-updates` | `PARALLEL_UPDATES` not defined in the platform files | Low |
| `reauthentication-flow` | No reauth flow (debatable: Modbus has no authentication) | Medium / N/A |
| `test-coverage` | Coverage < 95% -- tests limited to the domain layer | High |

---

## Gold (21 rules)

### Rules met (9)

| Rule | Detail |
|------|--------|
| `diagnostics` | `diagnostics.py`: entry data (host redacted), HC-A unit identity `(Ou, Iu)` and current slot, coordinator's last poll |
| `devices` | 8 devices created dynamically from the profile |
| `entity-category` | `EntityCategory.DIAGNOSTIC` used on advanced entities |
| `entity-device-class` | `SensorDeviceClass.POWER`, `ENERGY`, `TEMPERATURE`, etc. |
| `entity-disabled-by-default` | Advanced entities disabled by default |
| `entity-translations` | EN, FR, NL, RO translations (translations/) |
| `reconfiguration-flow` | `async_step_reconfigure`: gateway, connection, variant, model and power supply; reloads only when the data changed; refuses a unit already configured (compared on the connection target, not on the gateway hardware identifier, which is not proven unique, #162); the options flow keeps only the external sensors, beta features and telemetry |
| `repair-issues` | Repair flows (`missing_config`, `enable_telemetry`, `enable_energy_cost`) + `connection_error` issue |
| `stale-devices` | `async_remove_config_entry_device`: a circuit, DHW or pool device the heat pump no longer declares can be removed |

### Rules not met (12)

| Rule | Detail | Effort |
|------|--------|--------|
| `discovery` | No auto-discovery (limited by Modbus TCP) | N/A |
| `discovery-update-info` | N/A without discovery | N/A |
| `dynamic-devices` | Devices fixed at configuration time | N/A |
| `icon-translations` | No `icons.json` | Medium |
| `exception-translations` | Exceptions not translatable (`HomeAssistantError` without `translation_key`) | Medium |
| `docs-data-update` | No dedicated section in the documentation | Low |
| `docs-examples` | No automation examples | Low |
| `docs-known-limitations` | No known limitations section | Low |
| `docs-troubleshooting` | No troubleshooting section | Low |
| `docs-use-cases` | No use cases section | Low |
| `docs-supported-functions` | Partial -- entities listed but not exhaustively | Low |

---

## Platinum (3 rules)

| Rule | Status | Detail |
|------|--------|--------|
| `async-dependency` | Done | pymodbus supports asyncio |
| `inject-websession` | N/A | Modbus TCP, not HTTP |
| `strict-typing` | Not done | Type hints present but no `py.typed` / strict mode |

---

## Suggested action plan

### To reach Silver (4 actions)

**Quick wins:**
1. `parallel-updates` -- Add `PARALLEL_UPDATES = 0` to each platform file
2. `log-when-unavailable` -- Log once when unavailable and once when back

**Larger work:**
3. `reauthentication-flow` -- Assess whether it is relevant for Modbus (likely exempt)
4. `test-coverage` -- Extend tests to >95% (config flow, platforms, entities)

### Towards Gold

**Documentation quick wins:**
- `docs-data-update`, `docs-examples`, `docs-known-limitations`, `docs-troubleshooting`, `docs-use-cases`, `docs-supported-functions`

**Development:**
- `icon-translations` -- Create `icons.json`
- `exception-translations` -- Use `HomeAssistantError` with `translation_key`
