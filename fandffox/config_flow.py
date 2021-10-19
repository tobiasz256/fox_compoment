"""Config flow for F&F Fox devices."""
from __future__ import annotations

import logging
from typing import Any

from foxrestapiclient.devices.fox_base_device import DeviceData, FoxBaseDevice
from foxrestapiclient.devices.fox_service_discovery import FoxServiceDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SCHEMA_INPUT_DEVICE_API_KEY, SCHEMA_INPUT_DEVICE_NAME_KEY

_LOGGER = logging.getLogger(__name__)

device_input_schema = vol.Schema(
    {
        vol.Optional(SCHEMA_INPUT_DEVICE_NAME_KEY): str,
        vol.Required(SCHEMA_INPUT_DEVICE_API_KEY, default="000"): str,
    }
)


async def validate_input(
    hass: HomeAssistant, device_data: DeviceData
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    errors = {}

    fetched_data = await FoxBaseDevice(device_data).async_fetch_device_info()
    if fetched_data is False:
        errors[SCHEMA_INPUT_DEVICE_API_KEY] = "wrong_api_key"
    return {}  # errors


async def serialize_dicovered_devices(
    hass: HomeAssistant, devices: list[DeviceData]
) -> dict[str, list[str]]:
    """Serialize discovered and configured devices."""
    serialized: dict[str, list[str]] = {"discovered_devices": []}
    for device in devices:
        serialized["discovered_devices"].append(device.__dict__)
    return serialized


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow."""

    VERSION = 1
    # Fox service discovery object
    fox_service_discovery = FoxServiceDiscovery()

    async def _async_do_discover_task(self):
        """Do service discovery task."""

        # Discover F&F Fox devices in local network
        await self.fox_service_discovery.async_discover_devices()

        # Continue the flow after show progress when the task is done.
        # To avoid a potential deadlock we create a new task that continues the flow.
        # The task must be completely done so the flow can await the task
        # if needed and get the task result.
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        # Do discover task
        self.hass.async_create_task(self._async_do_discover_task())
        return self.async_show_progress(
            step_id="discovering_finished", progress_action="task"
        )

    async def async_step_discovering_finished(
        self, user_input: dict[str, Any] | None = None
    ):
        """Discovering finished."""
        return self.async_show_progress_done(next_step_id="discovering_summary")

    async def async_step_discovering_summary(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle the discovering summary."""
        # Get discovered devices
        devices = self.fox_service_discovery.get_discovered_devices()
        # There is no devices, abort.
        if len(devices) <= 0:
            return self.async_abort(reason="no_devices_found")
        # If user input is not none, show configuration form.
        if "summary_displayed" in self.hass.data:
            self.hass.data.pop("summary_displayed")
            # Set current device index
            if "device_index" not in self.hass.data:
                self.hass.data.update({"device_index": 0})
            return self.async_show_form(
                step_id="configure_device",
                data_schema=device_input_schema,
                last_step=len(devices) == 1,
                description_placeholders={
                    "device_id": devices[0].mac_addr,
                    "device_host": devices[0].host,
                },
            )
        self.hass.data.update({"summary_displayed": True})
        return self.async_show_form(
            step_id="discovering_summary",
            description_placeholders={"devices_amount": len(devices)},
            last_step=False,
        )

    async def async_step_configure_device(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle configure device step."""
        errors = {}
        if user_input is not None:
            current_device: DeviceData = (
                self.fox_service_discovery.get_discovered_devices()[
                    self.hass.data["device_index"]
                ]
            )
            try:
                current_device.name = user_input[SCHEMA_INPUT_DEVICE_NAME_KEY]
                current_device.api_key = user_input[SCHEMA_INPUT_DEVICE_API_KEY]
            except KeyError:
                _LOGGER.info("Device name was not set. Default will be used.")
            errors = await validate_input(self.hass, current_device)
            if errors == {}:
                self.hass.data["device_index"] = self.hass.data["device_index"] + 1
                await self.async_set_unique_id(current_device.mac_addr)

        should_finish = len(self.fox_service_discovery.get_discovered_devices()) < (
            self.hass.data["device_index"] + 1
        )
        if should_finish is True:
            self.hass.data.pop("device_index")
            return self.async_create_entry(
                title="F&F Fox",
                data=await serialize_dicovered_devices(
                    self.hass, self.fox_service_discovery.get_discovered_devices()
                ),
            )
        is_last_step = len(self.fox_service_discovery.get_discovered_devices()) == (
            self.hass.data["device_index"] + 1
        )
        # Get next device to fill placeholders data
        next_device = self.fox_service_discovery.get_discovered_devices()[
            self.hass.data["device_index"]
        ]
        return self.async_show_form(
            step_id="configure_device",
            data_schema=device_input_schema,
            last_step=is_last_step,
            description_placeholders={
                "device_id": next_device.mac_addr,
                "device_host": next_device.host,
            },
            errors=errors,
        )
