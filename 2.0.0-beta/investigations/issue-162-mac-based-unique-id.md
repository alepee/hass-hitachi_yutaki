# Issue #162: MAC-based unique_id for Config Entry

**Date**: 2026-01-24  
**Status**: 🔍 Investigation  
**Target Release**: Beta.8 or v2.1.0  
**Priority**: 🔴 High  
**GitHub Issue**: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)

---

## Executive Summary

### Current Problem
The config entry uses `{IP}_{slave_id}` as unique_id, which is:
- ❌ Not stable (changes with DHCP)
- ❌ Allows duplicates (same gateway, different IPs)
- ❌ Non-compliant with HA best practices

### Proposed Solution
Use **gateway's MAC address** as unique_id via ARP table lookup.

### Benefits
- ✅ Prevents duplicate config entries
- ✅ Survives IP changes
- ✅ HA compliant
- ✅ Graceful fallback if MAC unavailable

### Implementation Effort
- **Complexity**: 🟡 Medium
- **Breaking Changes**: ❌ None
- **Time Estimate**: 1-2 days (including testing)

### Risks
- Low: ARP lookup might fail → Fallback to current behavior
- Migration safe: Only adds unique_id if missing, doesn't break existing entries

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Current Situation](#current-situation)
3. [Technical Analysis](#technical-analysis)
4. [Proposed Solution](#proposed-solution)
5. [Implementation Plan](#implementation-plan)
6. [Testing Strategy](#testing-strategy)
7. [Risks & Mitigations](#risks--mitigations)
8. [References](#references)

---

## Problem Statement

### Issues with Current Implementation

Currently, the config entry `unique_id` is based on `{IP}_{slave_id}`:

```python
# config_flow.py:333-336
await self.async_set_unique_id(
    f"{config[CONF_HOST]}_{config[CONF_SLAVE]}"
)
self._abort_if_unique_id_configured()
```

**Problems:**

1. **✗ Not truly unique**: IP addresses can be reused
2. **✗ Not stable**: DHCP can change the gateway's IP
3. **✗ Duplicate entries possible**: Same gateway can be added with different IPs
4. **✗ No IP change detection**: If the gateway IP changes, HA cannot detect it
5. **✗ Non-compliant**: Home Assistant best practices recommend stable identifiers (MAC, serial)

### Benefits of MAC-based unique_id

✅ **Duplicate detection**: Prevents multiple config entries for the same physical gateway  
✅ **Stability**: unique_id doesn't change even if IP changes  
✅ **HA Compliance**: Follows recommended best practices  
✅ **Future-proof**: Prepares for potential DHCP discovery  
✅ **Better UX**: Clear "Already configured" message if duplication is attempted

---

## Current Situation

### Code Analysis

**Config Flow (`config_flow.py`)**:
- Line 333-336: Sets unique_id to `f"{config[CONF_HOST]}_{config[CONF_SLAVE]}"`
- Calls `_abort_if_unique_id_configured()` to prevent duplicates
- **Issue**: Only prevents duplicates with same IP+slave combination

**Setup (`__init__.py`)**:
- No logic to add/update unique_id after initial setup
- No migration for existing installations without unique_id

### Real-World Scenarios Affected

**Scenario 1: DHCP IP Change**
```
Day 1: Gateway at 192.168.1.100 → Config entry created with unique_id "192.168.1.100_1"
Day 30: DHCP lease expires, gateway gets 192.168.1.150
Result: HA cannot detect this is the same gateway
```

**Scenario 2: Duplicate Configuration**
```
User adds gateway at 192.168.1.100 → Entry created
User forgets, adds same gateway at 192.168.1.100 → ❌ Prevented (good)
User's network changes, gateway now at 192.168.1.150
User adds gateway at 192.168.1.150 → ✅ Allowed (BAD - duplicate!)
```

**Scenario 3: Network Migration**
```
User moves to new router with different subnet
Old: 192.168.1.100 → New: 192.168.0.100
Same physical gateway, but HA treats it as different
```

---

## Technical Analysis

### ATW-MBS-02 Gateway Capabilities

#### What Modbus Registers Expose

After analyzing the register map (`api/modbus/registers/atw_mbs_02.py`):

- ✅ System state, model, temperatures, controls
- ✅ Operational parameters
- ❌ **NO MAC address register**
- ❌ **NO serial number register**
- ❌ **NO unique hardware identifier**

### MAC Address Retrieval Methods

#### Method 1: ARP Table Lookup (RECOMMENDED)

**How it works:**
1. Send ping to populate ARP cache
2. Read system's ARP table
3. Extract MAC address for the IP

**Advantages:**
- ✅ Works on Linux, macOS, Windows
- ✅ No additional hardware/firmware requirements
- ✅ Reliable if gateway responds to ping
- ✅ Commonly used pattern in HA integrations

**Disadvantages:**
- ❌ Requires network access at config time
- ❌ May fail if ARP cache is empty
- ❌ Slightly increases config flow time (~1s)

**Implementation:**

```python
import asyncio
import re
from typing import Optional

async def async_get_gateway_mac(ip_address: str) -> Optional[str]:
    """Get gateway MAC address from ARP table.
    
    Args:
        ip_address: Gateway IP address
        
    Returns:
        MAC address in format "AA:BB:CC:DD:EE:FF" or None if not found
    """
    try:
        # Step 1: Ping to populate ARP cache
        ping_process = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", ip_address,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await ping_process.wait()
        
        # Step 2: Read ARP table
        arp_process = await asyncio.create_subprocess_exec(
            "arp", "-n", ip_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await arp_process.communicate()
        
        # Step 3: Parse MAC address
        # Matches formats: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
        mac_pattern = r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})'
        match = re.search(mac_pattern, stdout.decode())
        
        if match:
            # Normalize to uppercase with colons
            return match.group(0).replace('-', ':').upper()
            
    except Exception as err:
        _LOGGER.debug("Could not get MAC from ARP: %s", err)
    
    return None
```

#### Method 2: DHCP Discovery (FUTURE)

Would require:
- Listening for DHCP broadcasts
- More complex implementation
- May not work if gateway uses static IP

**Decision**: Start with ARP, consider DHCP for future enhancement.

---

## Proposed Solution

### High-Level Approach

1. **During config flow setup**: Attempt to retrieve MAC address
2. **If successful**: Use MAC as unique_id
3. **If fails**: Log warning, allow setup to continue without unique_id (graceful degradation)
4. **For existing installations**: Add migration in `async_setup_entry()` to retroactively add unique_id

### Detailed Implementation

#### 1. Add MAC Retrieval Utility

**New file: `custom_components/hitachi_yutaki/utils.py`**

```python
"""Utility functions for Hitachi Yutaki integration."""

import asyncio
import logging
import platform
import re
from typing import Optional

_LOGGER = logging.getLogger(__name__)


async def async_get_gateway_mac(ip_address: str) -> Optional[str]:
    """Get gateway MAC address from ARP table.
    
    This function pings the gateway to populate the ARP cache,
    then reads the system's ARP table to extract the MAC address.
    
    Args:
        ip_address: Gateway IP address
        
    Returns:
        MAC address in format "AA:BB:CC:DD:EE:FF" or None if not found
        
    Note:
        - Works on Linux, macOS, and Windows
        - Adds ~1 second to config flow time
        - May fail if ARP cache is empty or gateway unreachable
    """
    system = platform.system()
    
    try:
        # Step 1: Ping to populate ARP cache
        ping_cmd = ["ping"]
        if system == "Windows":
            ping_cmd.extend(["-n", "1", "-w", "1000", ip_address])
        else:  # Linux, macOS
            ping_cmd.extend(["-c", "1", "-W", "1", ip_address])
            
        ping_process = await asyncio.create_subprocess_exec(
            *ping_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await ping_process.wait()
        
        # Step 2: Read ARP table
        if system == "Windows":
            arp_cmd = ["arp", "-a", ip_address]
        else:  # Linux, macOS
            arp_cmd = ["arp", "-n", ip_address]
            
        arp_process = await asyncio.create_subprocess_exec(
            *arp_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await arp_process.communicate()
        
        if arp_process.returncode != 0:
            _LOGGER.debug(
                "ARP command failed with return code %s: %s",
                arp_process.returncode,
                stderr.decode()
            )
            return None
        
        # Step 3: Parse MAC address
        # Matches formats: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
        mac_pattern = r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})'
        match = re.search(mac_pattern, stdout.decode())
        
        if match:
            # Normalize to uppercase with colons
            mac = match.group(0).replace('-', ':').upper()
            _LOGGER.debug("Found MAC address for %s: %s", ip_address, mac)
            return mac
        else:
            _LOGGER.debug("No MAC address found in ARP output for %s", ip_address)
            return None
            
    except Exception as err:
        _LOGGER.debug("Could not get MAC from ARP for %s: %s", ip_address, err)
        return None
```

#### 2. Modify Config Flow

**Update `config_flow.py`**:

```python
from homeassistant.helpers.device_registry import format_mac
from .utils import async_get_gateway_mac

async def async_validate_connection(self, config: dict) -> FlowResult:
    """Validate the Modbus connection."""
    errors: dict[str, str] = {}

    api_client_class = GATEWAY_INFO[config["gateway_type"]].client_class
    api_client = api_client_class(
        self.hass,
        name=config[CONF_NAME],
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        slave=config[CONF_SLAVE],
    )

    try:
        if not await api_client.connect():
            errors["base"] = "cannot_connect"
        else:
            await api_client.read_values(api_client.register_map.gateway_keys)

            system_state = await api_client.read_value("system_state")
            if system_state == 2:  # Data init
                errors["base"] = "system_initializing"
            elif system_state == 1:  # Desync
                errors["base"] = "desync_error"
            else:
                model_key = await api_client.get_model_key()
                if model_key:
                    # Try to get MAC address for unique_id
                    mac = await async_get_gateway_mac(config[CONF_HOST])
                    
                    if mac:
                        # Use MAC as unique_id
                        unique_id = format_mac(mac)
                        _LOGGER.info(
                            "Gateway MAC address detected: %s (unique_id: %s)",
                            mac,
                            unique_id
                        )
                    else:
                        # Fallback to IP+slave (current behavior)
                        unique_id = f"{config[CONF_HOST]}_{config[CONF_SLAVE]}"
                        _LOGGER.warning(
                            "Could not retrieve gateway MAC address. "
                            "Using IP-based unique_id: %s. "
                            "Duplicate detection will be limited.",
                            unique_id
                        )
                    
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=config[CONF_NAME],
                        data={
                            k: v for k, v in config.items() if k != "show_advanced"
                        },
                    )
                else:
                    errors["base"] = "invalid_slave"

    except (ModbusException, ConnectionException, OSError):
        errors["base"] = "cannot_connect"
    finally:
        if api_client.connected:
            await api_client.close()

    return self.async_show_form(
        step_id="advanced" if "show_advanced" in config else "user",
        data_schema=ADVANCED_SCHEMA
        if "show_advanced" in config
        else GATEWAY_SCHEMA,
        errors=errors,
    )
```

#### 3. Add Migration for Existing Installations

**Update `__init__.py`**:

```python
from .utils import async_get_gateway_mac
from homeassistant.helpers.device_registry import format_mac

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hitachi Yutaki from a config entry."""
    _LOGGER.info("Setting up Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    # Add unique_id if missing (for existing installations)
    if entry.unique_id is None:
        _LOGGER.info(
            "Config entry has no unique_id, attempting to add one based on MAC address"
        )
        
        mac = await async_get_gateway_mac(entry.data[CONF_HOST])
        
        if mac:
            unique_id = format_mac(mac)
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)
            _LOGGER.info(
                "Added MAC-based unique_id to existing config entry: %s",
                unique_id
            )
        else:
            # Fallback to IP+slave for consistency
            unique_id = f"{entry.data[CONF_HOST]}_{entry.data[CONF_SLAVE]}"
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)
            _LOGGER.warning(
                "Could not retrieve MAC, using IP-based unique_id: %s",
                unique_id
            )
    
    # Continue normal setup...
    # [rest of setup code remains unchanged]
```

---

## Implementation Plan

### Phase 1: Core Implementation (Target: Beta.8)

#### Step 1: Add Utility Function
- [ ] Create `custom_components/hitachi_yutaki/utils.py`
- [ ] Implement `async_get_gateway_mac()` with multi-platform support
- [ ] Add comprehensive error handling and logging

#### Step 2: Update Config Flow
- [ ] Import new utility
- [ ] Modify `async_validate_connection()` to retrieve MAC
- [ ] Set unique_id based on MAC (with IP+slave fallback)
- [ ] Update logging to indicate MAC detection status

#### Step 3: Add Migration Logic
- [ ] Update `async_setup_entry()` in `__init__.py`
- [ ] Add unique_id retroactively for existing installations
- [ ] Log migration status

#### Step 4: Testing
- [ ] Unit tests for MAC retrieval function
- [ ] Integration tests for config flow
- [ ] Manual testing on different OS (Linux, macOS, Windows)
- [ ] Test fallback behavior when MAC unavailable

#### Step 5: Documentation
- [ ] Update README with duplicate detection info
- [ ] Add release notes
- [ ] Document fallback behavior

### Phase 2: Enhancement (Future - v2.2.0+)

- [ ] Consider DHCP discovery as alternative MAC source
- [ ] Add config flow option to manually specify MAC (rare cases)
- [ ] Investigate if gateway firmware updates expose MAC via Modbus

---

## Testing Strategy

### Unit Tests

**Test file: `tests/test_utils.py`**

```python
"""Test utility functions."""

import pytest
from custom_components.hitachi_yutaki.utils import async_get_gateway_mac


@pytest.mark.asyncio
async def test_get_gateway_mac_valid_ip():
    """Test MAC retrieval for valid, reachable IP."""
    # This test requires a real gateway on the network
    # In CI, this could be mocked
    mac = await async_get_gateway_mac("192.168.1.100")
    
    if mac:
        # Validate format
        assert len(mac) == 17  # AA:BB:CC:DD:EE:FF
        assert mac.count(':') == 5
        assert all(c in '0123456789ABCDEF:' for c in mac)


@pytest.mark.asyncio
async def test_get_gateway_mac_invalid_ip():
    """Test MAC retrieval for unreachable IP."""
    mac = await async_get_gateway_mac("192.168.255.254")
    assert mac is None


@pytest.mark.asyncio
async def test_get_gateway_mac_invalid_format():
    """Test MAC retrieval with invalid IP format."""
    mac = await async_get_gateway_mac("not_an_ip")
    assert mac is None
```

### Integration Tests

**Test Scenarios:**

1. **Fresh Installation - MAC Available**
   - Setup new integration
   - Verify unique_id is MAC-based
   - Attempt to add same gateway again → Should be prevented

2. **Fresh Installation - MAC Unavailable**
   - Mock MAC retrieval to fail
   - Setup new integration
   - Verify unique_id falls back to IP+slave
   - Verify warning is logged

3. **Existing Installation - No unique_id**
   - Create entry without unique_id
   - Restart HA
   - Verify migration adds MAC-based unique_id

4. **Existing Installation - IP-based unique_id**
   - Entry has old IP+slave unique_id
   - Question: Should we migrate? (See Risks section)

### Manual Testing

**Platforms:**
- [ ] Home Assistant OS (Linux-based)
- [ ] Home Assistant Container (Docker on Linux)
- [ ] Home Assistant Core (macOS)
- [ ] Home Assistant Core (Windows)

**Test Cases:**
1. ✅ Add new gateway with working MAC retrieval
2. ✅ Attempt duplicate with same IP → Prevented
3. ✅ Attempt duplicate with different IP (same MAC) → Prevented
4. ✅ Add gateway with MAC retrieval failure → Works with fallback
5. ✅ Existing installation migration → unique_id added
6. ✅ Verify no impact on entity unique_ids (they should remain unchanged)

---

## Risks & Mitigations

### Risk 1: MAC Retrieval Failure

**Scenario**: ARP lookup fails during config flow

**Impact**: 
- User cannot add gateway if we make MAC mandatory
- Duplicate detection unavailable

**Mitigation**:
- ✅ **Graceful degradation**: Fall back to IP+slave unique_id
- ✅ Log clear warning message
- ✅ Integration still functional

**Code:**
```python
if mac:
    unique_id = format_mac(mac)
else:
    # Fallback - integration still works
    unique_id = f"{config[CONF_HOST]}_{config[CONF_SLAVE]}"
    _LOGGER.warning(...)
```

### Risk 2: Platform Compatibility

**Scenario**: ARP command differs across OS

**Impact**: MAC retrieval fails on some platforms

**Mitigation**:
- ✅ Use `platform.system()` to detect OS
- ✅ Adjust command for Windows vs Unix-like
- ✅ Extensive multi-platform testing
- ✅ Fallback to IP+slave if command fails

**Supported Platforms:**
- Linux: `arp -n <ip>`
- macOS: `arp -n <ip>`
- Windows: `arp -a <ip>`

### Risk 3: Migration of Existing Installations

**Scenario**: User has entry with IP-based unique_id, MAC-based unique_id is now available

**Question**: Should we migrate IP-based → MAC-based?

**Options:**

**Option A: Migrate IP → MAC**
- ✅ Better long-term consistency
- ❌ Risk: If gateway MAC changes (very rare), HA thinks it's different gateway
- ❌ Complex: Need to check if new MAC-based unique_id already exists

**Option B: Keep existing IP-based, only add if missing**
- ✅ Safe: No breaking changes
- ✅ Simple implementation
- ❌ Mixed environment: Some entries MAC-based, some IP-based

**Recommendation**: **Option B** - Only add unique_id if missing, don't migrate existing

**Code:**
```python
if entry.unique_id is None:
    # Add unique_id (MAC or fallback to IP+slave)
    mac = await async_get_gateway_mac(entry.data[CONF_HOST])
    unique_id = format_mac(mac) if mac else f"{entry.data[CONF_HOST]}_{entry.data[CONF_SLAVE]}"
    hass.config_entries.async_update_entry(entry, unique_id=unique_id)
# Do NOT migrate existing IP-based unique_ids
```

### Risk 4: Performance Impact

**Scenario**: ARP lookup adds latency to config flow

**Impact**: 
- Config flow takes ~1 second longer
- User perceives slowness

**Mitigation**:
- ✅ Only happens during initial setup (rare operation)
- ✅ User already expects some wait time for connection validation
- ✅ Can be optimized by running in parallel with Modbus validation

**Optimization:**
```python
# Run MAC retrieval and Modbus connection in parallel
mac_task = asyncio.create_task(async_get_gateway_mac(config[CONF_HOST]))
modbus_connected = await api_client.connect()

if modbus_connected:
    # ... validate modbus ...
    mac = await mac_task  # Get MAC result
```

### Risk 5: Multiple Gateways on Same Network

**Scenario**: User has multiple ATW-MBS-02 gateways (multiple heat pumps)

**Expected Behavior**: Each gateway has unique MAC → Separate config entries

**Test**: 
- ✅ Verify different MACs create different entries
- ✅ Verify no interference between entries

**No risk**: This is the desired behavior.

### Risk 6: Users with Duplicate Entries (Current Situation)

**Scenario**: Some users may already have duplicate config entries (possible today)

**Question**: What happens after upgrade?

**Answer**:
- ✅ Both existing entries keep their entry_id (different UUIDs)
- ✅ Both entries continue to work
- ✅ Migration adds unique_id to both (same MAC)
- ❌ User cannot add a third duplicate (good!)
- User should manually remove one duplicate

**This is acceptable**: Forces cleanup of existing bad state.

---

## Impact Analysis

### Impact on Existing Users

**✅ Safe - No Breaking Changes:**

- `entry_id` (UUID) remains unchanged
- All entities keep their current unique_ids
- No entity migration needed
- History is preserved
- Automations continue to work

**🔄 Changes:**

- Duplicate detection enabled (prevents adding the same gateway twice)
- Only affects **new** installations or additions

### Impact on New Users

**✅ Better Experience:**

- Cannot accidentally create duplicates
- More robust configuration
- Better aligned with HA best practices

### Impact on Beta Testers

**Test Scenarios:**

1. **Fresh beta.8 install**: MAC-based unique_id from the start
2. **Upgrade from beta.7**: Migration adds unique_id
3. **Network change**: Same gateway, different IP → HA still recognizes it (via MAC)

---

## Implementation Checklist

### Development
- [ ] Create `utils.py` with `async_get_gateway_mac()`
- [ ] Update `config_flow.py` to use MAC-based unique_id
- [ ] Update `__init__.py` to migrate existing installations
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Run linter (`./scripts/lint`)
- [ ] Manual testing on multiple platforms

### Testing
- [ ] Test on Linux (HA OS / Container)
- [ ] Test on macOS
- [ ] Test on Windows
- [ ] Test MAC retrieval success
- [ ] Test MAC retrieval failure (fallback)
- [ ] Test duplicate prevention
- [ ] Test migration for existing installations
- [ ] Test no side effects on entities

### Documentation
- [ ] Update CHANGELOG
- [ ] Update release notes
- [ ] Document in architecture if needed
- [ ] Add comments in code for maintainability

### Release
- [ ] Tag as beta.8 or later
- [ ] Monitor community feedback
- [ ] Address any platform-specific issues

---

## References

### Related Issues
- GitHub Issue: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)

### Home Assistant Documentation
- [Config Flow Best Practices](https://developers.home-assistant.io/docs/config_entries_config_flow_handler)
- [Device Registry](https://developers.home-assistant.io/docs/device_registry_index/)
- [`format_mac()` helper](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/device_registry.py)

### Similar Implementations in HA Core
Many integrations use MAC-based unique_id:
- `homeassistant.components.xiaomi_miio`
- `homeassistant.components.unifi`
- `homeassistant.components.tplink`

### External Resources
- [ARP command reference](https://linux.die.net/man/8/arp)
- Reference implementation: `/Users/alepee/Documents/Perso/homeassistant/integrations/hitachi-yutaki-modus-data-extractor/get_gateway_mac.py`

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-24 | Use ARP table lookup | No MAC exposed via Modbus, ARP is reliable and cross-platform |
| 2026-01-24 | Graceful fallback to IP+slave | Ensures integration works even if MAC unavailable |
| 2026-01-24 | Do not migrate existing IP-based unique_ids | Safer, avoids potential conflicts |
| 2026-01-24 | Target Beta.8 | Non-breaking enhancement, suitable for beta release |

---

## Next Steps

1. **Review this investigation** with project maintainer
2. **Decide on target release** (Beta.8 vs v2.1.0)
3. **Implement Phase 1** (core functionality)
4. **Test extensively** on multiple platforms
5. **Gather beta feedback** before stable release

---

**Status**: 🔍 Ready for Implementation
