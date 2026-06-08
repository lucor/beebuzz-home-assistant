"""Tests for the BeeBuzz repair issues."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.client import BeeBuzzError
from custom_components.beebuzz.const import DOMAIN
from custom_components.beebuzz.coordinator import (
    ISSUE_KEYS_REFRESH_FAILED,
    ISSUE_NO_DEVICES_PAIRED,
    KEYS_REFRESH_FAILURE_THRESHOLD,
)


async def test_no_devices_paired_creates_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """An empty device key list should create the no_devices_paired issue."""

    mock_client.async_fetch_keys.return_value = []

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_NO_DEVICES_PAIRED)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.translation_key == ISSUE_NO_DEVICES_PAIRED


async def test_no_devices_issue_clears_when_keys_appear(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    fake_device_keys,
) -> None:
    """The no_devices_paired issue should clear once devices are paired."""

    mock_client.async_fetch_keys.return_value = []
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys
    mock_client.async_fetch_keys.return_value = list(fake_device_keys)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_NO_DEVICES_PAIRED) is None
    )


async def test_repeated_refresh_failures_create_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    fake_device_keys,
) -> None:
    """Sustained refresh failures should raise keys_refresh_failed."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys
    mock_client.async_fetch_keys.side_effect = BeeBuzzError("boom")

    for _ in range(KEYS_REFRESH_FAILURE_THRESHOLD):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_KEYS_REFRESH_FAILED)
    assert issue is not None
    assert issue.is_fixable is False

    mock_client.async_fetch_keys.side_effect = None
    mock_client.async_fetch_keys.return_value = list(fake_device_keys)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_KEYS_REFRESH_FAILED) is None
    )
