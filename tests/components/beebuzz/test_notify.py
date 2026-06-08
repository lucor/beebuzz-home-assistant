"""Tests for BeeBuzz notify entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_notify_entity_sends_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The notify entity should map HA message fields to BeeBuzz payload fields."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_states = hass.states.async_all(NOTIFY_DOMAIN)
    assert notify_states

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {
            "entity_id": notify_states[0].entity_id,
            "message": "Motion detected",
            "title": "Camera",
        },
        blocking=True,
    )

    mock_client.async_push.assert_awaited_once()
    kwargs = mock_client.async_push.await_args.kwargs
    assert kwargs["title"] == "Camera"
    assert kwargs["body"] == "Motion detected"
    mock_client.async_attachment_from_value.assert_awaited_once_with(None)


async def test_notify_entity_defaults_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The notify entity should provide a default title when omitted."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_states = hass.states.async_all(NOTIFY_DOMAIN)
    assert notify_states

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {
            "entity_id": notify_states[0].entity_id,
            "message": "Front door opened",
        },
        blocking=True,
    )

    mock_client.async_push.assert_awaited_once()
    kwargs = mock_client.async_push.await_args.kwargs
    assert kwargs["title"] == "Home Assistant"
    assert kwargs["body"] == "Front door opened"


async def test_notify_entity_records_notification_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The notify entity should record a notification timestamp after sending."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_states = hass.states.async_all(NOTIFY_DOMAIN)
    assert notify_states

    state_before = hass.states.get(notify_states[0].entity_id)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {
            "entity_id": notify_states[0].entity_id,
            "message": "Front door opened",
            "title": "Door",
        },
        blocking=True,
    )

    mock_client.async_push.assert_awaited_once()
    mock_client.async_attachment_from_value.assert_awaited_once_with(None)
    kwargs = mock_client.async_push.await_args.kwargs
    assert kwargs["title"] == "Door"
    assert kwargs["body"] == "Front door opened"
    state_after = hass.states.get(notify_states[0].entity_id)
    assert state_after is not None
    assert state_after.state != "unknown"
    assert state_after.state != state_before.state
