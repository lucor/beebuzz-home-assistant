"""Tests for the BeeBuzz integration setup/unload/migrate."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.const import (
    CONF_API_TOKEN,
    CONF_DEVICE_KEYS,
    CONF_HOST,
    CONF_PRIORITY,
    CONF_TOPIC,
    DEFAULT_HOST,
    DOMAIN,
)


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Setting up and unloading a BeeBuzz entry should succeed."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.client is mock_client
    mock_client.async_fetch_keys.assert_awaited()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_v1_entry_moves_options_and_drops_device_keys(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """A V1 entry should migrate to V2 with user options moved."""

    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="BeeBuzz",
        version=1,
        data={
            CONF_HOST: DEFAULT_HOST,
            CONF_API_TOKEN: "old-token",
            CONF_TOPIC: "alerts",
            CONF_PRIORITY: "high",
            CONF_DEVICE_KEYS: [{"age_recipient": "ignored"}],
        },
    )
    legacy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    assert legacy_entry.version == 2
    assert legacy_entry.data == {
        CONF_HOST: DEFAULT_HOST,
        CONF_API_TOKEN: "old-token",
    }
    for option_key in (CONF_TOPIC, CONF_PRIORITY):
        assert option_key in legacy_entry.options
    assert CONF_DEVICE_KEYS not in legacy_entry.data
    assert CONF_DEVICE_KEYS not in legacy_entry.options
