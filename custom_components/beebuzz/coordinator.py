"""Data update coordinator and runtime data for BeeBuzz."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    BeeBuzzAuthError,
    BeeBuzzClient,
    BeeBuzzConnectionError,
    BeeBuzzError,
    build_api_url,
    normalize_topic,
    validate_device_keys,
)
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PRIORITY,
    CONF_TOPIC,
    DEFAULT_PRIORITY,
    DEFAULT_TOPIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ISSUE_NO_DEVICES_PAIRED = "no_devices_paired"
ISSUE_KEYS_REFRESH_FAILED = "keys_refresh_failed"
KEYS_REFRESH_FAILURE_THRESHOLD = 3
KEYS_REFRESH_INTERVAL = timedelta(minutes=15)


type BeeBuzzConfigEntry = ConfigEntry["BeeBuzzRuntimeData"]


@dataclass
class BeeBuzzRuntimeData:
    """Holds BeeBuzz runtime data."""

    client: BeeBuzzClient
    keys: BeeBuzzKeysCoordinator


class BeeBuzzKeysCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that keeps the BeeBuzz device public keys in sync."""

    config_entry: BeeBuzzConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BeeBuzzConfigEntry,
        client: BeeBuzzClient,
    ) -> None:
        """Initialize the keys coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=KEYS_REFRESH_INTERVAL,
            always_update=False,
        )
        self.client = client
        self._consecutive_failures = 0

    @property
    def api_url(self) -> str:
        """Return the configured BeeBuzz API URL."""

        return build_api_url(self.config_entry.data.get(CONF_HOST))

    @property
    def api_token(self) -> str:
        """Return the configured BeeBuzz API token."""

        return self.config_entry.data[CONF_API_TOKEN]

    @property
    def default_topic(self) -> str:
        """Return the configured default topic."""

        return normalize_topic(
            self.config_entry.options.get(CONF_TOPIC, DEFAULT_TOPIC)
        )

    @property
    def default_priority(self) -> str:
        """Return the configured default priority."""

        return self.config_entry.options.get(CONF_PRIORITY, DEFAULT_PRIORITY)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch the latest device public keys from BeeBuzz."""

        try:
            keys = await self.client.async_fetch_keys(self.api_url, self.api_token)
        except BeeBuzzAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except BeeBuzzConnectionError as err:
            self._record_refresh_failure()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        except BeeBuzzError as err:
            self._record_refresh_failure()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self._record_refresh_success()
        self._sync_no_devices_issue(keys)
        return keys

    async def async_send_message(
        self,
        *,
        title: str,
        body: str,
        attachment: Any = None,
        topic: str | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        """Encrypt and send a BeeBuzz notification using the cached keys."""

        try:
            resolved_attachment = await self.client.async_attachment_from_value(
                attachment
            )
            response = await self._async_push(
                title=title,
                body=body,
                attachment=resolved_attachment,
                topic=topic,
                priority=priority,
            )
        except BeeBuzzAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except BeeBuzzConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        except BeeBuzzError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        await self._async_apply_response_keys(response)
        return response

    async def _async_push(
        self,
        *,
        title: str,
        body: str,
        attachment: Any,
        topic: str | None,
        priority: str | None,
    ) -> dict[str, Any]:
        """Send a single push using the currently cached keys."""

        return await self.client.async_push(
            api_url=self.api_url,
            api_token=self.api_token,
            topic=topic or self.default_topic,
            priority=priority or self.default_priority,
            title=title,
            body=body,
            attachment=attachment,
            device_keys=self.data or [],
        )

    async def _async_apply_response_keys(self, response: dict[str, Any]) -> None:
        """Apply key changes embedded in a push response."""

        if "device_keys" not in response:
            return

        incoming = validate_device_keys(response.get("device_keys") or [])
        current = self.data or []
        if _key_set(current) == _key_set(incoming):
            return

        added = _key_set(incoming) - _key_set(current)
        removed = _key_set(current) - _key_set(incoming)
        _LOGGER.debug(
            "BeeBuzz device keys changed: %d added, %d removed",
            len(added),
            len(removed),
        )
        self.async_set_updated_data(incoming)
        self._sync_no_devices_issue(incoming)

    def _record_refresh_failure(self) -> None:
        """Track a refresh failure and raise a repair issue when persistent."""

        self._consecutive_failures += 1
        if self._consecutive_failures >= KEYS_REFRESH_FAILURE_THRESHOLD:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_KEYS_REFRESH_FAILED,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_KEYS_REFRESH_FAILED,
            )

    def _record_refresh_success(self) -> None:
        """Clear the persistent failure repair issue when a refresh succeeds."""

        if self._consecutive_failures:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_KEYS_REFRESH_FAILED)
        self._consecutive_failures = 0

    def _sync_no_devices_issue(self, keys: list[dict[str, Any]]) -> None:
        """Create or clear the no-devices-paired repair issue."""

        if keys:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_NO_DEVICES_PAIRED)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_NO_DEVICES_PAIRED,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NO_DEVICES_PAIRED,
        )


def _key_set(keys: list[dict[str, Any]]) -> set[str]:
    """Return the comparable set of age recipients."""

    return {
        str(key.get("age_recipient", "")).strip()
        for key in keys
        if key.get("age_recipient")
    }
