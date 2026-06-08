"""Sensor platform for BeeBuzz."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import fingerprint_age_recipient
from .const import (
    ATTR_FINGERPRINT,
    ATTR_LAST_REFRESH_SUCCESS,
)
from .coordinator import BeeBuzzConfigEntry
from .entity import BeeBuzzBaseEntity

ATTR_FINGERPRINTS = "fingerprints"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BeeBuzzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BeeBuzz sensor entities."""

    async_add_entities([BeeBuzzDeviceKeysSensor(config_entry.runtime_data, config_entry)])


class BeeBuzzDeviceKeysSensor(BeeBuzzBaseEntity, SensorEntity):
    """Sensor exposing the current BeeBuzz device key count."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "device_keys"

    def __init__(self, runtime, config_entry: BeeBuzzConfigEntry) -> None:
        """Initialize the device keys sensor."""

        super().__init__(runtime, config_entry, "device_keys")

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""

        self.async_on_remove(
            self.runtime.keys.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write state when the key set changes."""

        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Return the current number of device keys."""

        return len(self.runtime.keys.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return non-sensitive device key details.

        Only fingerprints (a salted-free, short SHA-256 prefix of the public
        key) are exposed; raw age recipients identify devices uniquely and are
        intentionally never written to entity state.
        """

        fingerprints = [
            {
                ATTR_FINGERPRINT: fingerprint_age_recipient(
                    str(key.get("age_recipient", ""))
                ),
            }
            for key in self.runtime.keys.data or []
        ]

        return {
            ATTR_FINGERPRINTS: fingerprints,
            ATTR_LAST_REFRESH_SUCCESS: self.runtime.keys.last_update_success,
        }
