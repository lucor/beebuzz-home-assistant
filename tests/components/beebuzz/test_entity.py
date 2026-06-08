"""Tests for BeeBuzz base entities."""

from __future__ import annotations

from unittest.mock import Mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beebuzz.const import PUBLIC_URL
from custom_components.beebuzz.entity import BeeBuzzBaseEntity


def test_device_info_uses_public_configuration_url(
    mock_config_entry: MockConfigEntry,
) -> None:
    """The service info link should point to the public BeeBuzz site."""

    entity = BeeBuzzBaseEntity(Mock(), mock_config_entry, "test")

    assert entity.device_info["configuration_url"] == PUBLIC_URL
