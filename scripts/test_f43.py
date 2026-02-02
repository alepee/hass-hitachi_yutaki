#!/usr/bin/env python3
"""Test Modbus Function Code 43 (Device Identification) on ATW-MBS-02 gateway.

Run with: python scripts/test_f43.py
"""

from pymodbus.client import ModbusTcpClient

try:
    # pymodbus 3.x
    from pymodbus.pdu.mei_message import ReadDeviceInformationRequest
except ImportError:
    # pymodbus 2.x fallback
    from pymodbus.mei_message import ReadDeviceInformationRequest

GATEWAY_IP = "192.168.0.4"
SLAVE_ID = 1


def main():
    """Test Modbus F43 (Device Identification) on the gateway."""
    client = ModbusTcpClient(host=GATEWAY_IP, port=502, timeout=10)
    if not client.connect():
        print("❌ Connection failed")
        return

    print(f"✅ Connected to {GATEWAY_IP}\n")

    # 1. Input Registers 0-2 (current unique_id)
    print("=== Input Registers 0-2 ===")
    result = client.read_input_registers(address=0, count=3, device_id=SLAVE_ID)
    if not result.isError():
        print(
            f"Unique ID: {result.registers[0]}-{result.registers[1]}-{result.registers[2]}"
        )
        print(
            f"Hex:       {result.registers[0]:04X}:{result.registers[1]:04X}:{result.registers[2]:04X}"
        )
    else:
        print(f"❌ Error: {result}")

    # 2. F43 Basic (read_code=0x01)
    print("\n=== F43 Basic Identification ===")
    try:
        request = ReadDeviceInformationRequest(
            read_code=0x01, object_id=0x00, dev_id=SLAVE_ID
        )
        result = client.execute(False, request)
        if hasattr(result, "information") and result.information:
            print("✅ F43 SUPPORTED!")
            names = {0: "VendorName", 1: "ProductCode", 2: "Revision"}
            for obj_id, value in result.information.items():
                print(f"  {names.get(obj_id, f'Obj_{obj_id}')}: {value}")
        else:
            print(f"❌ F43 not supported or empty: {result}")
    except Exception as e:
        print(f"❌ F43 error: {e}")

    # 3. F43 Regular (read_code=0x02) - includes UserApplicationName
    print("\n=== F43 Regular Identification ===")
    try:
        request = ReadDeviceInformationRequest(
            read_code=0x02, object_id=0x00, dev_id=SLAVE_ID
        )
        result = client.execute(False, request)
        if hasattr(result, "information") and result.information:
            names = {
                0: "VendorName",
                1: "ProductCode",
                2: "Revision",
                3: "VendorUrl",
                4: "ProductName",
                5: "ModelName",
                6: "UserApplicationName",
            }
            for obj_id, value in result.information.items():
                marker = " ⭐" if obj_id == 6 else ""
                print(f"  {names.get(obj_id, f'Obj_{obj_id}')}: {value}{marker}")
        else:
            print(f"  No regular objects: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 4. F43 Extended (read_code=0x03) - vendor specific
    print("\n=== F43 Extended (Vendor-specific) ===")
    try:
        request = ReadDeviceInformationRequest(
            read_code=0x03, object_id=0x80, dev_id=SLAVE_ID
        )
        result = client.execute(False, request)
        if hasattr(result, "information") and result.information:
            for obj_id, value in result.information.items():
                print(f"  0x{obj_id:02X}: {value}")
        else:
            print(f"  No extended objects: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")

    client.close()
    print("\n✅ Done")


if __name__ == "__main__":
    main()
