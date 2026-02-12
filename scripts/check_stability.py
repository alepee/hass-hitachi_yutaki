#!/usr/bin/env python3
"""Check stability of proposed unique_id registers.

Reads registers 0-2 and 10-12 multiple times to verify they are stable.
"""

import time

from pymodbus.client import ModbusTcpClient

GATEWAY_IP = "192.168.0.4"
GATEWAY_PORT = 502
DEVICE_ID = 1
NUM_READS = 10
DELAY = 1  # seconds between reads


def main():
    """Run stability check: read registers multiple times and report consistency."""
    print("=" * 60)
    print("STABILITY CHECK FOR UNIQUE_ID REGISTERS")
    print("=" * 60)
    print(f"Gateway: {GATEWAY_IP}:{GATEWAY_PORT}")
    print(f"Reads: {NUM_READS} with {DELAY}s delay")
    print("=" * 60)

    client = ModbusTcpClient(host=GATEWAY_IP, port=GATEWAY_PORT, timeout=10)
    if not client.connect():
        print("❌ Connection failed!")
        return

    print("\n✅ Connected\n")

    # Store all readings
    input_readings = []
    holding_readings = []

    print("Reading registers...")
    for i in range(NUM_READS):
        print(f"\n--- Read {i + 1}/{NUM_READS} ---")

        # Read Input Registers 0-15
        try:
            result = client.read_input_registers(
                address=0, count=15, device_id=DEVICE_ID
            )
            if not result.isError():
                reading = {
                    "reg0": result.registers[0],
                    "reg1": result.registers[1],
                    "reg2": result.registers[2],
                    "reg8": result.registers[8],
                    "reg10": result.registers[10],
                    "reg11": result.registers[11],
                    "reg12": result.registers[12],
                }
                input_readings.append(reading)
                print(
                    f"  INPUT  0-2:   {reading['reg0']}-{reading['reg1']}-{reading['reg2']}"
                )
                print(f"  INPUT  8:     {reading['reg8']} (expected dynamic)")
                print(
                    f"  INPUT  10-12: {reading['reg10']}-{reading['reg11']}-{reading['reg12']}"
                )
            else:
                print(f"  ❌ Input error: {result}")
        except Exception as e:
            print(f"  ❌ Input exception: {e}")

        # Read Holding Registers 0-15
        try:
            result = client.read_holding_registers(
                address=0, count=15, device_id=DEVICE_ID
            )
            if not result.isError():
                reading = {
                    "reg0": result.registers[0],
                    "reg1": result.registers[1],
                    "reg2": result.registers[2],
                    "reg8": result.registers[8],
                    "reg10": result.registers[10],
                    "reg11": result.registers[11],
                    "reg12": result.registers[12],
                }
                holding_readings.append(reading)
                print(
                    f"  HOLD   0-2:   {reading['reg0']}-{reading['reg1']}-{reading['reg2']}"
                )
                print(f"  HOLD   8:     {reading['reg8']} (expected dynamic)")
                print(
                    f"  HOLD   10-12: {reading['reg10']}-{reading['reg11']}-{reading['reg12']}"
                )
            else:
                print(f"  ❌ Holding error: {result}")
        except Exception as e:
            print(f"  ❌ Holding exception: {e}")

        if i < NUM_READS - 1:
            time.sleep(DELAY)

    client.close()

    # Analyze stability
    print("\n" + "=" * 60)
    print("STABILITY ANALYSIS")
    print("=" * 60)

    def check_stability(readings, reg_name):
        values = [r[reg_name] for r in readings]
        unique = set(values)
        if len(unique) == 1:
            return f"✅ STABLE ({values[0]})"
        else:
            return f"❌ VARIES: {unique}"

    if input_readings:
        print("\nINPUT REGISTERS:")
        print(f"  Reg 0:  {check_stability(input_readings, 'reg0')}")
        print(f"  Reg 1:  {check_stability(input_readings, 'reg1')}")
        print(f"  Reg 2:  {check_stability(input_readings, 'reg2')}")
        print(f"  Reg 8:  {check_stability(input_readings, 'reg8')}")
        print(f"  Reg 10: {check_stability(input_readings, 'reg10')}")
        print(f"  Reg 11: {check_stability(input_readings, 'reg11')}")
        print(f"  Reg 12: {check_stability(input_readings, 'reg12')}")

    if holding_readings:
        print("\nHOLDING REGISTERS:")
        print(f"  Reg 0:  {check_stability(holding_readings, 'reg0')}")
        print(f"  Reg 1:  {check_stability(holding_readings, 'reg1')}")
        print(f"  Reg 2:  {check_stability(holding_readings, 'reg2')}")
        print(f"  Reg 8:  {check_stability(holding_readings, 'reg8')}")
        print(f"  Reg 10: {check_stability(holding_readings, 'reg10')}")
        print(f"  Reg 11: {check_stability(holding_readings, 'reg11')}")
        print(f"  Reg 12: {check_stability(holding_readings, 'reg12')}")

    # Final recommendation
    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)

    if input_readings:
        r = input_readings[0]
        proposed_id = f"{r['reg0']}-{r['reg1']}-{r['reg2']}-{r['reg10']}-{r['reg11']}-{r['reg12']}"
        print(f"\nProposed unique_id: hitachi_yutaki_{proposed_id}")


if __name__ == "__main__":
    main()
