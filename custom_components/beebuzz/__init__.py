"""BeeBuzz Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import BeeBuzzClient
from .const import (
    CONF_API_TOKEN,
    CONF_DEVICE_KEYS,
    CONF_HOST,
    CONF_PRIORITY,
    CONF_TOPIC,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import (
    BeeBuzzConfigEntry,
    BeeBuzzKeysCoordinator,
    BeeBuzzRuntimeData,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BeeBuzz integration."""

    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BeeBuzzConfigEntry) -> bool:
    """Set up BeeBuzz from a config entry."""

    client = BeeBuzzClient(hass)
    coordinator = BeeBuzzKeysCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = BeeBuzzRuntimeData(client=client, keys=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: BeeBuzzConfigEntry
) -> None:
    """Reload the entry when options change."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BeeBuzzConfigEntry) -> bool:
    """Unload a BeeBuzz config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older BeeBuzz config entries."""

    if entry.version == 1:
        new_data = {
            CONF_HOST: entry.data.get(CONF_HOST, ""),
            CONF_API_TOKEN: entry.data.get(CONF_API_TOKEN, ""),
        }
        new_options = dict(entry.options)
        for key in (CONF_TOPIC, CONF_PRIORITY):
            if key in entry.data and key not in new_options:
                new_options[key] = entry.data[key]

        # CONF_DEVICE_KEYS used to live in entry.data; it now lives in the
        # coordinator's runtime data and does not need to be persisted.
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=2,
        )
        _LOGGER.debug(
            "Migrated BeeBuzz config entry %s to version 2 (dropped %s)",
            entry.entry_id,
            CONF_DEVICE_KEYS,
        )

    return True
