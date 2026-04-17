"""Meridian Smart — Home Assistant integratie voor Meridian 218, 210, Ellipse en verwante producten."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .meridian_client import MeridianClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stel de integratie in vanuit een config entry."""
    host = entry.data[CONF_HOST]
    client = MeridianClient(host)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    # Start persistente verbinding als achtergrondtaak
    entry.async_create_background_task(
        hass,
        client.start_persistent(),
        f"meridian_smart_{host}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder de integratie."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: MeridianClient = hass.data[DOMAIN].pop(entry.entry_id)
        await client.disconnect()
    return unload_ok
