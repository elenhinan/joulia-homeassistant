"""Switches for Joulia EV Charging."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Joulia switches based on a config entry."""
    coordinator: JouliaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    for charger_id in coordinator.data:
        entities.append(JouliaCableLockSwitch(coordinator, charger_id))
        entities.append(JouliaChargingControlSwitch(coordinator, charger_id))

    async_add_entities(entities)


class JouliaCableLockSwitch(JouliaBaseEntity, SwitchEntity):
    """Switch to permanently lock or unlock the charging cable."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:lock"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_cable_lock"
        self._attr_name = "Cable Lock"

    @property
    def is_on(self) -> bool:
        """Return True if cable is permanently locked."""
        charger = self.charger_data.get("charger")
        if charger and charger.sockets:
            return charger.sockets[0].is_cable_locked_permanently
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the charging cable."""
        success = await self.coordinator.client.set_cable_lock(
            charger_id=self.charger_id,
            socket_id=1,
            locked=True,
        )
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to lock cable for charger %s", self.charger_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the charging cable."""
        success = await self.coordinator.client.set_cable_lock(
            charger_id=self.charger_id,
            socket_id=1,
            locked=False,
        )
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to unlock cable for charger %s", self.charger_id)


class JouliaChargingControlSwitch(JouliaBaseEntity, SwitchEntity):
    """Switch to remotely start or stop a charging transaction."""

    _attr_icon = "mdi:ev-plug-type2"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize the charging switch."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_charging_control"
        self._attr_name = "Charging"

    @property
    def is_on(self) -> bool:
        """Return True if the charger is actively charging."""
        charger = self.charger_data.get("charger")
        if charger and charger.sockets:
            return charger.sockets[0].status.lower() in ["charging", "preparing"]
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        sub = self.charger_data.get("subscription")
        sub_id = sub.id if sub else ""

        try:
            await self.coordinator.client.start_transaction(
                charger_id=self.charger_id,
                socket_id=1,
                subscription_id=sub_id,
            )
        except Exception as err:
            _LOGGER.warning("Could not start charging on %s: %s", self.charger_id, err)
        finally:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        sub = self.charger_data.get("subscription")
        sub_id = sub.id if sub else None

        try:
            await self.coordinator.client.stop_transaction(
                charger_id=self.charger_id,
                socket_id=1,
                subscription_id=sub_id,
            )
        except Exception as err:
            _LOGGER.warning("Could not stop charging on %s: %s", self.charger_id, err)
        finally:
            await self.coordinator.async_request_refresh()

