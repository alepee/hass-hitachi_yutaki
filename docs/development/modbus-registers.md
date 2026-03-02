# Modbus Registers

## Overview

Registers are the interface between the integration and the heat pump hardware.
Each Hitachi gateway type exposes a set of Modbus holding registers that encode
sensor readings, operating states, and writable commands. The integration
abstracts these registers behind human-readable string keys so that entity code
never deals with raw addresses.

Each supported gateway has its own register map implementation. Adding support
for a new gateway means implementing a new `HitachiRegisterMap` subclass with
its own register definitions.

## Key Concepts

### Register vs Key

A **register** is a Modbus address (e.g. `1091`). A **key** is the
human-readable string the integration uses internally (e.g. `"outdoor_temp"`).
The mapping between the two is defined by `RegisterDefinition` instances grouped
into dictionaries per device.

### CONTROL vs STATUS Registers

Hitachi gateways expose two logical register ranges:

- **CONTROL** (R/W) -- commands sent to the heat pump (e.g. target temperature,
  power on/off).
- **STATUS** (R) -- actual state read back from the heat pump (e.g. current
  temperature, operating mode).

**Always read from STATUS registers for sensor entities.** Reading a CONTROL
register only tells you what was last *commanded*, not the actual running state.
For the ATW-MBS-02, CONTROL and STATUS share the same address space (addresses
1000-1031 are R/W, 1080+ are R-only). For the HC-A(16/64)MB, the two ranges are
at different offsets (CONTROL at offset 50, STATUS at offset 100), and writable
registers use the `write_address` field.

### RegisterDefinition Dataclass

Every register is described by a `RegisterDefinition` (defined in
`api/modbus/registers/__init__.py`):

```python
@dataclass
class RegisterDefinition:
    address: int                                    # Read address (STATUS register)
    deserializer: Callable[[Any], Any] | None = None  # Raw value -> Python value
    serializer: Callable[[Any], Any] | None = None    # Python value -> raw value (for writes)
    write_address: int | None = None                  # Write address if different from read
    fallback: RegisterDefinition | None = None        # Fallback register if primary returns None
```

- `address` -- the Modbus holding register address used for reads.
- `deserializer` -- optional function applied after reading the raw 16-bit value.
- `serializer` -- optional function applied before writing a value.
- `write_address` -- when the write address differs from the read address (used
  by HC-A(16/64)MB where CONTROL and STATUS are at different offsets).
- `fallback` -- an alternative register to try when the primary returns `None`
  (e.g. sensor error `0xFFFF`).

## Register Definition Files

### ATW-MBS-02

File: `api/modbus/registers/atw_mbs_02.py`

The original gateway. All registers use absolute addresses (1000-1231). CONTROL
and STATUS addresses share the same namespace, so `write_address` is not needed.

### HC-A(16/64)MB

File: `api/modbus/registers/hc_a_mb.py`

The newer gateway. Addresses are computed as `base + offset` where `base = 5000
+ (unit_id * 200)`. CONTROL registers (offsets 50-86) and STATUS registers
(offsets 100-192) are separate, so writable keys specify both addresses.

### Register Groups

Both files organize registers into dictionaries by device:

| Dictionary                       | Device                | Example keys                                  |
| -------------------------------- | --------------------- | --------------------------------------------- |
| `REGISTER_GATEWAY`               | ATW-MBS-02 gateway    | `alarm_code`, `unit_model`, `system_config`   |
| `REGISTER_CONTROL_UNIT`          | Main control unit     | `outdoor_temp`, `water_inlet_temp`, `unit_power` |
| `REGISTER_PRIMARY_COMPRESSOR`    | Primary compressor    | `compressor_frequency`, `compressor_current`  |
| `REGISTER_SECONDARY_COMPRESSOR`  | Secondary compressor  | `secondary_compressor_frequency`              |
| `REGISTER_CIRCUIT_1`             | Heating/cooling zone 1| `circuit1_power`, `circuit1_target_temp`      |
| `REGISTER_CIRCUIT_2`             | Heating/cooling zone 2| `circuit2_power`, `circuit2_target_temp`      |
| `REGISTER_DHW`                   | Domestic hot water    | `dhw_power`, `dhw_current_temp`               |
| `REGISTER_POOL`                  | Pool heating          | `pool_power`, `pool_current_temp`             |

### Concrete Examples

A read-only register (ATW-MBS-02):

```python
"outdoor_temp": RegisterDefinition(1091, deserializer=convert_signed_16bit),
```

Address `1091`, value deserialized through `convert_signed_16bit` to handle
negative temperatures via two's complement.

A writable register with a serializer (ATW-MBS-02):

```python
"pool_target_temp": RegisterDefinition(
    1029, deserializer=convert_from_tenths, serializer=lambda v: int(v * 10)
),
```

Reads are divided by 10 (tenths to degrees); writes multiply by 10 (degrees to
tenths).

A writable register with separate read/write addresses (HC-A(16/64)MB):

```python
"unit_power": RegisterDefinition(
    self._addr(100), write_address=self._addr(50)
),
```

Reads from STATUS offset 100, writes to CONTROL offset 50.

A register with a fallback (ATW-MBS-02):

```python
"water_outlet_temp": RegisterDefinition(
    1200,
    deserializer=convert_signed_16bit,
    fallback=RegisterDefinition(1093, deserializer=convert_signed_16bit),
),
```

Reads register 1200 first; if it returns `None` (sensor error), falls back to
register 1093.

## Common Deserializers

| Function                     | Purpose                                       | Example                              |
| ---------------------------- | --------------------------------------------- | ------------------------------------ |
| `convert_signed_16bit`       | Two's complement for signed 16-bit values     | `0xFF9C` -> `-100` (temperature)     |
| `convert_from_tenths`        | Divide by 10 for decimal precision            | `253` -> `25.3` (degrees or m3/h)    |
| `convert_pressure`           | Hundredths of MPa to bar (divide by 10)       | `510` -> `51.0` bar                  |
| `deserialize_unit_model`     | Model ID to string key                        | `2` -> `"yutaki_s80"`               |
| `deserialize_system_state`   | System state code to string                   | `0` -> `"synchronized"`             |
| `deserialize_operation_state`| Operation state code to translation key       | `6` -> `"operation_state_heat_thermo_on"` |
| `deserialize_otc_method`     | OTC method code to constant                   | `1` -> `OTCCalculationMethod.POINTS` |
| `deserialize_alarm_code`     | Alarm code to translation key                 | `42` -> `"alarm_code_42"`           |

## Data Flow

### Reading (gateway to entity)

```
Hardware register
    |
    v
api_client.read_values(keys)          # Reads holding registers via pymodbus
    |
    v
RegisterDefinition.deserializer(raw)   # Converts raw 16-bit value to Python type
    |
    v
api_client._data[key] = value          # Stored in client internal cache
    |
    v
coordinator._async_update_data()       # Copies to coordinator.data[key]
    |
    v
entity.value_fn(coordinator)           # Entity reads via coordinator.data.get("key")
```

Entity descriptions reference the key with a `value_fn` lambda:

```python
HitachiYutakiSensorEntityDescription(
    key="outdoor_temp",
    value_fn=lambda coordinator: coordinator.data.get("outdoor_temp"),
    # ...
)
```

### Writing (entity to gateway)

```
entity calls api_client.write_value(key, value)
    |
    v
RegisterDefinition.serializer(value)   # Converts Python value to raw (if serializer set)
    |
    v
write_register(write_address or address, raw_value)  # pymodbus write_register
```

The `write_value` method checks that the key is in `WRITABLE_KEYS` before
attempting the write, and uses `write_address` when it differs from the read
address.

## Adding a New Register

1. **Find the register address** in the gateway documentation
   (see [gateway docs](../gateway/)).

2. **Add a `RegisterDefinition`** to the appropriate `REGISTER_*` dictionary in
   the gateway's register file. Choose the correct group based on which device
   the register belongs to.

3. **Add a deserializer** if the raw value needs conversion (signed temperature,
   tenths, pressure, enum mapping). Reuse existing functions when possible.

4. **If the register is writable**: add a serializer if needed, and add the key
   to the `WRITABLE_KEYS` set.

5. **Create an entity description** in the appropriate `entities/<domain>/`
   builder, referencing the key in `value_fn`.

6. **If the register is model-specific**: add the key to the profile's
   `extra_register_keys` list instead of the base register group (see
   [Profiles](profiles.md)).

## Sentinel Values

Certain raw register values have special meaning and should not be interpreted
as normal data:

| Raw value  | Decimal  | Meaning                                              |
| ---------- | -------- | ---------------------------------------------------- |
| `0xFFFF`   | 65535    | Sensor not connected or communication error          |
| `0xFF81`   | -127 (signed) | Temperature sensor disconnected                |
| `0xFFBD`   | -67 (signed)  | DHW temperature sensor disconnected            |

The `convert_signed_16bit` and `convert_from_tenths` deserializers return `None`
when they encounter `0xFFFF`, which propagates as an unavailable entity state in
Home Assistant.

## Further Reading

- [Gateway hardware documentation](../gateway/) -- register addresses and
  footnotes from the manufacturer PDF
- [Profiles](profiles.md) -- how model-specific registers are selected
- [Architecture overview](../architecture.md) -- hexagonal architecture and
  layer boundaries
