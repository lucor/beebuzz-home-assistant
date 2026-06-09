"""Config flow for BeeBuzz."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .client import BeeBuzzAuthError, BeeBuzzClient, BeeBuzzConnectionError, build_api_url
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PRIORITY,
    CONF_TOPIC,
    DEFAULT_HOST,
    DEFAULT_PRIORITY,
    DEFAULT_TOPIC,
    DOMAIN,
    PRIORITIES,
)

_LOGGER = logging.getLogger(__name__)

HOST_DESCRIPTION_PLACEHOLDERS = {"official_host": DEFAULT_HOST}


class BeeBuzzConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a BeeBuzz config flow."""

    VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate(
                user_input[CONF_HOST], user_input[CONF_API_TOKEN]
            )
            if not errors:
                return self.async_create_entry(
                    title="BeeBuzz",
                    data={
                        CONF_HOST: user_input[CONF_HOST].strip(),
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN].strip(),
                    },
                    options={
                        CONF_TOPIC: user_input[CONF_TOPIC].strip(),
                        CONF_PRIORITY: user_input[CONF_PRIORITY],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(
                user_input or {}, include_connection=True, include_behavior=True
            ),
            description_placeholders=HOST_DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""

        entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN].strip() or entry.data[CONF_API_TOKEN]
            errors = await self._async_validate(user_input[CONF_HOST], api_token)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST].strip(),
                        CONF_API_TOKEN: api_token,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(
                entry.data, include_connection=True, include_behavior=False
            ),
            description_placeholders=HOST_DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle a reauthentication trigger."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm reauthentication by submitting a new API token."""

        entry = self._get_reauth_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN].strip()
            errors = await self._async_validate(entry.data[CONF_HOST], api_token)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_TOKEN: api_token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BeeBuzzOptionsFlow:
        """Create the options flow."""

        return BeeBuzzOptionsFlow()

    async def _async_validate(self, host: str, api_token: str) -> dict[str, str]:
        """Validate credentials by fetching public keys."""

        client = BeeBuzzClient(self.hass)
        try:
            await client.async_fetch_keys(build_api_url(host), api_token.strip())
        except BeeBuzzAuthError:
            return {"base": "invalid_auth"}
        except BeeBuzzConnectionError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected BeeBuzz error during config flow validation")
            return {"base": "unknown"}
        return {}


class BeeBuzzOptionsFlow(config_entries.OptionsFlow):
    """Handle BeeBuzz options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage BeeBuzz options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current, include_connection=False, include_behavior=True
            ),
        )


def _schema(
    defaults: dict[str, Any] | Mapping[str, Any],
    *,
    include_connection: bool,
    include_behavior: bool,
) -> vol.Schema:
    """Build the config/options form schema."""

    fields: dict[Any, Any] = {}
    if include_connection:
        fields[
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST))
        ] = str
        fields[vol.Required(CONF_API_TOKEN, default="")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
    if include_behavior:
        fields.update(
            {
                vol.Required(
                    CONF_TOPIC, default=defaults.get(CONF_TOPIC, DEFAULT_TOPIC)
                ): str,
                vol.Required(
                    CONF_PRIORITY,
                    default=defaults.get(CONF_PRIORITY, DEFAULT_PRIORITY),
                ): vol.In(PRIORITIES),
            }
        )
    return vol.Schema(fields)
