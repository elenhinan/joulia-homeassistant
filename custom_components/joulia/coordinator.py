"""DataUpdateCoordinator for Joulia EV Charging."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ActiveSession, ChargerDetails, JouliaApiError, JouliaClient, Subscription
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class JouliaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Class to manage fetching Joulia data from the cloud API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: JouliaClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all subscriptions, chargers, and active session details."""
        try:
            subscriptions: list[Subscription] = await self.client.get_subscriptions()
            data: Dict[str, Dict[str, Any]] = {}

            for sub in subscriptions:
                charger_id = sub.charger_id
                if not charger_id:
                    continue

                try:
                    charger_details: ChargerDetails = await self.client.get_charger_details(charger_id)
                except JouliaApiError as err:
                    _LOGGER.warning("Failed to fetch charger %s: %s", charger_id, err)
                    continue

                # Fetch active session for primary socket
                session: ActiveSession
                try:
                    session = await self.client.get_session(charger_id, socket_id=1)
                except Exception as err:
                    _LOGGER.debug("Could not fetch active session for %s: %s", charger_id, err)
                    session = ActiveSession(start_time=None, total_kwh=0.0, current_kw=None)

                data[charger_id] = {
                    "subscription": sub,
                    "charger": charger_details,
                    "session": session,
                }

            if not data:
                _LOGGER.warning("No chargers found in Joulia account subscriptions.")

            return data

        except JouliaApiError as err:
            raise UpdateFailed(f"Error communicating with Joulia API: {err}") from err

