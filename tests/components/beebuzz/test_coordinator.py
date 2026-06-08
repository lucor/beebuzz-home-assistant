"""Tests for the BeeBuzz keys coordinator and send pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.client import (
    BeeBuzzAuthError,
    BeeBuzzConnectionError,
    BeeBuzzError,
    BeeBuzzValidationError,
)


async def test_send_message_uses_cached_keys(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The send pipeline should use the cached device keys."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys

    await coordinator.async_send_message(title="t", body="b")
    mock_client.async_push.assert_awaited()
    call = mock_client.async_push.await_args
    assert call.kwargs["title"] == "t"
    assert call.kwargs["body"] == "b"
    assert call.kwargs["device_keys"] == coordinator.data


async def test_send_message_applies_response_keys(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A successful push should apply the returned device keys."""

    new_recipient = (
        "age1cy0su9fwf3gf9mw868g5yut09p6nytfmmnktexz2ya5uqg9vl9sss4euqm"
    )
    response_keys = [{"device_id": "device-2", "age_recipient": new_recipient}]
    mock_client.async_push.return_value = {
        "status": "ok",
        "device_keys": response_keys,
    }

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys
    response = await coordinator.async_send_message(title="t", body="b")

    assert response["status"] == "ok"
    assert mock_client.async_push.await_count == 1
    assert coordinator.data == response_keys


async def test_send_message_does_not_refresh_keys_on_push_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    fake_device_keys,
) -> None:
    """A push failure should not trigger an implicit key fetch."""

    mock_client.async_push.side_effect = BeeBuzzError("temporary failure")
    mock_client.async_fetch_keys.side_effect = [
        list(fake_device_keys),  # initial coordinator refresh
    ]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_message(title="t", body="b")

    assert mock_client.async_push.await_count == 1
    assert mock_client.async_fetch_keys.await_count == 1


@pytest.mark.parametrize(
    "error_class",
    [BeeBuzzAuthError, BeeBuzzConnectionError, BeeBuzzValidationError],
)
async def test_send_message_does_not_retry_on_specific_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    fake_device_keys,
    error_class: type[Exception],
) -> None:
    """Auth, connection and validation errors must not trigger a key refresh retry."""

    mock_client.async_push.side_effect = error_class("nope")
    mock_client.async_fetch_keys.side_effect = [
        list(fake_device_keys),  # initial coordinator refresh
    ]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_message(title="t", body="b")

    assert mock_client.async_push.await_count == 1
    assert mock_client.async_fetch_keys.await_count == 1


async def test_send_message_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A 401 from a send call should start the reauth flow."""

    mock_client.async_push.side_effect = BeeBuzzAuthError("denied")

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_message(title="t", body="b")
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("beebuzz")
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
