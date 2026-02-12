#!/usr/bin/env python3
"""Comprehensive Modbus register scanner for ATW-MBS-02 gateway.

Scans all register types across the FULL address range (0-65535) to discover
undocumented registers that might be useful for unique identification.

Run with: python scripts/scan_registers.py
"""

import sys
import time

from pymodbus.client import ModbusTcpClient

# === CONFIGURATION ===
GATEWAY_IP = "192.168.0.4"
GATEWAY_PORT = 502
DEVICE_ID = 1
TIMEOUT = 10

# Scan parameters
CHUNK_SIZE = 50  # Registers per read (smaller = more reliable)
DELAY_BETWEEN_READS = 0.1  # Seconds between reads
# ======================


def progress_bar(current, total, width=40, prefix="", found=0, errors=0):
    """Display a progress bar."""
    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(
        f"\r  {prefix} [{bar}] {percent * 100:5.1f}% | Found: {found} | Err: {errors}"
    )
    sys.stdout.flush()


def scan_registers(client, read_func, start, end, results, reg_type):
    """Scan registers with progress feedback."""
    total = end - start
    error_count = 0

    addr = start
    while addr < end:
        count = min(CHUNK_SIZE, end - addr)
        progress = addr - start

        try:
            result = read_func(address=addr, count=count, device_id=DEVICE_ID)
            if not result.isError():
                for i, val in enumerate(result.registers):
                    if val != 0:
                        results.append((addr + i, val, f"0x{val:04X}"))
            else:
                error_count += 1
        except Exception:
            error_count += 1

        # Update progress every chunk
        progress_bar(
            progress, total, prefix=f"{addr:5d}", found=len(results), errors=error_count
        )

        time.sleep(DELAY_BETWEEN_READS)
        addr += CHUNK_SIZE

    progress_bar(total, total, prefix="Done ", found=len(results), errors=error_count)
    print()


def scan_coils_discrete(client, read_func, start, end, results, reg_type):
    """Scanner for coils and discrete inputs with progress."""
    total = end - start
    error_count = 0

    addr = start
    while addr < end:
        count = min(CHUNK_SIZE, end - addr)
        progress = addr - start

        try:
            result = read_func(address=addr, count=count, device_id=DEVICE_ID)
            if not result.isError():
                for i, val in enumerate(result.bits[:count]):
                    if val:
                        results.append((addr + i, 1, "ON"))
            else:
                error_count += 1
        except Exception:
            error_count += 1

        progress_bar(
            progress, total, prefix=f"{addr:5d}", found=len(results), errors=error_count
        )

        time.sleep(DELAY_BETWEEN_READS)
        addr += CHUNK_SIZE

    progress_bar(total, total, prefix="Done ", found=len(results), errors=error_count)
    print()


def format_duration(seconds):
    """Format seconds as mm:ss."""
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


def test_connection(client):
    """Test basic connectivity with known registers."""
    print("Testing connection with known registers...")

    # Test Input Register 0 (known to work from previous tests)
    try:
        result = client.read_input_registers(address=0, count=3, device_id=DEVICE_ID)
        if not result.isError():
            print(
                f"  ✅ Input Registers 0-2: {result.registers[0]}-{result.registers[1]}-{result.registers[2]}"
            )
            return True
        else:
            print(f"  ❌ Input Registers error: {result}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    return False


def main():
    start_time = time.time()

    print("=" * 60)
    print("ATW-MBS-02 FULL REGISTER SCAN")
    print("=" * 60)
    print(f"Gateway:    {GATEWAY_IP}:{GATEWAY_PORT}")
    print(f"Device ID:   {DEVICE_ID}")
    print("Range:      0 - 65535 (full Modbus address space)")
    print(f"Chunk size: {CHUNK_SIZE} registers")
    print(f"Delay:      {DELAY_BETWEEN_READS}s between reads")
    print("=" * 60)

    client = ModbusTcpClient(host=GATEWAY_IP, port=GATEWAY_PORT, timeout=TIMEOUT)
    if not client.connect():
        print("\n❌ Connection failed!")
        return

    print("\n✅ Connected to gateway\n")

    # Test connection first
    if not test_connection(client):
        print("\n❌ Connection test failed! Check network connectivity.")
        client.close()
        return

    print()
    all_results = {}

    # 1. Input Registers (FC 4) - Full range
    print("━" * 60)
    print("📖 INPUT REGISTERS (Function Code 4)")
    print("━" * 60)
    input_results = []
    scan_registers(
        client, client.read_input_registers, 0, 65536, input_results, "input"
    )
    all_results["input_registers"] = input_results
    elapsed = time.time() - start_time
    print(
        f"   ⏱️  Elapsed: {format_duration(elapsed)} | Total found: {len(input_results)}\n"
    )

    # 2. Holding Registers (FC 3) - Full range
    print("━" * 60)
    print("📝 HOLDING REGISTERS (Function Code 3)")
    print("━" * 60)
    holding_results = []
    scan_registers(
        client, client.read_holding_registers, 0, 65536, holding_results, "holding"
    )
    all_results["holding_registers"] = holding_results
    elapsed = time.time() - start_time
    print(
        f"   ⏱️  Elapsed: {format_duration(elapsed)} | Total found: {len(holding_results)}\n"
    )

    # 3. Coils (FC 1) - Full range
    print("━" * 60)
    print("🔘 COILS (Function Code 1)")
    print("━" * 60)
    coil_results = []
    scan_coils_discrete(client, client.read_coils, 0, 65536, coil_results, "coils")
    all_results["coils"] = coil_results
    elapsed = time.time() - start_time
    print(
        f"   ⏱️  Elapsed: {format_duration(elapsed)} | Total found: {len(coil_results)}\n"
    )

    # 4. Discrete Inputs (FC 2) - Full range
    print("━" * 60)
    print("📍 DISCRETE INPUTS (Function Code 2)")
    print("━" * 60)
    discrete_results = []
    scan_coils_discrete(
        client, client.read_discrete_inputs, 0, 65536, discrete_results, "discrete"
    )
    all_results["discrete_inputs"] = discrete_results
    elapsed = time.time() - start_time
    print(
        f"   ⏱️  Elapsed: {format_duration(elapsed)} | Total found: {len(discrete_results)}\n"
    )

    client.close()

    total_time = time.time() - start_time

    # Print summary
    print("\n" + "=" * 60)
    print("🏁 SCAN COMPLETE")
    print("=" * 60)
    print(f"Total time: {format_duration(total_time)}")
    print()

    for reg_type, results in all_results.items():
        count = len(results)
        icon = (
            "📖"
            if "input" in reg_type
            else "📝"
            if "holding" in reg_type
            else "🔘"
            if "coil" in reg_type
            else "📍"
        )
        print(f"{icon} {reg_type.replace('_', ' ').title()}: {count} non-zero values")

    # Detailed results
    print("\n" + "=" * 60)
    print("📋 DETAILED RESULTS")
    print("=" * 60)

    for reg_type, results in all_results.items():
        if results:
            print(
                f"\n### {reg_type.upper().replace('_', ' ')} ({len(results)} values) ###"
            )
            print(f"{'Address':<10} {'Decimal':<12} {'Hex':<10}")
            print("-" * 35)
            for addr, val, hex_val in sorted(results, key=lambda x: x[0]):
                print(f"{addr:<10} {val:<12} {hex_val:<10}")

    # Export to file
    output_file = "scan_results.txt"
    with open(output_file, "w") as f:
        f.write("ATW-MBS-02 Full Register Scan Results\n")
        f.write(f"Gateway: {GATEWAY_IP}:{GATEWAY_PORT}\n")
        f.write(f"Device ID: {DEVICE_ID}\n")
        f.write(f"Scan duration: {format_duration(total_time)}\n")
        f.write("=" * 60 + "\n\n")

        for reg_type, results in all_results.items():
            f.write(
                f"\n### {reg_type.upper().replace('_', ' ')} ({len(results)} values) ###\n"
            )
            if results:
                f.write(f"{'Address':<10} {'Decimal':<12} {'Hex':<10}\n")
                f.write("-" * 35 + "\n")
                for addr, val, hex_val in sorted(results, key=lambda x: x[0]):
                    f.write(f"{addr:<10} {val:<12} {hex_val:<10}\n")
            else:
                f.write("(no non-zero values found)\n")

    print(f"\n\n💾 Results exported to: {output_file}")

    # Highlight interesting findings
    print("\n" + "=" * 60)
    print("🔍 ANALYSIS HINTS")
    print("=" * 60)

    if all_results["input_registers"]:
        low_inputs = [r for r in all_results["input_registers"] if r[0] < 100]
        if low_inputs:
            print("\n⭐ Low Input Registers (0-99) - potential identifiers:")
            for addr, val, hex_val in low_inputs:
                print(f"   Register {addr}: {val} ({hex_val})")

    if all_results["holding_registers"]:
        version_regs = [
            r for r in all_results["holding_registers"] if 1080 <= r[0] <= 1100
        ]
        if version_regs:
            print("\n⭐ Version Registers (1080-1100):")
            for addr, val, hex_val in version_regs:
                print(f"   Register {addr}: {val} ({hex_val})")


if __name__ == "__main__":
    main()
