"""Constants for the BeeBuzz integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "beebuzz"
PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.NOTIFY, Platform.SENSOR]

DEFAULT_HOST = "beebuzz.app"
PUBLIC_URL = "https://beebuzz.app"
DEFAULT_TOPIC = "#general"
DEFAULT_PRIORITY = "normal"

CONF_API_TOKEN = "api_token"
CONF_HOST = "host"
CONF_TOPIC = "topic"
CONF_PRIORITY = "priority"
CONF_DEVICE_KEYS = "device_keys"

PRIORITIES = ["normal", "high"]

ATTR_TITLE = "title"
ATTR_BODY = "body"
ATTR_ATTACHMENT = "attachment"
ATTR_TOPIC = "topic"
ATTR_PRIORITY = "priority"

SERVICE_SEND_MESSAGE = "send_message"

MAX_ATTACHMENT_BYTES = 1024 * 1024

ATTR_FINGERPRINT = "fingerprint"
ATTR_LAST_REFRESH_SUCCESS = "last_refresh_success"
