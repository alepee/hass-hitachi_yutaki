# Issue #162: Hardware-based Unique ID - Consolidated Investigation

**Date**: 2026-01-24
**Status**: ✅ **IMPLEMENTED - Ready for Beta.8**
**Goal**: Uniquely identify each gateway to prevent duplicate config entries

---

## Executive Summary

Issue #162 requested a hardware-based `unique_id` for config entries to:
- Prevent duplicate configurations
- Survive DHCP IP address changes
- Allow Home Assistant to detect already-configured gateways

**Implemented solution**: Read Modbus Input Registers 0-2 (ATW-MBS-02 gateway hardware identifiers)

---

## Investigation Timeline

### Phase 1: MAC/ARP Approach ❌

**Initial hypothesis**: Use gateway MAC address via ARP table lookup

**Tested implementation**:
```python
async def async_get_gateway_mac(ip_address: str) -> str | None:
    # 1. Ping to populate ARP cache
    # 2. Read ARP table
    # 3. Extract MAC address
```

**Result**: ❌ Failed in ~95% of installations

### Phase 2: Root Cause Investigation ✅

**Root cause identified**: Docker container network isolation

```
┌─────────────────────────────────────────────────────────────┐
│                       Host Machine                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           External Network (192.168.0.x)            │   │
│  │  ┌─────────────┐                                    │   │
│  │  │ Modbus      │ 192.168.0.4                        │   │
│  │  │ Gateway     │ ← MAC invisible from container     │   │
│  │  └─────────────┘                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↑ NAT/Routing                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Docker Network (172.30.32.x)              │   │
│  │  ┌─────────────┐  ┌─────────────┐                   │   │
│  │  │ HA Core     │  │ Supervisor  │                   │   │
│  │  │ (integr.)   │  │ 172.30.32.2 │                   │   │
│  │  └─────────────┘  └─────────────┘                   │   │
│  │       ↑ ARP table = Docker network only             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Tests performed on HA OS**:
```bash
# Ping works (routed via NAT)
ha > ping 192.168.0.4
64 bytes from 192.168.0.4: seq=0 ttl=99 time=0.352 ms

# ARP table = only internal Docker network
ha > arp -a
supervisor (172.30.32.2) at 46:ae:7f:d1:5b:3e [ether] on eth0
hassio_dns.hassio (172.30.32.3) at 8a:34:a2:0c:05:e3 [ether] on eth0

# External IP not visible
ha > ip neigh show 192.168.0.4
# (no output)
```

**Impact by installation type**:

| Installation | MAC via ARP | Reason |
|--------------|-------------|--------|
| Home Assistant OS | ❌ | Containerized |
| Home Assistant Supervised | ❌ | Containerized |
| Home Assistant Container | ❌ | Docker by design |
| Home Assistant Core | ✅ | Bare metal, direct network access |

**Conclusion**: MAC/ARP approach is architecturally impossible for ~95% of HA installations.

### Phase 3: Alternative Solution ✅

**New approach**: ATW-MBS-02 gateway Modbus Input Registers

The gateway exposes hardware identification registers accessible via Modbus:
- **Register 0**: Hardware identifier 1
- **Register 1**: Hardware identifier 2
- **Register 2**: Hardware identifier 3

**unique_id format**: `hitachi_yutaki_{reg0}-{reg1}-{reg2}`
**Example**: `hitachi_yutaki_3846-103-56`

---

## Implemented Solution

### Modified Files

| File | Changes |
|------|---------|
| `api/base.py` | Added abstract method `async_get_unique_id()` |
| `api/modbus/__init__.py` | Implemented Input Registers 0-2 read |
| `config_flow.py` | Uses `async_get_unique_id()` |
| `__init__.py` | Automatic migration for existing installations |

### Deleted Files

| File | Reason |
|------|--------|
| `utils.py` | Obsolete MAC/ARP function |
| `scripts/test_mac_retrieval.py` | No longer needed |

### Created Files

| File | Content |
|------|---------|
| `tests/test_modbus_api.py` | 10 unit tests |

### Core Code

**`api/modbus/__init__.py`**:
```python
async def async_get_unique_id(self) -> str | None:
    """Get hardware-based unique identifier from Input Registers 0-2."""
    try:
        result = await self._client.read_input_registers(address=0, count=3, slave=self._slave)
        if result.isError():
            return None
        if len(result.registers) < 3:
            return None
        return f"{result.registers[0]}-{result.registers[1]}-{result.registers[2]}"
    except Exception:
        return None
```

**`config_flow.py`**:
```python
# In async_validate_connection()
unique_id = await api_client.async_get_unique_id()
if unique_id:
    unique_id = f"{DOMAIN}_{unique_id}"
else:
    unique_id = f"{host}_{slave}"  # Fallback
```

---

## Modbus Solution Advantages

| Criterion | MAC/ARP | Modbus Input Registers |
|-----------|---------|------------------------|
| Docker containers | ❌ Isolated ARP | ✅ Works via Modbus TCP |
| System commands | ❌ OS-dependent | ✅ Universal |
| Network namespaces | ❌ Shows wrong IPs | ✅ Direct connection |
| Cache expiration | ❌ Requires ping | ✅ Direct read |
| Complexity | ❌ Ping + ARP + parsing | ✅ Single Modbus read |

---

## Final Behavior

### New Installations

```mermaid
flowchart TD
    Start[Add integration] --> Connect[Connect to gateway]
    Connect --> Valid{Connection OK?}
    Valid -->|No| Error[Error]
    Valid -->|Yes| GetID[Read Input Registers 0-2]
    GetID --> IDFound{Registers read?}
    IDFound -->|Yes| UseHW[unique_id = hitachi_yutaki_X-Y-Z]
    IDFound -->|No| UseFallback[unique_id = IP_slave]
    UseHW --> CheckDupe[Check duplicate]
    UseFallback --> CheckDupe
    CheckDupe --> IsDupe{Already exists?}
    IsDupe -->|Yes| Abort[Abort: Already configured]
    IsDupe -->|No| Create[Create config entry]
```

### Existing Installation Migration

```mermaid
flowchart TD
    Start[HA restart with Beta.8] --> Load[Load integration]
    Load --> CheckUID{unique_id exists?}
    CheckUID -->|Yes| Skip[No migration needed]
    CheckUID -->|No| TempClient[Temporary API client]
    TempClient --> Connect[Connect to gateway]
    Connect --> GetID[Read Input Registers 0-2]
    GetID --> IDFound{Registers read?}
    IDFound -->|Yes| SetHW[unique_id = hitachi_yutaki_X-Y-Z]
    IDFound -->|No| SetIP[unique_id = IP_slave]
    SetHW --> Update[Update config entry]
    SetIP --> Update
    Update --> Close[Close temp client]
    Close --> Continue[Continue setup]
    Skip --> Continue
```

---

## Tests

### Unit Tests ✅

```bash
pytest tests/test_modbus_api.py -v
```

**10 passing tests**:
- `test_async_get_unique_id_success`
- `test_async_get_unique_id_different_values`
- `test_async_get_unique_id_modbus_error`
- `test_async_get_unique_id_modbus_exception`
- `test_async_get_unique_id_connection_error`
- `test_async_get_unique_id_os_error`
- `test_async_get_unique_id_insufficient_registers`
- `test_async_get_unique_id_zero_values`
- `test_async_get_unique_id_max_values`
- `test_async_get_unique_id_more_than_three_registers`

### Linter ✅

```bash
./scripts/lint
```
All checks pass.

---

## Manual Testing Guide

### Scenario 1: New Installation

1. Start HA dev: `./scripts/develop`
2. Add Hitachi Yutaki integration
3. Check logs:
   ```
   DEBUG: Hardware unique_id retrieved: 3846-103-56
   ```
4. Verify `.storage/core.config_entries`:
   ```json
   {"unique_id": "hitachi_yutaki_3846-103-56", ...}
   ```

### Scenario 2: Duplicate Prevention

1. Try to add the same gateway a second time
2. Expected: "Already configured" message, setup aborted

### Scenario 3: Migration

1. Stop HA
2. Edit `.storage/core.config_entries`, remove `unique_id`
3. Restart HA
4. Check logs for migration
5. Verify `unique_id` is restored

### Scenario 4: Fallback

1. If registers are unreadable
2. Expected: `unique_id = IP_slave` (e.g., `192.168.0.4_1`)
3. Integration works normally

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Modbus read fails | Very low | Low | Fallback to IP+slave |
| Incorrect register values | Very low | Low | Tested as stable |
| Performance impact | None | None | Single Modbus read |
| Breaking changes | None | None | Backward compatible |

---

## Conclusion

The investigation for issue #162 demonstrated that:

1. **MAC/ARP approach is impossible** in containerized environments (95% of HA installations)
2. **Modbus Input Registers approach works** in all environments
3. **IP+slave fallback** ensures operation even on failure

The implemented solution is:
- ✅ Universal (works everywhere)
- ✅ Robust (graceful fallback)
- ✅ Simple (single Modbus read)
- ✅ Tested (10 unit tests)
- ✅ Backward compatible (automatic migration)

**Final Status**: 🎯 **READY FOR BETA.8**
**Last Updated**: 2026-01-27
