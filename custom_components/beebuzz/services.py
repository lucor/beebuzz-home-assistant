"""Service handlers for BeeBuzz."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_ATTACHMENT,
    ATTR_BODY,
    ATTR_PRIORITY,
    ATTR_TITLE,
    ATTR_TOPIC,
    DOMAIN,
    PRIORITIES,
    SERVICE_SEND_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TITLE): cv.string,
        vol.Required(ATTR_BODY): cv.string,
        vol.Optional(ATTR_ATTACHMENT): vol.Any(cv.string, dict),
        vol.Optional(ATTR_TOPIC): cv.string,
        vol.Optional(ATTR_PRIORITY): vol.In(PRIORITIES),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register BeeBuzz services."""

    async def _async_handle_send_message(call: ServiceCall) -> None:
        """Handle the integration-level send service."""

        loaded_entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
        if not loaded_entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_entry_loaded",
            )

        runtime = loaded_entries[0].runtime_data
        await runtime.keys.async_send_message(
            title=call.data[ATTR_TITLE],
            body=call.data[ATTR_BODY],
            attachment=call.data.get(ATTR_ATTACHMENT),
            topic=call.data.get(ATTR_TOPIC),
            priority=call.data.get(ATTR_PRIORITY),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        _async_handle_send_message,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
    )
