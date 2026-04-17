"""Meridian Smart — Home Assistant media_player platform."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .meridian_client import MeridianClient

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Stel de media_player entity in vanuit een config entry."""
    client: MeridianClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MeridianMediaPlayer(client, entry)])


class MeridianMediaPlayer(MediaPlayerEntity):
    """Representeert één Meridian zone als HA media_player."""

    _attr_has_entity_name = True
    _attr_name = None   # Gebruikt zone_name als naam

    def __init__(self, client: MeridianClient, entry: ConfigEntry) -> None:
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"meridian_{entry.entry_id}"
        self._attr_supported_features = SUPPORTED_FEATURES
        # Registreer callback zodat HA bijgewerkt wordt bij statuswijziging
        client._state_callback = self._on_state_changed

    @callback
    def _on_state_changed(self):
        """Wordt aangeroepen door MeridianClient bij elke statuswijziging."""
        self.async_write_ha_state()

    # ------------------------------------------------------------------ #
    # HA state properties                                                  #
    # ------------------------------------------------------------------ #

    @property
    def available(self) -> bool:
        return self._client.state.available

    @property
    def name(self) -> str:
        return self._client.state.zone_name or self._entry.title

    @property
    def state(self) -> MediaPlayerState:
        if not self._client.state.available:
            return MediaPlayerState.UNAVAILABLE
        if self._client.state.standby:
            return MediaPlayerState.OFF
        ps = self._client.state.player_state.lower()
        if ps == "pause":
            return MediaPlayerState.PAUSED
        if ps == "play":
            return MediaPlayerState.PLAYING
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> Optional[float]:
        return self._client.state.volume / 99.0

    @property
    def is_volume_muted(self) -> bool:
        return self._client.state.muted

    @property
    def source(self) -> Optional[str]:
        return self._client.state.source

    @property
    def source_list(self) -> list[str]:
        return list(self._client.state.sources.values())

    @property
    def media_title(self) -> Optional[str]:
        if not self._client.pro_enabled:
            return None
        return self._client.state.media_title or None

    @property
    def media_artist(self) -> Optional[str]:
        if not self._client.pro_enabled:
            return None
        return self._client.state.media_artist or None

    @property
    def media_album_name(self) -> Optional[str]:
        if not self._client.pro_enabled:
            return None
        return self._client.state.media_album or None

    @property
    def media_image_url(self) -> Optional[str]:
        if not self._client.pro_enabled:
            return None
        return self._client.state.media_image_url or None

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "product": self._client.state.product,
            "serial_number": self._client.state.serial,
            "protocol_version": self._client.state.protocol_version,
            "pro_license": self._client.pro_enabled,
        }
        return attrs

    # ------------------------------------------------------------------ #
    # HA service calls                                                     #
    # ------------------------------------------------------------------ #

    async def async_turn_on(self) -> None:
        """Zet apparaat aan door laatste bron te selecteren."""
        await self._client.send_command("SRC")

    async def async_turn_off(self) -> None:
        await self._client.standby()

    async def async_set_volume_level(self, volume: float) -> None:
        await self._client.set_volume(int(volume * 99))

    async def async_volume_up(self) -> None:
        await self._client.volume_up()

    async def async_volume_down(self) -> None:
        await self._client.volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.mute()

    async def async_select_source(self, source: str) -> None:
        await self._client.select_source_by_name(source)

    async def async_media_play(self) -> None:
        await self._client.media_play()

    async def async_media_pause(self) -> None:
        await self._client.media_pause()

    async def async_media_next_track(self) -> None:
        await self._client.media_next()

    async def async_media_previous_track(self) -> None:
        await self._client.media_previous()
