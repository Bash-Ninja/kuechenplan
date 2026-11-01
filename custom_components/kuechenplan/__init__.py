"""The Küchenplan integration."""

from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any

import probatio as p

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    CONF_AUDIT_INTERVAL,
    CONF_FRESH_WEEKDAY,
    CONF_PLAN_WEEKDAYS,
    CONF_STORES,
    DOMAIN,
    NAME,
    PANEL_COMPONENT,
    PANEL_URL_PATH,
    SIGNAL_UPDATED,
    STATIC_URL,
)
from .llm_api import KuechenplanAPI
from .operations import OPERATIONS, Operation
from .store import KuechenplanStore, Settings

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.TODO,
]
FRONTEND_DIR = Path(__file__).parent / "frontend"
PANEL_FILE = FRONTEND_DIR / "kuechenplan-panel.js"
CONFIG_SCHEMA = p.Schema({DOMAIN: p.Schema({})}, extra=p.ALLOW_EXTRA)

type KuechenplanConfigEntry = ConfigEntry[KuechenplanStore]


def _settings(entry: ConfigEntry) -> Settings:
    """Read the settings of a config entry."""
    names = [name.strip() for name in entry.options[CONF_STORES].split(",")]
    return Settings(
        stores={slugify(name): name for name in names if name},
        plan_weekdays=[int(day) for day in entry.options[CONF_PLAN_WEEKDAYS]],
        fresh_weekday=int(entry.options[CONF_FRESH_WEEKDAY]),
        audit_interval_days=int(entry.options[CONF_AUDIT_INTERVAL]),
    )


def _active_store(hass: HomeAssistant) -> KuechenplanStore:
    """Return the store of the loaded config entry."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        return entry.runtime_data
    raise HomeAssistantError(f"{NAME} is not set up")


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register every operation as a service."""

    def _make_handler(operation: Operation):
        async def _handle(call: ServiceCall) -> ServiceResponse:
            try:
                return operation.run(_active_store(hass), dict(call.data))
            except HomeAssistantError as err:
                raise ServiceValidationError(str(err)) from err

        return _handle

    for operation in OPERATIONS.values():
        hass.services.async_register(
            DOMAIN,
            operation.name,
            _make_handler(operation),
            schema=p.Schema(dict, extra=p.ALLOW_EXTRA),
            supports_response=SupportsResponse.ONLY
            if operation.read_only
            else SupportsResponse.OPTIONAL,
        )
        async_set_service_schema(
            hass,
            DOMAIN,
            operation.name,
            {
                "name": operation.name.replace("_", " ").capitalize(),
                "description": operation.description,
                "fields": {},
            },
        )


@websocket_api.websocket_command({"type": f"{DOMAIN}/subscribe"})
@callback
def _ws_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the household data now and after every change."""
    msg_id = msg["id"]

    @callback
    def _send() -> None:
        connection.send_message(
            websocket_api.event_message(msg_id, _active_store(hass).snapshot())
        )

    connection.subscriptions[msg_id] = async_dispatcher_connect(
        hass, SIGNAL_UPDATED, _send
    )
    connection.send_result(msg_id)
    _send()


@websocket_api.websocket_command(
    {
        "type": f"{DOMAIN}/call",
        p.Required("operation"): p.In(list(OPERATIONS)),
        p.Optional("args", default={}): dict,
    }
)
@callback
def _ws_call(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run an operation for the panel."""
    try:
        result = OPERATIONS[msg["operation"]].run(_active_store(hass), msg["args"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "failed", str(err))
        return
    connection.send_result(msg["id"], result)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up what stays registered across config entry reloads."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
    )
    websocket_api.async_register_command(hass, _ws_subscribe)
    websocket_api.async_register_command(hass, _ws_call)
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KuechenplanConfigEntry) -> bool:
    """Set up Küchenplan from a config entry."""
    store = KuechenplanStore(hass, _settings(entry))
    await store.async_load()
    entry.runtime_data = store

    entry.async_on_unload(llm.async_register_api(hass, KuechenplanAPI(hass, store)))

    @callback
    def _midnight(_: datetime) -> None:
        store.async_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, _midnight, hour=0, minute=0, second=5)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    version = await hass.async_add_executor_job(
        lambda: sha1(PANEL_FILE.read_bytes()).hexdigest()[:12]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=NAME,
        sidebar_icon="mdi:silverware-fork-knife",
        module_url=f"{STATIC_URL}/{PANEL_FILE.name}?v={version}",
        require_admin=False,
    )
    entry.async_on_unload(lambda: frontend.async_remove_panel(hass, PANEL_URL_PATH))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: KuechenplanConfigEntry) -> None:
    """Apply changed options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: KuechenplanConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_save()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
