"""Tests for BeeBuzz button entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_refresh_device_keys_button_fetches_keys(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The refresh button should force a key refresh."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    button_states = [
        state for state in hass.states.async_all(BUTTON_DOMAIN)
        if state.entity_id.endswith("refresh_device_keys")
    ]
    assert button_states

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": button_states[0].entity_id},
        blocking=True,
    )

    assert mock_client.async_fetch_keys.await_count == 2
