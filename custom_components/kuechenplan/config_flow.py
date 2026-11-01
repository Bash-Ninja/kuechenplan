"""Config flow for the Küchenplan integration."""

from typing import Any, override

import probatio as p

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from .const import (
    CONF_AUDIT_INTERVAL,
    CONF_FRESH_WEEKDAY,
    CONF_PLAN_WEEKDAYS,
    CONF_STORES,
    DEFAULT_AUDIT_INTERVAL,
    DEFAULT_FRESH_WEEKDAY,
    DEFAULT_PLAN_WEEKDAYS,
    DEFAULT_STORES,
    DOMAIN,
    NAME,
)

WEEKDAYS = [
    SelectOptionDict(value=str(index), label=label)
    for index, label in enumerate(
        ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    )
]
DEFAULTS = {
    CONF_STORES: DEFAULT_STORES,
    CONF_PLAN_WEEKDAYS: DEFAULT_PLAN_WEEKDAYS,
    CONF_FRESH_WEEKDAY: DEFAULT_FRESH_WEEKDAY,
    CONF_AUDIT_INTERVAL: DEFAULT_AUDIT_INTERVAL,
}


def _schema(values: dict[str, Any]) -> p.Schema:
    """Return the settings form."""
    return p.Schema(
        {
            p.Required(CONF_STORES, default=values[CONF_STORES]): TextSelector(),
            p.Required(
                CONF_PLAN_WEEKDAYS, default=values[CONF_PLAN_WEEKDAYS]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=WEEKDAYS, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
            p.Required(
                CONF_FRESH_WEEKDAY, default=values[CONF_FRESH_WEEKDAY]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=WEEKDAYS, mode=SelectSelectorMode.DROPDOWN
                )
            ),
            p.Required(
                CONF_AUDIT_INTERVAL, default=values[CONF_AUDIT_INTERVAL]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=90, step=1, mode=NumberSelectorMode.BOX
                )
            ),
        }
    )


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Return the form errors."""
    names = [name.strip() for name in user_input[CONF_STORES].split(",") if name.strip()]
    if not names:
        return {CONF_STORES: "no_stores"}
    if len({slugify(name) for name in names}) != len(names):
        return {CONF_STORES: "duplicate_store"}
    if not user_input[CONF_PLAN_WEEKDAYS]:
        return {CONF_PLAN_WEEKDAYS: "no_weekdays"}
    return {}


class KuechenplanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Küchenplan."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> "KuechenplanOptionsFlow":
        """Return the options flow."""
        return KuechenplanOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title=NAME, data={}, options=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or DEFAULTS), errors=errors
        )


class KuechenplanOptionsFlow(OptionsFlow):
    """Change the settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )
