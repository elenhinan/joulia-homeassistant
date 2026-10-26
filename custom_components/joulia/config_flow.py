"""Config flow for Joulia EV Charging integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .client import JouliaAuthError, JouliaClient
from .const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class JouliaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Joulia EV Charging."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            client = JouliaClient()
            try:
                tokens = await client.authenticate(username, password)
            except JouliaAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected exception connecting to Joulia API: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(tokens.user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Joulia ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return JouliaOptionsFlowHandler()


class JouliaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Joulia."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current_scan_interval,
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
