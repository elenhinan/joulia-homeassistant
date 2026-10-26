"""Buttons for Joulia EV Charging."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import JouliaDataUpdateCoordinator
from .const import DOMAIN
from .sensor import JouliaBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joulia buttons based on a config entry."""
    coordinator: JouliaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = []

    for charger_id in coordinator.data:
        entities.append(JouliaRebootButton(coordinator, charger_id))

    async_add_entities(entities)


class JouliaRebootButton(JouliaBaseEntity, ButtonEntity):
    """Button to remotely reboot the charger hardware."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_reboot"
        self._attr_name = "Reboot Charger"

    async def async_press(self) -> None:
        """Handle button press to reboot charger."""
        success = await self.coordinator.client.reboot_charger(self.charger_id)
        if success:
            _LOGGER.info("Successfully sent reboot command to charger %s", self.charger_id)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to send reboot command to charger %s", self.charger_id)

