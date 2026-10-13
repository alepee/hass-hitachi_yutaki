"""Home Assistant implementation of the domain clock port."""

from datetime import datetime
from time import monotonic

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


class HomeAssistantClock:
    """Keep elapsed time monotonic and civil dates in HA's configured timezone."""

    def __init__(self, hass: HomeAssistant | None = None) -> None:
        """Bind to the HA instance when available."""
        self._hass = hass

    def monotonic(self) -> float:
        """Return monotonic elapsed seconds."""
        return monotonic()

    def now(self) -> datetime:
        """Return timezone-aware civil time using HA's configured timezone."""
        zone = None
        if self._hass is not None:
            name = self._hass.config.time_zone
            if isinstance(name, str):
                zone = dt_util.get_time_zone(name)
        return dt_util.utcnow().astimezone(zone or dt_util.DEFAULT_TIME_ZONE)
