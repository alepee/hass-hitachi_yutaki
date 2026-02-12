#!/usr/bin/env python3
"""Annotated Modbus register scanner for Hitachi ATW gateways.

Supports ATW-MBS-02 and HC-A(16/64)MB gateways with auto-detection.
Scans relevant address ranges, annotates known registers with their name
and deserialized value, and outputs structured results to stdout.

Progress and status messages go to stderr so results can be redirected:
    make scan > scan_results.txt

Run with: uv run python scripts/scan_gateway.py --help
"""

from __future__ import annotations

import argparse
from enum import StrEnum
import importlib.util
from pathlib import Path
import sys
import time
import types

from pymodbus.client import ModbusTcpClient

# ---------------------------------------------------------------------------
# Bootstrap: load register map modules without importing the full HA package.
#
# The register files depend on:
#   - custom_components.hitachi_yutaki.const (a few constants + OTCCalculationMethod)
#   - custom_components.hitachi_yutaki.api.modbus.registers (RegisterDefinition, etc.)
#
# We build a minimal const stub, then load the files directly with importlib.
# ---------------------------------------------------------------------------

_INTEGRATION_ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "hitachi_yutaki"
_REGISTERS_DIR = _INTEGRATION_ROOT / "api" / "modbus" / "registers"


def _load_module_from_file(name: str, filepath: Path, package: str | None = None) -> types.ModuleType:
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(name, filepath, submodule_search_locations=[])
    if spec is None or spec.loader is None:
        msg = f"Cannot load module from {filepath}"
        raise ImportError(msg)
    mod = importlib.util.module_from_spec(spec)
    if package:
        mod.__package__ = package
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _bootstrap_register_maps():
    """Load AtwMbs02RegisterMap and HcAMbRegisterMap without HA dependencies."""
    # 1. Build a minimal const module with only what the register files need
    const_mod = types.ModuleType("custom_components.hitachi_yutaki.const")

    class OTCCalculationMethod(StrEnum):
        DISABLED = "disabled"
        POINTS = "points"
        GRADIENT = "gradient"
        FIX = "fix"

    const_mod.CIRCUIT_PRIMARY_ID = 1  # type: ignore[attr-defined]
    const_mod.CIRCUIT_SECONDARY_ID = 2  # type: ignore[attr-defined]
    const_mod.CIRCUIT_MODE_HEATING = "heating"  # type: ignore[attr-defined]
    const_mod.CIRCUIT_MODE_COOLING = "cooling"  # type: ignore[attr-defined]
    const_mod.OTCCalculationMethod = OTCCalculationMethod  # type: ignore[attr-defined]

    # Install fake package hierarchy so relative imports resolve
    for mod_name in [
        "custom_components",
        "custom_components.hitachi_yutaki",
        "custom_components.hitachi_yutaki.api",
        "custom_components.hitachi_yutaki.api.modbus",
    ]:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = []  # type: ignore[attr-defined]
        pkg.__package__ = mod_name
        sys.modules.setdefault(mod_name, pkg)

    sys.modules["custom_components.hitachi_yutaki.const"] = const_mod

    # 2. Load registers/__init__.py (pure Python, no HA deps)
    reg_pkg_name = "custom_components.hitachi_yutaki.api.modbus.registers"
    reg_init = _REGISTERS_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        reg_pkg_name,
        reg_init,
        submodule_search_locations=[str(_REGISTERS_DIR)],
    )
    reg_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    reg_mod.__package__ = reg_pkg_name
    sys.modules[reg_pkg_name] = reg_mod
    spec.loader.exec_module(reg_mod)  # type: ignore[union-attr]

    # 3. Load the two gateway register files
    atw_mod = _load_module_from_file(
        f"{reg_pkg_name}.atw_mbs_02",
        _REGISTERS_DIR / "atw_mbs_02.py",
        package=reg_pkg_name,
    )
    hc_mod = _load_module_from_file(
        f"{reg_pkg_name}.hc_a_mb",
        _REGISTERS_DIR / "hc_a_mb.py",
        package=reg_pkg_name,
    )

    return atw_mod.AtwMbs02RegisterMap, hc_mod.HcAMbRegisterMap


AtwMbs02RegisterMap, HcAMbRegisterMap = _bootstrap_register_maps()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GATEWAY_ATW_MBS_02 = "atw-mbs-02"
GATEWAY_HC_A_MB = "hc-a-mb"

RANGE_TARGETED = "targeted"
RANGE_FULL = "full"
RANGE_EXHAUSTIVE = "exhaustive"

# Sentinel value: 0xFFFF means "not connected" / "sensor error" / "unused"
EMPTY_REGISTER = 0xFFFF

# Detection registers
ATW_MBS_02_UNIT_MODEL_ADDR = 1218
HC_A_MB_UNIT_MODEL_OFFSET = 162  # base + 162

# ---------------------------------------------------------------------------
# System configuration bitmasks (register system_config)
# Used by both ATW-MBS-02 (reg 1089) and HC-A-MB (offset 140)
# ---------------------------------------------------------------------------
SYSTEM_CONFIG_BITS = [
    (0x0001, "Circuit 1 Heating"),
    (0x0002, "Circuit 2 Heating"),
    (0x0004, "Circuit 1 Cooling"),
    (0x0008, "Circuit 2 Cooling"),
    (0x0010, "DHW"),
    (0x0020, "Pool"),
    (0x0040, "Circuit 1 Thermostat"),
    (0x0080, "Circuit 2 Thermostat"),
    (0x0100, "Circuit 1 Wireless"),
    (0x0200, "Circuit 2 Wireless"),
    (0x0400, "Circuit 1 Wireless Temp"),
    (0x0800, "Circuit 2 Wireless Temp"),
]

SYSTEM_STATUS_BITS = [
    (0x0001, "Defrost"),
    (0x0002, "Solar"),
    (0x0004, "Pump 1"),
    (0x0008, "Pump 2"),
    (0x0010, "Pump 3"),
    (0x0020, "Compressor"),
    (0x0040, "Boiler"),
    (0x0080, "DHW Heater"),
    (0x0100, "Space Heater"),
    (0x0200, "Smart Function"),
]

UNIT_MODEL_NAMES = {
    0: "Yutaki S",
    1: "Yutaki S Combi",
    2: "Yutaki S80",
    3: "Yutaki M",
    4: "Yutaki SC Lite (HC-A-MB only)",
    5: "Yutampo R32 (HC-A-MB only)",
    6: "YCC (HC-A-MB only)",
}

OPERATION_STATES = {
    0: "Off",
    1: "Cool (demand off)",
    2: "Cool (thermo off)",
    3: "Cool (thermo on)",
    4: "Heat (demand off)",
    5: "Heat (thermo off)",
    6: "Heat (thermo on)",
    7: "DHW (off)",
    8: "DHW (on)",
    9: "Pool (off)",
    10: "Pool (on)",
    11: "Alarm",
}

UNIT_MODES = {0: "Cool", 1: "Heat", 2: "Auto"}

# ---------------------------------------------------------------------------
# Scan ranges per gateway type
#   (function_code, start, end_exclusive, label)
#   FC1 = Coils, FC2 = Discrete Inputs, FC3 = Holding Registers, FC4 = Input Registers
# ---------------------------------------------------------------------------

# targeted: known register zones with discovery margin (~1s)
RANGES_ATW_MBS_02_TARGETED = [
    (4, 0, 100, "Input Registers (FC4) 0-99"),
    (3, 1000, 1300, "Holding Registers (FC3) 1000-1299"),
]

RANGES_HC_A_MB_TARGETED_TEMPLATE = [
    (3, 0, 20, "Outdoor Unit Registers 0-19"),
    (3, 50, 100, "Control Registers 50-99"),
    (3, 100, 200, "Status Registers 100-199"),
]

# full: FC3 + FC4 over 0-65535 (~45s)
RANGES_FULL = [
    (4, 0, 65536, "Input Registers (FC4) 0-65535"),
    (3, 0, 65536, "Holding Registers (FC3) 0-65535"),
]

# exhaustive: FC1-FC4 over 0-65535 (~3min)
RANGES_EXHAUSTIVE = [
    (4, 0, 65536, "Input Registers (FC4) 0-65535"),
    (3, 0, 65536, "Holding Registers (FC3) 0-65535"),
    (1, 0, 65536, "Coils (FC1) 0-65535"),
    (2, 0, 65536, "Discrete Inputs (FC2) 0-65535"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def info(msg: str) -> None:
    """Print an informational message to stderr."""
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def progress_bar(
    current: int,
    total: int,
    *,
    width: int = 40,
    prefix: str = "",
    found: int = 0,
    errors: int = 0,
) -> None:
    """Display a progress bar on stderr."""
    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    sys.stderr.write(
        f"\r  {prefix} [{bar}] {percent * 100:5.1f}% | Found: {found} | Err: {errors}"
    )
    sys.stderr.flush()


def format_duration(seconds: float) -> str:
    """Format seconds as mm:ss."""
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


# ---------------------------------------------------------------------------
# Lookup table builder
# ---------------------------------------------------------------------------


def build_lookup(register_map) -> dict[int, list[tuple[str, object]]]:
    """Build {address -> [(register_name, deserializer), ...]} from a register map.

    A single address may appear multiple times (e.g. operation_state and
    operation_state_code share the same address with different deserializers).
    We keep all of them so annotations are exhaustive.
    """
    lookup: dict[int, list[tuple[str, object]]] = {}
    for name, reg_def in register_map.all_registers.items():
        entry = (name, reg_def.deserializer)
        lookup.setdefault(reg_def.address, []).append(entry)
        # Also index write_address so CONTROL-only registers are found
        if reg_def.write_address is not None and reg_def.write_address != reg_def.address:
            lookup.setdefault(reg_def.write_address, []).append(
                (f"{name} [write]", reg_def.serializer)
            )
    return lookup


# ---------------------------------------------------------------------------
# Connection & detection
# ---------------------------------------------------------------------------


def test_connection(client: ModbusTcpClient, device_id: int) -> bool:
    """Test basic connectivity by reading input register 0."""
    try:
        result = client.read_input_registers(address=0, count=1, device_id=device_id)
        if not result.isError():
            return True
    except Exception:
        pass
    # Fallback: try holding register 0
    try:
        result = client.read_holding_registers(address=0, count=1, device_id=device_id)
        return not result.isError()
    except Exception:
        return False


def detect_gateway(client: ModbusTcpClient, device_id: int, unit_id: int) -> str | None:
    """Auto-detect gateway type by probing known registers.

    Returns GATEWAY_ATW_MBS_02, GATEWAY_HC_A_MB, or None.
    """
    # Try ATW-MBS-02: unit_model at holding register 1218
    try:
        result = client.read_holding_registers(
            address=ATW_MBS_02_UNIT_MODEL_ADDR, count=1, device_id=device_id
        )
        if not result.isError() and 0 <= result.registers[0] <= 3:
            return GATEWAY_ATW_MBS_02
    except Exception:
        pass

    # Try HC-A-MB: unit_model at base + 162
    hc_addr = 5000 + (unit_id * 200) + HC_A_MB_UNIT_MODEL_OFFSET
    try:
        result = client.read_holding_registers(address=hc_addr, count=1, device_id=device_id)
        if not result.isError() and 0 <= result.registers[0] <= 6:
            return GATEWAY_HC_A_MB
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _scan_loop(
    client: ModbusTcpClient,
    device_id: int,
    read_func,
    start: int,
    end: int,
    label: str,
    chunk_size: int,
    delay: float,
    extract_values,
) -> list[tuple[int, int]]:
    """Run a scan loop for any Modbus function code."""
    results: list[tuple[int, int]] = []
    total = end - start
    error_count = 0
    addr = start

    while addr < end:
        count = min(chunk_size, end - addr)
        try:
            resp = read_func(address=addr, count=count, device_id=device_id)
            if not resp.isError():
                for i, val in extract_values(resp, count):
                    if val != 0:
                        results.append((addr + i, val))
            else:
                error_count += 1
        except Exception:
            error_count += 1

        progress_bar(
            addr - start,
            total,
            prefix=f"{label} {addr:5d}",
            found=len(results),
            errors=error_count,
        )
        time.sleep(delay)
        addr += chunk_size

    progress_bar(
        total,
        total,
        prefix=f"{label} Done ",
        found=len(results),
        errors=error_count,
    )
    sys.stderr.write("\n")
    return results


def _extract_registers(resp, _count: int):
    """Extract (index, value) pairs from a register response."""
    return enumerate(resp.registers)


def _extract_bits(resp, count: int):
    """Extract (index, value) pairs from a coil/discrete response."""
    return ((i, int(v)) for i, v in enumerate(resp.bits[:count]))


def scan_range(
    client: ModbusTcpClient,
    device_id: int,
    fc: int,
    start: int,
    end: int,
    label: str,
    chunk_size: int,
    delay: float,
) -> list[tuple[int, int]]:
    """Scan a Modbus register range and return non-zero (address, raw_value) pairs."""
    fc_map = {
        1: (client.read_coils, _extract_bits),
        2: (client.read_discrete_inputs, _extract_bits),
        3: (client.read_holding_registers, _extract_registers),
        4: (client.read_input_registers, _extract_registers),
    }
    if fc not in fc_map:
        msg = f"Unsupported function code: {fc}"
        raise ValueError(msg)
    read_func, extractor = fc_map[fc]
    return _scan_loop(client, device_id, read_func, start, end, label, chunk_size, delay, extractor)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_annotation(
    address: int, raw: int, lookup: dict[int, list[tuple[str, object]]]
) -> tuple[str, str]:
    """Return (register_name, deserialized_value) for an address.

    If multiple names map to the same address, join them with " / ".
    """
    entries = lookup.get(address)
    if not entries:
        return ("", "")

    names = []
    deserialized_parts = []
    for name, deser in entries:
        names.append(name)
        if deser is not None:
            try:
                deserialized_parts.append(str(deser(raw)))
            except Exception:
                deserialized_parts.append("?")

    reg_name = " / ".join(names)
    deser_str = " / ".join(deserialized_parts) if deserialized_parts else ""
    return (reg_name, deser_str)


def print_results(
    results: list[tuple[int, int]],
    lookup: dict[int, list[tuple[str, object]]],
    label: str,
) -> tuple[int, int]:
    """Print a block of scan results to stdout, skipping 0xFFFF registers.

    Returns (printed_count, skipped_empty_count).
    """
    visible = [(addr, raw) for addr, raw in results if raw != EMPTY_REGISTER]
    skipped = len(results) - len(visible)
    if not visible:
        if skipped:
            print(f"\n### {label} ({skipped} empty registers skipped) ###")
        return (0, skipped)
    count_label = f"{len(visible)} registers"
    if skipped:
        count_label += f", {skipped} empty skipped"
    print(f"\n### {label} ({count_label}) ###")
    print(f"{'Address':<8} {'Dec':>7} {'Hex':>8}   {'Register':<55} {'Deserialized'}")
    print("-" * 100)
    for addr, raw in sorted(visible, key=lambda x: x[0]):
        reg_name, deser_str = format_annotation(addr, raw, lookup)
        print(f"{addr:<8} {raw:>7} {raw:#06x}   {reg_name:<55} {deser_str}")
    return (len(visible), skipped)


def _decode_bitmask(value: int, bits: list[tuple[int, str]]) -> list[str]:
    """Decode a bitmask into a list of active flag names."""
    return [name for mask, name in bits if value & mask]


def print_system_recap(all_results: list[tuple[str, list[tuple[int, int]]]], gateway_type: str) -> None:
    """Print a human-readable system configuration recap."""
    # Collect all results into a flat address->value dict
    reg_values: dict[int, int] = {
        addr: raw
        for _, results in all_results
        for addr, raw in results
        if raw != EMPTY_REGISTER
    }

    # Determine addresses based on gateway type
    if gateway_type == GATEWAY_ATW_MBS_02:
        addr_model = 1218
        addr_config = 1089
        addr_status = 1222
        addr_state = 1094
        addr_op_state = 1090
        addr_mode = 1001
        addr_outdoor = 1091
        addr_inlet = 1092
        addr_outlet = 1093
        addr_target = 1219
        addr_flow = 1220
        addr_power = 1098
    else:
        # HC-A-MB addresses would need unit_id, skip recap for now
        print("\n" + "=" * 100)
        print("SYSTEM RECAP (HC-A-MB: use targeted mode for detailed recap)")
        print("=" * 100)
        return

    print("\n" + "=" * 100)
    print("SYSTEM CONFIGURATION RECAP")
    print("=" * 100)

    # Unit model
    model_raw = reg_values.get(addr_model)
    if model_raw is not None:
        print(f"  Unit model:       {UNIT_MODEL_NAMES.get(model_raw, f'unknown ({model_raw})')}")

    # Operation mode
    mode_raw = reg_values.get(addr_mode)
    if mode_raw is not None:
        print(f"  Unit mode:        {UNIT_MODES.get(mode_raw, f'unknown ({mode_raw})')}")

    # Operation state
    op_state = reg_values.get(addr_op_state)
    if op_state is not None:
        print(f"  Operation state:  {OPERATION_STATES.get(op_state, f'unknown ({op_state})')}")

    # System state
    state_raw = reg_values.get(addr_state)
    if state_raw is not None:
        state_names = {0: "Synchronized", 1: "Desynchronized", 2: "Initializing"}
        print(f"  System state:     {state_names.get(state_raw, f'unknown ({state_raw})')}")

    # Temperatures & measurements
    print()
    outdoor = reg_values.get(addr_outdoor)
    if outdoor is not None:
        outdoor = outdoor - 65536 if outdoor > 32767 else outdoor
        print(f"  Outdoor temp:     {outdoor} C")
    inlet = reg_values.get(addr_inlet)
    if inlet is not None:
        inlet = inlet - 65536 if inlet > 32767 else inlet
        print(f"  Water inlet:      {inlet} C")
    outlet = reg_values.get(addr_outlet)
    if outlet is not None:
        outlet = outlet - 65536 if outlet > 32767 else outlet
        print(f"  Water outlet:     {outlet} C")
    target = reg_values.get(addr_target)
    if target is not None:
        target = target - 65536 if target > 32767 else target
        print(f"  Water target:     {target} C")
    flow = reg_values.get(addr_flow)
    if flow is not None:
        print(f"  Water flow:       {flow / 10.0} m3/h")
    power = reg_values.get(addr_power)
    if power is not None:
        print(f"  Power cons.:      {power} W")

    # System config bitmask — dedicated table
    config_raw = reg_values.get(addr_config)
    if config_raw is not None:
        print()
        print(f"  System config register: 0x{config_raw:04X} ({config_raw})")
        print(f"  {'Feature':<30} {'Status'}")
        print(f"  {'-' * 30} {'-' * 8}")
        for mask, name in SYSTEM_CONFIG_BITS:
            status = "ON" if config_raw & mask else "-"
            print(f"  {name:<30} {status}")

    # System status bitmask — dedicated table
    status_raw = reg_values.get(addr_status)
    if status_raw is not None:
        print()
        print(f"  System status register: 0x{status_raw:04X} ({status_raw})")
        print(f"  {'Component':<30} {'Active'}")
        print(f"  {'-' * 30} {'-' * 8}")
        for mask, name in SYSTEM_STATUS_BITS:
            active = "ON" if status_raw & mask else "-"
            print(f"  {name:<30} {active}")

    print("=" * 100)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Annotated Modbus register scanner for Hitachi ATW gateways.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
scan ranges (--range):
  targeted     Known register zones + margin (~1s)
  full         FC3 + FC4 over 0-65535 (~45s)
  exhaustive   FC1-FC4 over 0-65535 (~3min)

examples:
  %(prog)s                              # scan with defaults (auto-detect, targeted)
  %(prog)s --range full                 # full FC3+FC4 scan
  %(prog)s --host 10.0.0.5 --gateway hc-a-mb --unit-id 1
  %(prog)s > scan_results.txt           # redirect results, progress on stderr
""",
    )
    parser.add_argument("--host", default="192.168.0.4", help="Gateway IP (default: 192.168.0.4)")
    parser.add_argument("--port", type=int, default=502, help="Gateway Modbus port (default: 502)")
    parser.add_argument("--slave", type=int, default=1, help="Modbus slave/device ID (default: 1)")
    parser.add_argument(
        "--gateway",
        choices=[GATEWAY_ATW_MBS_02, GATEWAY_HC_A_MB],
        default=None,
        help="Gateway type (default: auto-detect)",
    )
    parser.add_argument(
        "--unit-id",
        type=int,
        default=0,
        help="HC-A-MB unit ID, determines address block (default: 0)",
    )
    parser.add_argument(
        "--range",
        choices=[RANGE_TARGETED, RANGE_FULL, RANGE_EXHAUSTIVE],
        default=RANGE_TARGETED,
        help="Scan range: targeted (default), full (FC3+FC4 0-65535), exhaustive (FC1-FC4 0-65535)",
    )
    parser.add_argument("--timeout", type=int, default=10, help="Connection timeout in seconds (default: 10)")
    parser.add_argument("--chunk-size", type=int, default=50, help="Registers per read (default: 50)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between reads in seconds (default: 0.1)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    start_time = time.time()

    # -- Header (stdout) --
    print("=" * 100)
    print("HITACHI GATEWAY MODBUS REGISTER SCAN")
    print("=" * 100)
    print(f"Host:       {args.host}:{args.port}")
    print(f"Slave ID:   {args.slave}")
    print(f"Gateway:    {args.gateway or 'auto-detect'}")
    if args.gateway == GATEWAY_HC_A_MB or args.gateway is None:
        print(f"Unit ID:    {args.unit_id}")
    print(f"Range:      {args.range}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Delay:      {args.delay}s")
    print("=" * 100)

    # -- Connect --
    info(f"\nConnecting to {args.host}:{args.port} ...")
    client = ModbusTcpClient(host=args.host, port=args.port, timeout=args.timeout)
    if not client.connect():
        info("ERROR: Connection failed!")
        return 1

    info("Connected.")

    # -- Test connection --
    info("Testing connectivity ...")
    if not test_connection(client, args.slave):
        info("ERROR: Connection test failed — no readable registers. Check host/slave ID.")
        client.close()
        return 1
    info("Connection OK.\n")

    # -- Detect gateway --
    gateway_type = args.gateway
    if gateway_type is None:
        info("Auto-detecting gateway type ...")
        gateway_type = detect_gateway(client, args.slave, args.unit_id)
        if gateway_type is None:
            info(
                "ERROR: Could not auto-detect gateway type.\n"
                "  Neither ATW-MBS-02 nor HC-A-MB responded with a valid unit_model.\n"
                "  Try forcing the type with --gateway atw-mbs-02 or --gateway hc-a-mb"
            )
            client.close()
            return 1
        info(f"Detected: {gateway_type}\n")
    else:
        info(f"Gateway forced: {gateway_type}\n")

    print(f"Detected:   {gateway_type}")

    # -- Build register map & lookup --
    if gateway_type == GATEWAY_ATW_MBS_02:
        register_map = AtwMbs02RegisterMap()
    else:
        register_map = HcAMbRegisterMap(unit_id=args.unit_id)

    # -- Determine scan ranges --
    if args.range == RANGE_FULL:
        scan_ranges = RANGES_FULL
    elif args.range == RANGE_EXHAUSTIVE:
        scan_ranges = RANGES_EXHAUSTIVE
    elif gateway_type == GATEWAY_ATW_MBS_02:
        scan_ranges = RANGES_ATW_MBS_02_TARGETED
    else:
        base = 5000 + (args.unit_id * 200)
        scan_ranges = [
            (fc, base + offset_start, base + offset_end, label)
            for fc, offset_start, offset_end, label in RANGES_HC_A_MB_TARGETED_TEMPLATE
        ]

    lookup = build_lookup(register_map)

    # -- Scan --
    all_results: list[tuple[str, list[tuple[int, int]]]] = []
    total_found = 0

    info("")
    for fc, range_start, range_end, label in scan_ranges:
        fc_label = f"FC{fc}"
        full_label = f"{fc_label} {label}"
        info(f"Scanning {full_label} ({range_start}-{range_end - 1}) ...")
        results = scan_range(
            client, args.slave, fc, range_start, range_end, fc_label, args.chunk_size, args.delay
        )
        all_results.append((full_label, results))
        total_found += len(results)

    client.close()
    total_time = time.time() - start_time

    # -- Output results (stdout) --
    total_printed = 0
    total_empty = 0
    for label, results in all_results:
        printed, skipped = print_results(results, lookup, label)
        total_printed += printed
        total_empty += skipped

    # -- System recap --
    print_system_recap(all_results, gateway_type)

    # -- Summary --
    print("\n" + "=" * 100)
    print("SCAN COMPLETE")
    print("=" * 100)
    print(f"Duration:        {format_duration(total_time)}")
    print(f"Gateway:         {gateway_type}")
    print(f"Total non-zero:  {total_found} ({total_printed} with data, {total_empty} empty/0xFFFF)")
    for label, results in all_results:
        visible = sum(1 for _, v in results if v != EMPTY_REGISTER)
        empty = len(results) - visible
        line = f"  {label}: {visible}"
        if empty:
            line += f" (+{empty} empty)"
        print(line)

    # Count annotated vs unknown (excluding empty)
    annotated = 0
    unknown = 0
    for _, results in all_results:
        for addr, raw in results:
            if raw == EMPTY_REGISTER:
                continue
            if addr in lookup:
                annotated += 1
            else:
                unknown += 1
    print(f"Annotated:       {annotated}")
    print(f"Unknown:         {unknown}")
    print("=" * 100)

    info(f"\nDone in {format_duration(total_time)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
