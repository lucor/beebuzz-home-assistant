"""Base entity for BeeBuzz."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PUBLIC_URL
from .coordinator import BeeBuzzConfigEntry, BeeBuzzRuntimeData


class BeeBuzzBaseEntity(Entity):
    """Base BeeBuzz entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: BeeBuzzRuntimeData,
        config_entry: BeeBuzzConfigEntry,
        key: str,
    ) -> None:
        """Initialize the BeeBuzz base entity."""

        self.runtime = runtime
        self.config_entry = config_entry
        # The integration uses single_config_entry, so DOMAIN is a stable
        # base for unique IDs and survives entry re-creation.
        self._attr_unique_id = f"{DOMAIN}_{key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="BeeBuzz",
            model="Push Notification Service",
            name="BeeBuzz",
            configuration_url=PUBLIC_URL,
        )
