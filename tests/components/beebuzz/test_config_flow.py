"""Tests for the BeeBuzz config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.client import BeeBuzzAuthError, BeeBuzzConnectionError
from custom_components.beebuzz.const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PRIORITY,
    CONF_TOPIC,
    DEFAULT_HOST,
    DEFAULT_PRIORITY,
    DEFAULT_TOPIC,
    DOMAIN,
)


@pytest.fixture
def mock_flow_client():
    """Patch the BeeBuzzClient inside the config_flow module."""

    with patch(
        "custom_components.beebuzz.config_flow.BeeBuzzClient",
        autospec=True,
    ) as client_cls:
        instance = client_cls.return_value
        instance.async_fetch_keys = AsyncMock(return_value=[])
        yield instance


@pytest.fixture
def mock_setup_entry():
    """Patch async_setup_entry to keep config-flow tests focused."""

    with patch(
        "custom_components.beebuzz.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock:
        yield mock


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_flow_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """The user flow stores host+token in data and behavior in options."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: DEFAULT_HOST,
            CONF_API_TOKEN: "secret-token",
            CONF_TOPIC: DEFAULT_TOPIC,
            CONF_PRIORITY: DEFAULT_PRIORITY,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: DEFAULT_HOST,
        CONF_API_TOKEN: "secret-token",
    }
    assert result["options"][CONF_TOPIC] == DEFAULT_TOPIC
    assert result["options"][CONF_PRIORITY] == DEFAULT_PRIORITY
    mock_flow_client.async_fetch_keys.assert_awaited()


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_flow_client: AsyncMock
) -> None:
    """A 401 should surface as invalid_auth error."""

    mock_flow_client.async_fetch_keys.side_effect = BeeBuzzAuthError("nope")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: DEFAULT_HOST,
            CONF_API_TOKEN: "bad",
            CONF_TOPIC: DEFAULT_TOPIC,
            CONF_PRIORITY: DEFAULT_PRIORITY,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_flow_client: AsyncMock
) -> None:
    """A connection error should surface as cannot_connect."""

    mock_flow_client.async_fetch_keys.side_effect = BeeBuzzConnectionError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: DEFAULT_HOST,
            CONF_API_TOKEN: "x",
            CONF_TOPIC: DEFAULT_TOPIC,
            CONF_PRIORITY: DEFAULT_PRIORITY,
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_updates_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: AsyncMock,
    mock_client: AsyncMock,
) -> None:
    """Reauth should update the API token and reload the entry."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-token"


async def test_reconfigure_flow_updates_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: AsyncMock,
    mock_client: AsyncMock,
) -> None:
    """Reconfigure should update host while keeping the existing token by default."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: DEFAULT_HOST,
            CONF_API_TOKEN: "",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # Token should be preserved when the field is left empty.
    assert mock_config_entry.data[CONF_API_TOKEN] == "test-token"


async def test_options_flow_updates_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The options flow should update the entry options."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TOPIC: "alerts",
            CONF_PRIORITY: "high",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_TOPIC] == "alerts"
    assert mock_config_entry.options[CONF_PRIORITY] == "high"
