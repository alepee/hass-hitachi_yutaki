"""Utility functions for Hitachi Yutaki integration."""

from __future__ import annotations

import asyncio
import logging
import platform
import re

_LOGGER = logging.getLogger(__name__)


async def async_get_gateway_mac(ip_address: str) -> str | None:
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

        _LOGGER.debug("Pinging %s to populate ARP cache", ip_address)
        ping_process = await asyncio.create_subprocess_exec(
            *ping_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(ping_process.wait(), timeout=2.0)

        # Step 2: Read ARP table
        if system == "Windows":
            arp_cmd = ["arp", "-a", ip_address]
        else:  # Linux, macOS
            arp_cmd = ["arp", "-n", ip_address]

        _LOGGER.debug("Reading ARP table for %s", ip_address)
        arp_process = await asyncio.create_subprocess_exec(
            *arp_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            arp_process.communicate(), timeout=2.0
        )

        if arp_process.returncode != 0:
            _LOGGER.debug(
                "ARP command failed with return code %s: %s",
                arp_process.returncode,
                stderr.decode().strip(),
            )
            return None

        # Step 3: Parse MAC address
        # Matches formats: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
        mac_pattern = r"([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})"
        match = re.search(mac_pattern, stdout.decode())

        if match:
            # Normalize to uppercase with colons
            mac = match.group(0).replace("-", ":").upper()
            _LOGGER.debug("Found MAC address for %s: %s", ip_address, mac)
            return mac
        else:
            _LOGGER.debug("No MAC address found in ARP output for %s", ip_address)
            _LOGGER.debug("ARP output: %s", stdout.decode().strip())
            return None

    except TimeoutError:
        _LOGGER.debug("Timeout while trying to get MAC for %s", ip_address)
        return None
    except Exception as err:
        _LOGGER.debug(
            "Could not get MAC from ARP for %s: %s", ip_address, err, exc_info=True
        )
        return None
