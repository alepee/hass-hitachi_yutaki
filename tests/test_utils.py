"""Test utility functions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hitachi_yutaki.utils import async_get_gateway_mac


@pytest.mark.asyncio
async def test_get_gateway_mac_success():
    """Test successful MAC address retrieval."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(return_value=0)

    mock_arp_process = AsyncMock()
    mock_arp_process.returncode = 0
    mock_arp_process.communicate = AsyncMock(
        return_value=(
            b"? (192.168.1.100) at aa:bb:cc:dd:ee:ff [ether] on eth0\n",
            b"",
        )
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[mock_ping_process, mock_arp_process],
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_get_gateway_mac_with_dash_format():
    """Test MAC address retrieval with dash format (Windows style)."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(return_value=0)

    mock_arp_process = AsyncMock()
    mock_arp_process.returncode = 0
    mock_arp_process.communicate = AsyncMock(
        return_value=(
            b"Interface: 192.168.1.1 --- 0x3\n"
            b"  Internet Address      Physical Address      Type\n"
            b"  192.168.1.100         aa-bb-cc-dd-ee-ff     dynamic\n",
            b"",
        )
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[mock_ping_process, mock_arp_process],
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_get_gateway_mac_not_found():
    """Test MAC address retrieval when IP not in ARP table."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(return_value=0)

    mock_arp_process = AsyncMock()
    mock_arp_process.returncode = 1
    mock_arp_process.communicate = AsyncMock(
        return_value=(
            b"? (192.168.1.100) -- no entry\n",
            b"",
        )
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[mock_ping_process, mock_arp_process],
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac is None


@pytest.mark.asyncio
async def test_get_gateway_mac_timeout():
    """Test MAC address retrieval timeout."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(side_effect=asyncio.TimeoutError)

    with patch(
        "asyncio.create_subprocess_exec",
        return_value=mock_ping_process,
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac is None


@pytest.mark.asyncio
async def test_get_gateway_mac_exception():
    """Test MAC address retrieval with exception."""
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=OSError("Network error"),
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac is None


@pytest.mark.asyncio
async def test_get_gateway_mac_invalid_output():
    """Test MAC address retrieval with invalid ARP output."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(return_value=0)

    mock_arp_process = AsyncMock()
    mock_arp_process.returncode = 0
    mock_arp_process.communicate = AsyncMock(
        return_value=(
            b"Invalid output without MAC address\n",
            b"",
        )
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[mock_ping_process, mock_arp_process],
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac is None


@pytest.mark.asyncio
async def test_get_gateway_mac_lowercase_conversion():
    """Test that lowercase MAC addresses are converted to uppercase."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(return_value=0)

    mock_arp_process = AsyncMock()
    mock_arp_process.returncode = 0
    mock_arp_process.communicate = AsyncMock(
        return_value=(
            b"? (192.168.1.100) at 11:22:33:44:55:66 [ether] on eth0\n",
            b"",
        )
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[mock_ping_process, mock_arp_process],
    ):
        mac = await async_get_gateway_mac("192.168.1.100")
        assert mac == "11:22:33:44:55:66"
        assert mac.isupper()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform_name", "expected_ping_cmd", "expected_arp_cmd"),
    [
        ("Linux", ["ping", "-c", "1", "-W", "1", "192.168.1.100"], ["arp", "-n", "192.168.1.100"]),
        ("Darwin", ["ping", "-c", "1", "-W", "1", "192.168.1.100"], ["arp", "-n", "192.168.1.100"]),
        ("Windows", ["ping", "-n", "1", "-w", "1000", "192.168.1.100"], ["arp", "-a", "192.168.1.100"]),
    ],
)
async def test_get_gateway_mac_platform_specific_commands(
    platform_name, expected_ping_cmd, expected_arp_cmd
):
    """Test that correct commands are used for each platform."""
    mock_ping_process = AsyncMock()
    mock_ping_process.wait = AsyncMock(return_value=0)

    mock_arp_process = AsyncMock()
    mock_arp_process.returncode = 0
    mock_arp_process.communicate = AsyncMock(
        return_value=(
            b"? (192.168.1.100) at aa:bb:cc:dd:ee:ff [ether] on eth0\n",
            b"",
        )
    )

    with (
        patch("platform.system", return_value=platform_name),
        patch(
            "asyncio.create_subprocess_exec",
            side_effect=[mock_ping_process, mock_arp_process],
        ) as mock_exec,
    ):
        await async_get_gateway_mac("192.168.1.100")

        # Check that correct commands were called
        calls = mock_exec.call_args_list
        assert len(calls) == 2

        # Check ping command
        ping_call_args = calls[0][0]
        assert list(ping_call_args) == expected_ping_cmd

        # Check arp command
        arp_call_args = calls[1][0]
        assert list(arp_call_args) == expected_arp_cmd
