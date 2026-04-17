"""Pro licentie validatie voor Meridian Smart."""
import hashlib
import hmac as _hmac
import logging

import aiohttp

from .const import PRO_LICENSE_URL

_LOGGER = logging.getLogger(__name__)

# Offline signing key (gesplitst om eenvoudig kopiëren te bemoeilijken)
_SIGN_KEY = "wooniot" + "-meridian-" + "pro-2026" + "-secret" + "-key"


async def check_pro_license(key: str, serial: str) -> dict:
    """Valideer Pro licentiesleutel via WoonIoT server.

    Returns dict: valid, reason, type, method (online/offline).
    serial = eerste 8 chars van Meridian SerialNumber.
    """
    if not key:
        return {"valid": False, "reason": "no_key", "type": None, "method": None}

    serial_short = serial[:8] if serial else ""

    # Online validatie
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                PRO_LICENSE_URL,
                json={"key": key, "serial": serial_short},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "valid": data.get("valid", False),
                        "reason": data.get("reason", "ok" if data.get("valid") else "unknown"),
                        "type": data.get("type"),
                        "method": "online",
                        "serial_sent": serial_short,
                    }
    except Exception as exc:
        _LOGGER.debug("Online licentiecheck mislukt, offline fallback: %s", exc)

    # Offline fallback: HMAC signature check
    valid = _verify_offline(key)
    return {
        "valid": valid,
        "reason": "ok" if valid else "invalid_signature",
        "type": "offline",
        "method": "offline",
        "serial_sent": serial_short,
    }


def _verify_offline(key: str) -> bool:
    """Verifieer licentiesleutel via HMAC signature (offline)."""
    parts = key.strip().split("-")
    if len(parts) != 4:
        return False
    prefix = parts[0]
    if prefix not in ("PRO", "TRIAL"):
        return False
    body = f"{prefix}-{parts[1]}-{parts[2]}"
    sig = _hmac.new(
        _SIGN_KEY.encode(), body.encode(), hashlib.sha256
    ).hexdigest()[:4].upper()
    return parts[3] == sig


def generate_license_key(prefix: str = "PRO") -> str:
    """Genereer een nieuwe licentiesleutel (voor intern gebruik op de server)."""
    import secrets
    part1 = secrets.token_hex(3).upper()
    part2 = secrets.token_hex(3).upper()
    body = f"{prefix}-{part1}-{part2}"
    sig = _hmac.new(
        _SIGN_KEY.encode(), body.encode(), hashlib.sha256
    ).hexdigest()[:4].upper()
    return f"{body}-{sig}"
