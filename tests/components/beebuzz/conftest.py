"""Shared fixtures for BeeBuzz tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

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


VALID_AGE_RECIPIENT = (
    "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p"
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Auto-enable loading custom integrations in all tests."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock BeeBuzz config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="BeeBuzz",
        version=2,
        data={
            CONF_HOST: DEFAULT_HOST,
            CONF_API_TOKEN: "test-token",
        },
        options={
            CONF_TOPIC: DEFAULT_TOPIC,
            CONF_PRIORITY: DEFAULT_PRIORITY,
        },
    )


@pytest.fixture
def fake_device_keys() -> list[dict[str, Any]]:
    """Return a list of fake BeeBuzz device keys."""

    return [
        {
            "device_id": "device-1",
            "age_recipient": VALID_AGE_RECIPIENT,
        }
    ]


@pytest.fixture
def mock_client(fake_device_keys) -> Generator[AsyncMock, None, None]:
    """Patch the BeeBuzzClient with an AsyncMock."""

    with patch(
        "custom_components.beebuzz.BeeBuzzClient",
        autospec=True,
    ) as client_cls:
        instance = client_cls.return_value
        instance.async_fetch_keys = AsyncMock(return_value=list(fake_device_keys))
        instance.async_push = AsyncMock(return_value={"status": "ok"})
        instance.async_attachment_from_value = AsyncMock(return_value=None)
        yield instance
