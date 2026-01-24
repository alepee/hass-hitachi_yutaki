#!/usr/bin/env python3
# ruff: noqa: T201
"""Manual test script for MAC address retrieval.

This script can be used to test the MAC address retrieval function
without running the full test suite.

Usage:
    python3 scripts/test_mac_retrieval.py <ip_address>

Example:
    python3 scripts/test_mac_retrieval.py 192.168.1.100

"""

import asyncio
import logging
from pathlib import Path
import sys

# Add custom_components to path
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

from hitachi_yutaki.utils import async_get_gateway_mac

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main():
    """Test MAC retrieval."""
    if len(sys.argv) < 2:
        print("Usage: python3 test_mac_retrieval.py <ip_address>")
        print("Example: python3 test_mac_retrieval.py 192.168.1.100")
        sys.exit(1)

    ip_address = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"Testing MAC address retrieval for: {ip_address}")
    print(f"{'='*60}\n")

    mac = await async_get_gateway_mac(ip_address)

    print(f"\n{'='*60}")
    if mac:
        print(f"✅ SUCCESS: MAC address found: {mac}")
    else:
        print("❌ FAILED: Could not retrieve MAC address")
    print(f"{'='*60}\n")

    return mac is not None


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
