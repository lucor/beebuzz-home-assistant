"""Diagnostics platform for the BeeBuzz integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from .client import build_api_url, fingerprint_age_recipient
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_TOPIC,
    DEFAULT_HOST,
)
from .coordinator import BeeBuzzConfigEntry

TO_REDACT_OPTIONS = {CONF_TOPIC}
PUBLIC_HOSTS = {DEFAULT_HOST, f"api.{DEFAULT_HOST}"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: BeeBuzzConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a BeeBuzz config entry."""

    runtime = config_entry.runtime_data
    coordinator = runtime.keys

    raw_host = (config_entry.data.get(CONF_HOST) or "").strip()
    api_url = build_api_url(raw_host)
    parsed = urlparse(api_url)
    is_public_host = parsed.netloc in PUBLIC_HOSTS
    host_value = parsed.netloc if is_public_host else REDACTED

    # Always redact api_token and (for self-hosted setups) the host.
    redact_keys = {CONF_API_TOKEN}
    if not is_public_host:
        redact_keys.add(CONF_HOST)

    fingerprints = [
        fingerprint_age_recipient(str(key.get("age_recipient", "")))
        for key in (coordinator.data or [])
    ]

    return {
        "entry": {
            "title": config_entry.title,
            "version": config_entry.version,
            "data": async_redact_data(dict(config_entry.data), redact_keys),
            "options": async_redact_data(
                dict(config_entry.options), TO_REDACT_OPTIONS
            ),
        },
        "host": host_value,
        "device_keys": {
            "count": len(coordinator.data or []),
            "fingerprints": fingerprints,
        },
        "last_update_success": coordinator.last_update_success,
        "last_exception": (
            type(coordinator.last_exception).__name__
            if coordinator.last_exception is not None
            else None
        ),
    }
