"""F&F Fox cover platform implementation."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.cover import (
    DEVICE_CLASS_BLIND,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from . import FoxDevicesCoordinator
from .const import DOMAIN, POOLING_INTERVAL, SCHEMA_INPUT_UPDATE_POOLING
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switch entries."""

    device_coordinator: FoxDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        await device_coordinator.async_fetch_cover_devices()

        return device_coordinator.get_cover_devices()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="cover",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=(
            POOLING_INTERVAL if SCHEMA_INPUT_UPDATE_POOLING not in config_entry.options
            else config_entry.options.get(SCHEMA_INPUT_UPDATE_POOLING))),
    )

    await coordinator.async_config_entry_first_refresh()
    for idx, ent in enumerate(coordinator.data):
        entities.append(FoxBaseCover(coordinator, idx))
    async_add_entities(entities)
    return True


class FoxBaseCover(CoordinatorEntity, CoverEntity):
    """Fox base cover implementation."""

    def __init__(self, coordinator: DataUpdateCoordinator, idx: int) -> None:
        """Initialize object."""
        super().__init__(coordinator)
        self._idx = idx

    @property
    def name(self):
        """Return the name of the device."""
        return self.coordinator.data[self._idx].name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data[self._idx].is_available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device = self.coordinator.data[self._idx]
        return f"{device.mac_addr}-{device.device_platform}"

    @property
    def device_info(self):
        """Return device info."""
        return self.coordinator.data[self._idx].get_device_info()

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_BLIND

    @property
    def is_closed(self) -> bool | None:
        """Return is closed."""
        return self.coordinator.data[self._idx].is_cover_closed()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.coordinator.data[self._idx].async_open_cover()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.coordinator.data[self._idx].async_close_cover()
