"""API interfaces for Hitachi Yutaki integration.

This module defines the abstract API client used by the application/domain layers.
Concrete protocol adapters (e.g., Modbus TCP) must implement this interface.

Note: At this stage, the integration still uses the legacy coordinator implementation.
This interface is scaffolding to enable a progressive refactor without behavior changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Dict


class HitachiApiError(Exception):
    """Base exception for API-related errors."""


@dataclass(frozen=True)
class CircuitCapabilities:
    heating: bool
    cooling: bool


@dataclass(frozen=True)
class GatewayCapabilities:
    dhw: bool
    pool: bool
    circuits: Dict[int, CircuitCapabilities]


class HitachiApiClient(ABC):
    """Abstract API client for communicating with a Hitachi heat pump.

    Implementations encapsulate the transport/protocol details (Modbus, TCP, ESPHome, ...)
    and expose a minimal, protocol-agnostic interface to the application/domain layers.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish the underlying connection if needed.

        Returns True if the connection is ready, False otherwise.
        Implementations should be idempotent.
        """

    @abstractmethod
    def close(self) -> None:
        """Close the underlying connection and release resources."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether the underlying transport is connected/ready."""

    @property
    @abstractmethod
    def capabilities(self) -> GatewayCapabilities:
        """Gateway-level feature support exposed by this adapter (protocol-agnostic)."""

    @abstractmethod
    def get_model_key(self) -> str | None:
        """Return a canonical, protocol-agnostic model key, e.g. "yutaki_s80".

        Implementations should hide any protocol-specific numeric IDs.
        """

    # Minimal register-like access methods kept generic so they can be mapped by adapters
    @abstractmethod
    def read_value(self, key: str, *, context: Mapping[str, Any] | None = None) -> int:
        """Read a value identified by a logical key.

        For Modbus, adapters will translate keys to register addresses. Other protocols
        may translate to native commands. Implementations should raise HitachiApiError
        on failures.
        """

    @abstractmethod
    def write_value(
        self, key: str, value: int, *, context: Mapping[str, Any] | None = None
    ) -> None:
        """Write a value identified by a logical key.

        For Modbus, adapters will translate keys to register addresses. Other protocols
        may translate to native commands. Implementations should raise HitachiApiError
        on failures.
        """
