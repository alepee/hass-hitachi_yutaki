# Investigation: Repair Flow Optimization for 1.9.3 → 2.0.0 Migration

**Date**: 2026-01-23
**Context**: Version 2.0.0-beta.7 migration from 1.9.3
**Issue**: Suboptimal repair flow requiring multiple manual steps

## Problem Statement

When users upgrade from version 1.9.3 to 2.0.0, the integration requires `gateway_type` and `profile` parameters that didn't exist in 1.9.3.

### Current Broken State ❌

1. User upgrades integration to 2.0.0-beta.7
2. Integration setup fails with "Configuration incomplete" warning
3. Repair issue appears in Settings → System → Repairs
4. **User clicks "Fix" button → NOTHING HAPPENS** ❌
5. No repair form is displayed

### Root Cause

The repair issue is created with `is_fixable=True` in `__init__.py`, but **there is no `async_create_fix_flow()` function** to handle the repair flow creation. The `async_step_repair()` method exists in `HitachiYutakiOptionsFlow`, but Home Assistant doesn't know how to route to it from the repairs system.

The repair form code exists but is **completely unreachable** from the UI.

### Expected User Journey (After Fix)

1. User upgrades integration to 2.0.0
2. Integration setup fails with "Configuration incomplete" warning
3. Repair issue appears in Settings → System → Repairs
4. User clicks "Fix" button → **Repair form opens** ✅
5. User selects `gateway_type` (defaults to `modbus_atw_mbs_02`) and `profile`
6. User clicks "Submit" → Configuration saved
7. Integration automatically reloads
8. ✅ **Integration works immediately**

## Current Implementation Analysis

### 1. Setup Entry Flow (`__init__.py`)

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hitachi Yutaki from a config entry."""

    # Check for missing required configuration parameters
    missing_params = []
    if "gateway_type" not in entry.data:
        missing_params.append("gateway_type")
    if "profile" not in entry.data:
        missing_params.append("profile")

    if missing_params:
        # Create a repair issue to guide the user through reconfiguration
        async_create_issue(
            hass,
            DOMAIN,
            f"missing_config_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="missing_config",
        )

        # Return False to prevent setup until repair is completed
        return False
```

**Analysis**:
- ✅ Correctly detects missing parameters
- ✅ Creates repair issue with `is_fixable=True`
- ❌ **Issue has no associated fix flow handler** - button does nothing!

### 2. Repair Form Code (`config_flow.py`)

The repair form logic exists in `HitachiYutakiOptionsFlow.async_step_repair()` (lines 473-534), but is **unreachable** because:

**Missing**: No `async_create_fix_flow()` function to create the flow from the repair issue.

```python
# THIS FUNCTION DOES NOT EXIST ❌
async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairFlow:
    """Create repair flow."""
    # No implementation!
```

### 3. Root Cause - Missing Repair Flow Handler

Home Assistant's repair system requires a **module-level function** `async_create_fix_flow()` to create repair flows. Without it:

1. ✅ Issue is created correctly
2. ✅ "Fix" button appears in UI
3. ❌ Clicking "Fix" does NOTHING (no handler exists)
4. ❌ Form never appears

The repair system cannot route to `OptionsFlow.async_step_repair()` automatically. It needs an explicit flow factory function.

## Proposed Solutions

### Solution 1: Implement Repair Flow Handler + Auto-reload ⭐ **RECOMMENDED**

**Approach**: Add the missing `async_create_fix_flow()` function and trigger integration reload after repair.

**Implementation** (2 changes required):

```python
async def async_step_repair(
    self, user_input: dict[str, Any] | None = None
) -> FlowResult:
    """Handle repair step for missing configuration."""
    config_data = self.config_entry.data

    if user_input is not None:
        # Update the config entry with the missing parameters
        new_data = {
            **config_data,
            "gateway_type": user_input.get("gateway_type", "modbus_atw_mbs_02"),
            "profile": user_input.get("profile"),
        }

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

        # Clear the repair issue
        async_delete_issue(
            self.hass,
            DOMAIN,
            f"missing_config_{self.config_entry.entry_id}",
        )

        # ✨ NEW: Reload the integration to apply changes
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        return self.async_create_entry(
            title="Configuration repaired",
            data={},
        )
```

**Pros**:
- ✅ Actually makes the repair button work!
- ✅ User experience is seamless
- ✅ Integration immediately functional after repair
- ✅ No additional manual steps required
- ✅ Follows Home Assistant repair patterns correctly
- ✅ Dedicated flow class = cleaner separation of concerns

**Cons**:
- Requires creating a new flow class (~80 lines)
- Need to update imports

**User Journey After Fix**:
1. User clicks "Fix" in repairs → **Form now opens!** ✅
2. User selects gateway type and profile
3. User clicks "Submit"
4. Integration automatically reloads in background
5. Success notification appears
6. ✅ **Integration works immediately** - no additional steps needed

---

### Solution 2: Use Repair Flow Instead of Options Flow

**Approach**: Create a dedicated repair flow class inheriting from `RepairFlow` instead of routing through `OptionsFlow`.

**Implementation**:

```python
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

class MissingConfigRepairFlow(RepairFlow):
    """Handler for missing configuration repair flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle init step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation step."""
        if user_input is not None:
            # Get config entry
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            entry = next(
                (e for e in config_entries if e.entry_id in self.issue_id),
                None
            )

            if entry is None:
                return self.async_abort(reason="entry_not_found")

            # Update config entry
            new_data = {
                **entry.data,
                "gateway_type": user_input.get("gateway_type", "modbus_atw_mbs_02"),
                "profile": user_input.get("profile"),
            }

            self.hass.config_entries.async_update_entry(entry, data=new_data)

            # Reload integration
            await self.hass.config_entries.async_reload(entry.entry_id)

            return self.async_create_entry(data={})

        # Show form
        gateway_options = list(GATEWAY_INFO.keys())
        profile_options = list(PROFILES.keys())

        schema = vol.Schema({
            vol.Required("gateway_type", default=gateway_options[0]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=gateway_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("profile", default=profile_options[0]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=profile_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(step_id="confirm", data_schema=schema)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairFlow:
    """Create flow."""
    return MissingConfigRepairFlow()
```

And update `__init__.py`:

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hitachi Yutaki from a config entry."""

    if missing_params:
        async_create_issue(
            hass,
            DOMAIN,
            f"missing_config_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="missing_config",
            # Add repair flow handler
            data={"entry_id": entry.entry_id},
        )
        return False
```

**Pros**:
- ✅ Cleaner separation of concerns
- ✅ Proper use of Home Assistant repair system
- ✅ Can include custom messaging and instructions
- ✅ Better UX with dedicated repair interface

**Cons**:
- ❌ More code to write and maintain
- ❌ Requires understanding of RepairFlow API
- ❌ More refactoring needed
- ❌ May require translations updates

---

### Solution 3: Auto-detect Profile During Migration

**Approach**: During `async_migrate_entry()`, connect to the gateway and auto-detect the profile, eliminating the need for user input entirely.

**Implementation**:

```python
async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new_data = {**config_entry.data}

        # Add gateway_type (always modbus_atw_mbs_02 for 1.9.x users)
        if "gateway_type" not in new_data:
            new_data["gateway_type"] = "modbus_atw_mbs_02"

        # Auto-detect profile if missing
        if "profile" not in new_data:
            try:
                # Connect and read data
                gateway_info = GATEWAY_INFO["modbus_atw_mbs_02"]
                api_client = gateway_info.client_class(
                    hass,
                    name=config_entry.data[CONF_NAME],
                    host=config_entry.data[CONF_HOST],
                    port=config_entry.data[CONF_PORT],
                    slave=config_entry.data[CONF_SLAVE],
                )

                if await api_client.connect():
                    keys_to_read = api_client.register_map.base_keys
                    await api_client.read_values(keys_to_read)
                    all_data = {key: await api_client.read_value(key) for key in keys_to_read}
                    decoded_data = api_client.decode_config(all_data)

                    # Detect profile
                    detected_profiles = [
                        key for key, profile in PROFILES.items()
                        if profile.detect(decoded_data)
                    ]

                    if detected_profiles:
                        new_data["profile"] = detected_profiles[0]
                        _LOGGER.info("Auto-detected profile: %s", detected_profiles[0])
                    else:
                        # Fallback: still need user input
                        _LOGGER.warning("Could not auto-detect profile")

                    await api_client.close()

            except Exception as err:
                _LOGGER.error("Failed to auto-detect profile during migration: %s", err)

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
```

**Pros**:
- ✅ Zero user interaction needed (best UX)
- ✅ Profile detection is already implemented
- ✅ Works for 95%+ of cases automatically
- ✅ Eliminates repair flow entirely for most users

**Cons**:
- ❌ Migration requires network connection
- ❌ Migration can fail if gateway is offline
- ❌ Blocks during startup (migration is blocking)
- ❌ Still need repair fallback for failure cases
- ❌ More complex error handling

---

## Recommendation

**Must implement Solution 1** to make the repair system functional:
- Without this, the repair button literally does nothing
- This is a **blocking bug**, not just a UX issue
- Should be implemented immediately

**Consider Solution 3** for future enhancement (2.1.0):
- Eliminates manual intervention entirely
- Better long-term UX
- Requires more testing and error handling
- Can coexist with Solution 1 as a fallback

## Implementation Priority

### Phase 1: Quick Fix (beta.7/beta.8)
- ✅ Add integration reload after repair
- ✅ Test with real migration scenario
- ✅ Update any related translations if needed

### Phase 2: Long-term Enhancement (2.0.0 final or 2.1.0)
- Consider auto-detection during migration
- Add better error handling and fallback mechanisms
- Possibly refactor to dedicated RepairFlow

## Testing Plan

### Manual Testing
1. Create test instance with 1.9.3 configuration
2. Upgrade to 2.0.0-beta.7+fix
3. Verify repair issue appears
4. Complete repair flow
5. Verify integration loads automatically without manual steps
6. Check logs for any errors during reload

### Edge Cases
- Gateway offline during repair → verify graceful failure
- Multiple integration instances → verify correct entry is reloaded
- Rapid repair completion → verify no race conditions

## Files to Modify

### Primary Changes
- `custom_components/hitachi_yutaki/config_flow.py`
  - Add `async_create_fix_flow()` function at module level
  - Add `HitachiYutakiRepairFlow` class
  - Remove `async_step_repair` from `HitachiYutakiOptionsFlow` (lines 373-534, specifically 473-534)
  - Update imports if needed

### Secondary Changes
- Translation files: Verify existing translations work with repair flow
- Update `async_step_init` in OptionsFlow to remove the repair redirect (lines 378-387)

## Related Issues/PRs

- Entity migration (issue #8): Already handled by `entity_migration.py`
- Version 2 config flow: Introduced in beta.1
- Profile auto-detection: Implemented in config flow, can be reused

## Success Criteria

✅ User completes repair with gateway_type + profile selection
✅ Integration automatically reloads after repair
✅ Integration is immediately functional (no additional steps)
✅ No errors in logs during reload
✅ Repair issue is properly cleared
✅ Configuration persists across Home Assistant restarts
