"""Single command path from an entity to the gateway.

The API client reports each write as a ``bool`` (its port contract: a write
that the gateway did not apply returns ``False``; link errors never escape as
exceptions). Home Assistant expects a failed action to raise. This module is
the one place that translates between the two, so no entity has to remember to
check a return value, and a command made of several writes reports how far it
got.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from homeassistant.exceptions import HomeAssistantError

from ...const import DOMAIN

WRITE_FAILED = "write_failed"
COMMAND_PARTIALLY_APPLIED = "command_partially_applied"


class RefreshableCoordinator(Protocol):
    """The only coordinator capability a command needs."""

    async def async_request_refresh(self) -> None:
        """Re-read the device state."""


@dataclass(frozen=True, slots=True)
class CommandStep:
    """One write of a command.

    ``write`` returns ``False`` when the gateway did not apply the value. Any
    other result (``True``, or ``None`` for an action that is not a gateway
    write) counts as applied. ``name`` identifies the step in the error.
    """

    name: str
    write: Callable[[], Awaitable[bool | None]]


async def async_send_command(
    coordinator: RefreshableCoordinator,
    target: str | None,
    *steps: CommandStep,
) -> None:
    """Run ``steps`` in order, stopping at the first one the gateway refuses.

    The coordinator is refreshed whatever the outcome, so the entity shows the
    real device state rather than the requested one. A refused step raises a
    translated :class:`HomeAssistantError`; when earlier steps were applied,
    the error says so (``command_partially_applied``) instead of presenting a
    half-applied command as a plain failure.
    """
    applied: list[str] = []
    failed: str | None = None
    try:
        for step in steps:
            if await step.write() is False:
                failed = step.name
                break
            applied.append(step.name)
    finally:
        await coordinator.async_request_refresh()

    if failed is None:
        return

    placeholders = {"entity": target or "", "step": failed}
    if applied:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=COMMAND_PARTIALLY_APPLIED,
            translation_placeholders={**placeholders, "applied": ", ".join(applied)},
        )
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=WRITE_FAILED,
        translation_placeholders=placeholders,
    )
