# Meridian Smart — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/release/wooniot/ha-meridian-smart.svg)](https://github.com/wooniot/ha-meridian-smart/releases)

Control your **Meridian Audio** products from Home Assistant — including the 218, 210, 251, 258, Ellipse and other Ethernet-connected Meridian products.

## Features

- Full `media_player` entity per Meridian zone
- Real-time status updates (no polling)
- Volume control (direct + step)
- Source selection
- Standby / wake
- Mute
- Play / Pause / Next / Previous (streaming sources)
- Now Playing info: track, artist, album, artwork
- Multi-zone: add multiple devices independently
- Works entirely **local** — no cloud required

## Supported products

Any Meridian product with the Automation Interface for IP Control (port 9014), including:

| Product | Protocol version |
|---------|-----------------|
| Meridian 218 Zone Controller | v3 |
| Meridian 210 Streamer | v3/v4 |
| Meridian 251 DSP Loudspeaker | v3 |
| Meridian 258 DSP Loudspeaker | v3 |
| Meridian Ellipse | v4 |

## Installation via HACS

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three dots → **Custom repositories**
3. Add `https://github.com/wooniot/ha-meridian-smart` as **Integration**
4. Search for **Meridian Smart** and install
5. Restart Home Assistant

## Manual installation

Copy the `meridian_smart` folder from `custom_components/` to your HA `config/custom_components/` directory and restart.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Meridian Smart**
3. Enter the IP address of your Meridian product
4. Done — your zone appears as a `media_player` entity

## Protocol

This integration uses the official **Meridian Automation Interface for IP Control** (TCP port 9014). The protocol is documented by Meridian Audio and supported on all modern Ethernet-connected Meridian products.

## License

Free for personal use. A **Pro license** is available for installers and commercial use — contact [wooniot.nl](https://wooniot.nl).

---

Made with ❤️ by [WoonIoT](https://wooniot.nl) — Meridian Benelux importer
