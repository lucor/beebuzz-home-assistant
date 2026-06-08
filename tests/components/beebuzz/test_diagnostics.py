"""Tests for the BeeBuzz diagnostics platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.client import BeeBuzzConnectionError
from custom_components.beebuzz.const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_TOPIC,
)
from custom_components.beebuzz.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_sensitive_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """API token, age recipients and topic should be redacted."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry"]["data"][CONF_API_TOKEN] == REDACTED
    # Public host is left in clear; self-hosted is redacted (covered below).
    assert diagnostics["entry"]["data"][CONF_HOST] != REDACTED
    assert diagnostics["entry"]["options"][CONF_TOPIC] == REDACTED
    assert "api.beebuzz.app" in diagnostics["host"]
    assert diagnostics["device_keys"]["count"] == 1
    fingerprints = diagnostics["device_keys"]["fingerprints"]
    assert len(fingerprints) == 1
    assert fingerprints[0]
    # Raw age recipients must never be exposed in diagnostics.
    assert "age1" not in str(diagnostics["device_keys"])


async def test_diagnostics_shows_last_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The last exception type should be surfaced in diagnostics."""

    mock_client.async_fetch_keys.side_effect = [
        [  # initial refresh succeeds
            {"device_id": "device-1", "age_recipient": "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p"}
        ],
        BeeBuzzConnectionError("simulated failure"),  # subsequent refresh fails
    ]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.keys
    await coordinator.async_request_refresh()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["last_update_success"] is False
    assert diagnostics["last_exception"] == "UpdateFailed"


async def test_diagnostics_redacts_self_hosted_host(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Self-hosted hosts should be redacted while public host stays in clear."""

    entry = MockConfigEntry(
        domain="beebuzz",
        unique_id="beebuzz",
        title="BeeBuzz",
        version=2,
        data={
            CONF_HOST: "private.example.com",
            CONF_API_TOKEN: "tok",
        },
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["host"] == REDACTED
