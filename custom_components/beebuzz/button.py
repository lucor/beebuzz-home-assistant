"""Button platform for BeeBuzz."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BeeBuzzConfigEntry
from .entity import BeeBuzzBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BeeBuzzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BeeBuzz button entities."""

    async_add_entities([BeeBuzzRefreshKeysButton(config_entry.runtime_data, config_entry)])


class BeeBuzzRefreshKeysButton(BeeBuzzBaseEntity, ButtonEntity):
    """Button that refreshes BeeBuzz device keys."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh_device_keys"

    def __init__(self, runtime, config_entry: BeeBuzzConfigEntry) -> None:
        """Initialize the refresh keys button."""

        super().__init__(runtime, config_entry, "refresh_device_keys")

    async def async_press(self) -> None:
        """Refresh BeeBuzz device keys."""

        await self.runtime.keys.async_request_refresh()
