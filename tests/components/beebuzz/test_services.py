"""Tests for the BeeBuzz domain service."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.const import (
    ATTR_ATTACHMENT,
    ATTR_BODY,
    ATTR_PRIORITY,
    ATTR_TITLE,
    ATTR_TOPIC,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)


async def test_send_message_service_pushes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The domain service should forward arguments to the coordinator."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_TITLE: "Title",
            ATTR_BODY: "Body",
            ATTR_TOPIC: "alerts",
            ATTR_PRIORITY: "high",
            ATTR_ATTACHMENT: "https://example.com/img.png",
        },
        blocking=True,
    )

    mock_client.async_push.assert_awaited_once()
    kwargs = mock_client.async_push.await_args.kwargs
    assert kwargs["title"] == "Title"
    assert kwargs["body"] == "Body"
    assert kwargs["topic"] == "alerts"
    assert kwargs["priority"] == "high"
    mock_client.async_attachment_from_value.assert_awaited_once_with(
        "https://example.com/img.png"
    )


async def test_send_message_service_requires_loaded_entry(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Calling the service without a loaded entry should raise."""

    # Service is registered at async_setup, even without entries.
    from custom_components.beebuzz import async_setup

    await async_setup(hass, {})

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_TITLE: "T", ATTR_BODY: "B"},
            blocking=True,
        )
