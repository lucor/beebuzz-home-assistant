"""Tests for BeeBuzz sensor entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.const import ATTR_FINGERPRINT
from custom_components.beebuzz.sensor import ATTR_FINGERPRINTS


async def test_device_keys_sensor_exposes_count_and_fingerprints(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The device keys sensor should expose count and per-key fingerprints."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_states = [
        state for state in hass.states.async_all(SENSOR_DOMAIN)
        if state.entity_id.endswith("device_keys")
    ]
    assert sensor_states

    state = sensor_states[0]
    assert state.state == "1"
    fingerprints = state.attributes[ATTR_FINGERPRINTS]
    assert len(fingerprints) == 1
    assert fingerprints[0][ATTR_FINGERPRINT]
    # Raw age recipients must never be exposed in entity attributes.
    assert "age_recipient" not in fingerprints[0]
