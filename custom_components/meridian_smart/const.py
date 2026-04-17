"""Constanten voor Meridian Smart integratie."""
DOMAIN = "meridian_smart"
CONF_HOST = "host"
CONF_PRO_LICENSE = "pro_license_key"
DEFAULT_NAME = "Meridian"

PRO_LICENSE_URL = "https://ha-ds.internetist.nl/meridian/license"

# Pro features
PRO_FEATURES = [
    "now_playing",      # Track/artist/album/artwork
    "multi_zone",       # Meer dan 1 apparaat
    "menu_control",     # Bass/treble/balance via HA
]
