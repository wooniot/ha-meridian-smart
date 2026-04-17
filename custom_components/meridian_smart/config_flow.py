"""Config flow voor Meridian Smart — IP-adres invullen in HA UI."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_NAME
from .meridian_client import MeridianClient


class MeridianConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wizard om een Meridian apparaat toe te voegen via de UI."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Test verbinding
            client = MeridianClient(host)
            connected = await client.connect()
            await client.disconnect()

            if connected:
                # Gebruik zone_name als apparaatnaam als beschikbaar
                title = client.state.zone_name or user_input.get(CONF_NAME, DEFAULT_NAME)
                await self.async_set_unique_id(f"meridian_{host}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data={CONF_HOST: host})
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }),
            errors=errors,
        )
