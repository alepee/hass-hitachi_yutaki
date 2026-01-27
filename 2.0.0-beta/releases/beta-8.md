# Release Notes - Beta.8

**Release Date**: TBD
**Version**: 2.0.0-beta.8
**Status**: 🚧 In Development

---

## Overview

Beta.8 focuses on improving integration robustness and configuration reliability by implementing hardware-based unique identifiers for config entries using Modbus Input Registers.

---

## What's New

### Hardware-based Config Entry Identification

**Issue**: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)

Config entries now use the gateway's hardware identifier (read from Modbus Input Registers) as their unique identifier instead of the IP+slave combination.

#### Benefits

✅ **Prevents Duplicate Entries**: You can no longer accidentally create multiple config entries for the same physical gateway
✅ **Survives IP Changes**: If your gateway's IP changes (DHCP), Home Assistant recognizes it as the same device
✅ **Works Everywhere**: Unlike MAC/ARP approach, this works in Docker containers, VMs, and all HA installation types
✅ **Best Practice Compliance**: Follows Home Assistant's recommended approach for stable device identification
✅ **Automatic Migration**: Existing installations automatically get the new unique_id on next restart

#### How It Works

When you add a new gateway:
1. The integration connects to the gateway via Modbus (as before)
2. **NEW**: Reads Input Registers 0-2 (function code 04) containing hardware identifiers
3. Builds unique_id in format `hitachi_yutaki_XXXX-YYY-ZZ` (e.g., `hitachi_yutaki_3846-103-56`)
4. If Modbus read fails, falls back to IP+slave (graceful degradation)

**For existing installations**: On the next Home Assistant restart, the integration will automatically add the hardware-based unique_id to your existing config entry. No action required!

#### Technical Details

- Uses Modbus Input Registers 0-2 (function code 04)
- Register values are hardware/firmware identifiers, stable across reboots
- Method implemented in `ModbusApiClient.async_get_unique_id()`
- Completely transparent to users
- No impact on entities, history, or automations

#### Why Not MAC Address?

The initial approach using MAC addresses via ARP table lookup was abandoned because:
- ❌ **Docker isolation**: ARP table inside containers only shows internal Docker network (172.30.32.x)
- ❌ **Platform-dependent**: Required different commands for Linux/macOS/Windows
- ❌ **Cache issues**: ARP entries expire and require ping to refresh

The Modbus-based approach solves all these issues by using the existing Modbus connection.

---

## Migration Notes

### From Beta.7 to Beta.8

**No action required** - Migration is automatic.

On first restart with Beta.8:
- The integration will check if your config entry has a unique_id
- If missing, it will read the gateway's hardware identifier via Modbus
- The unique_id will be added automatically
- All entities, history, and automations remain unchanged

**What you'll see in logs**:
```
[hitachi_yutaki] Config entry has no unique_id, attempting to add one based on hardware identifier
[hitachi_yutaki] Added hardware-based unique_id to existing config entry: hitachi_yutaki_3846-103-56
```

Or, if Modbus read fails:
```
[hitachi_yutaki] Could not retrieve hardware identifier, using IP-based unique_id: 192.168.1.100_1
```

Both scenarios are normal and the integration will work correctly.

---

## Breaking Changes

**None** - This release is fully backward compatible.

---

## Bug Fixes

None in this release (focused on enhancement).

---

## Known Issues

Same as Beta.7:
- **#176**: Auto-detection failure for some Yutaki S Combi models
- **#177**: Cooling features not working for some configurations
- **#178**: Anti-legionella features need investigation
- **#179**: Migration UX could be improved
- **#166**: COP values in graphs need refinement
- **#167**: Modbus transaction ID errors (intermittent)
- **#171**: Temperature corrected sensor error
- **#173**: Cannot change DHW temperature (some models)

---

## Testing

### What to Test

1. **Fresh Installation**:
   - Add a new gateway
   - Check logs for "Gateway hardware identifier detected"
   - Verify unique_id format: `hitachi_yutaki_XXXX-YYY-ZZ`
   - Verify integration works normally

2. **Duplicate Prevention**:
   - Try to add the same gateway again
   - Should see "Already configured" message

3. **Existing Installation**:
   - Restart Home Assistant with Beta.8
   - Check logs for unique_id migration
   - Verify all entities still work
   - Verify history is preserved

### Test Results Template

Please report your test results in [Discussion #117](https://github.com/alepee/hass-hitachi_yutaki/discussions/117):

```markdown
**Beta.8 Test Results**

- Platform: [HA OS / Container / Core / Supervised]
- Gateway Model: [ATW-MBS-02]
- Heat Pump Model: [Yutaki S / S80 / M / etc.]

**Fresh Installation**:
- [ ] Hardware ID detected successfully
- [ ] unique_id format correct (hitachi_yutaki_X-Y-Z)
- [ ] Integration loaded
- [ ] Entities created

**Duplicate Prevention**:
- [ ] Duplicate prevented
- [ ] Error message shown

**Migration**:
- [ ] unique_id added automatically
- [ ] Integration loaded
- [ ] Entities preserved
- [ ] History preserved

**Hardware ID Values** (from logs): `____-____-____`

**Issues Found**: [None / Describe issues]
```

---

## Installation

### Via HACS (Recommended)

1. Open HACS
2. Go to Integrations
3. Find "Hitachi Yutaki"
4. Click "Update" or "Redownload"
5. Select version `2.0.0-beta.8`
6. Restart Home Assistant

### Manual Installation

1. Download `beta-8` from GitHub
2. Copy `custom_components/hitachi_yutaki/` to your HA config
3. Restart Home Assistant

---

## Upgrade Path

### From 1.9.x → Beta.8

Follow the standard upgrade path:
1. Backup your Home Assistant configuration
2. Install Beta.8
3. Restart Home Assistant
4. Complete repair flow if prompted (for missing profile/gateway_type)
5. Entity migration happens automatically
6. Config entry unique_id is added automatically

### From Beta.7 → Beta.8

Direct upgrade:
1. Install Beta.8
2. Restart Home Assistant
3. Config entry unique_id is added automatically
4. Done!

---

## Files Changed

### New/Modified
- `api/base.py` - Added `async_get_unique_id()` abstract method
- `api/modbus/__init__.py` - Implemented `async_get_unique_id()` using `read_input_registers`
- `config_flow.py` - Uses new method for unique_id generation
- `__init__.py` - Uses new method for existing installation migration
- `tests/test_modbus_api.py` - New tests for unique_id retrieval

### Removed
- `utils.py` - Removed obsolete `async_get_gateway_mac()` function

---

## Documentation

- **Investigation Summary**: [issue-162-implementation-summary.md](../investigations/issue-162-implementation-summary.md)
- **ARP Investigation (historical)**: [issue-162-arp-investigation.md](../investigations/issue-162-arp-investigation.md)
- **Issues Tracking**: [issues-tracking.md](../tracking/issues-tracking.md)

---

## Contributors

- @alepee - Implementation and investigation

Special thanks to beta testers:
- @tijmenvanstraten
- @Snoekbaarz

---

## Next Steps

### Beta.9+ Roadmap

Focus areas for upcoming betas:
1. **Auto-detection improvements** (issues #176, #177)
2. **Anti-legionella features** (issue #178)
3. **COP calculation refinements** (issue #166)
4. **Temperature control fixes** (issue #173)

See [Planned Improvements](../tracking/planned-improvements.md) for full roadmap.

---

## Support

- **Issues**: https://github.com/alepee/hass-hitachi_yutaki/issues
- **Discussions**: https://github.com/alepee/hass-hitachi_yutaki/discussions
- **Beta Testing**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117

---

**Status**: 🚧 Ready for Testing
**Last Updated**: 2026-01-24
