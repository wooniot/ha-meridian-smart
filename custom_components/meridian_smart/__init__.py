"""Meridian Smart — Home Assistant integratie voor Meridian 218, 210, Ellipse en verwante producten."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_PRO_LICENSE
from .meridian_client import MeridianClient
from .license import check_pro_license

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stel de integratie in vanuit een config entry."""
    host = entry.data[CONF_HOST]
    pro_key = entry.data.get(CONF_PRO_LICENSE, "")

    client = MeridianClient(host)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    # Start persistente verbinding als achtergrondtaak zodat serial bekend is
    entry.async_create_background_task(
        hass,
        client.start_persistent(),
        f"meridian_smart_{host}",
    )

    # Pro licentie valideren (na korte wachttijd zodat serial bekend is)
    if pro_key:
        async def _validate_license():
            import asyncio as _asyncio
            await _asyncio.sleep(5)   # wacht tot verbinding + initial state binnen is
            serial = client.state.serial
            result = await check_pro_license(pro_key, serial)
            client.pro_enabled = result.get("valid", False)
            _LOGGER.info(
                "Meridian Pro licentie: valid=%s method=%s reason=%s",
                result.get("valid"),
                result.get("method"),
                result.get("reason"),
            )

        entry.async_create_background_task(hass, _validate_license(), f"meridian_license_{host}")
    else:
        client.pro_enabled = False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder de integratie."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: MeridianClient = hass.data[DOMAIN].pop(entry.entry_id)
        await client.disconnect()
    return unload_ok
