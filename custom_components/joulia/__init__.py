"""The Joulia EV Charging Home Assistant integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import JouliaAuthError, JouliaClient
from .const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import JouliaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Joulia EV Charging from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    client = JouliaClient()

    try:
        await client.authenticate(username, password)
    except JouliaAuthError as err:
        _LOGGER.error("Authentication failed for Joulia account %s: %s", username, err)
        return False
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Joulia API: {err}") from err

    coordinator = JouliaDataUpdateCoordinator(
        hass=hass,
        client=client,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Joulia config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: JouliaDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)

