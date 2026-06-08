"""Notify platform for BeeBuzz."""

from __future__ import annotations

from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BeeBuzzConfigEntry
from .entity import BeeBuzzBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BeeBuzzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BeeBuzz notify entities."""

    async_add_entities([BeeBuzzNotifyEntity(config_entry.runtime_data, config_entry)])


class BeeBuzzNotifyEntity(BeeBuzzBaseEntity, NotifyEntity):
    """Notify entity for BeeBuzz messages."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_name = None

    def __init__(self, runtime, config_entry: BeeBuzzConfigEntry) -> None:
        """Initialize the BeeBuzz notifier."""

        super().__init__(runtime, config_entry, "notify")

    async def async_send_message(
        self,
        message: str,
        title: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a Home Assistant notify message through BeeBuzz."""

        await self.runtime.keys.async_send_message(
            title=title or "Home Assistant",
            body=message,
        )
