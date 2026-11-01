"""End-to-end tests through the real Home Assistant MCP server."""

import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.kuechenplan.const import (
    CONF_AUDIT_INTERVAL,
    CONF_FRESH_WEEKDAY,
    CONF_PLAN_WEEKDAYS,
    CONF_STORES,
    DOMAIN,
    EVENT_PLAN_APPLIED,
)

CLIENT_ID = "https://claude.example/"
SUNDAY = "2026-11-01 10:00:00+01:00"
MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY = (
    "2026-11-02",
    "2026-11-03",
    "2026-11-04",
    "2026-11-05",
    "2026-11-06",
)
PAD_KRA_PAO = {
    "name": "Pad Kra Pao",
    "servings": 2,
    "minutes": 20,
    "rice": True,
    "ingredients": [
        {"name": "Hackfleisch", "amount": 300, "unit": "g", "store": "rewe", "section": "Fleisch und Fisch"},
        {"name": "Thai-Basilikum", "amount": 1, "unit": "Bund", "store": "rewe", "section": "Obst und Gemüse", "fresh": True},
        {"name": "Eier", "amount": 2, "unit": "Stk.", "store": "rewe", "section": "Kühlregal"},
        {"name": "Sojasauce", "amount": 3, "unit": "EL", "staple": True},
    ],
    "steps": [{"text": "Anbraten", "minutes": 5}, {"text": "Servieren"}],
}
LACHS = {
    "name": "Lachs",
    "servings": 2,
    "minutes": 30,
    "ingredients": [
        {"name": "Lachsfilet", "amount": 0.3, "unit": "kg", "store": "REWE", "section": "Fleisch und Fisch", "fresh": True},
        {"name": "Eier", "amount": 2, "unit": "Stück", "store": "rewe", "section": "Kühlregal"},
        {"name": "Paprika", "amount": 3, "unit": "Stk.", "store": "rewe", "section": "Obst und Gemüse"},
    ],
    "steps": [{"text": "Braten"}],
}


class Client:
    """Minimal MCP client."""

    def __init__(self, http, token: str) -> None:
        """Initialize the client."""
        self._http = http
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }

    async def tools(self) -> dict:
        """Return the offered tools by name."""
        response = await self._http.post(
            "/api/mcp",
            headers=self._headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status == 200
        data = await response.json()
        return {tool["name"]: tool for tool in data["result"]["tools"]}

    async def call(self, name: str, /, **arguments) -> dict:
        """Call a tool that should succeed."""
        failed, result = await self.call_raw(name, **arguments)
        assert not failed, result
        return result

    async def call_raw(self, name: str, /, **arguments) -> tuple[bool, dict | str]:
        """Call a tool, returning whether it failed and its result."""
        response = await self._http.post(
            "/api/mcp",
            headers=self._headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        data = await response.json()
        result = data["result"]
        text = result["content"][0]["text"]
        if result.get("isError"):
            return True, text
        return False, json.loads(text)


@pytest.fixture
async def mcp(hass: HomeAssistant, hass_client_no_auth, hass_admin_user, freezer) -> Client:
    """Set up the integration and the real MCP server."""
    freezer.move_to(SUNDAY)
    await hass.config.async_set_time_zone("Europe/Berlin")
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "http", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STORES: "REWE, Lidl",
            CONF_PLAN_WEEKDAYS: ["0", "1", "2", "3", "4"],
            CONF_FRESH_WEEKDAY: "2",
            CONF_AUDIT_INTERVAL: 14,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    entry = MockConfigEntry(domain="mcp_server", data={"llm_hass_api": [DOMAIN]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    refresh = await hass.auth.async_create_refresh_token(hass_admin_user, CLIENT_ID)
    token = hass.auth.async_create_access_token(refresh)
    return Client(await hass_client_no_auth(), token)


def by_name(items: list[dict]) -> dict[str, dict]:
    """Index shopping items by name, requiring them to be unique."""
    result = {item["name"]: item for item in items}
    assert len(result) == len(items)
    return result


async def test_tools_have_usable_schemas(mcp: Client) -> None:
    """A planner sees nested recipes in the tool schema."""
    tools = await mcp.tools()
    assert "get_planning_context" in tools
    days = tools["apply_week_plan"]["inputSchema"]["properties"]["days"]
    recipe = days["items"]["properties"]["recipe"]["properties"]
    assert "ingredients" in recipe
    assert "fresh" in recipe["ingredients"]["items"]["properties"]


async def test_plan_fills_calendar_lists_and_sensors(
    hass: HomeAssistant, mcp: Client
) -> None:
    """Everything visible follows from a single plan call."""
    events = async_capture_events(hass, EVENT_PLAN_APPLIED)
    assert hass.states.get("binary_sensor.kuchenplan_plan_fehlt").state == "on"

    result = await mcp.call(
        "apply_week_plan",
        days=[
            {"date": MONDAY, "recipe": PAD_KRA_PAO},
            {"date": THURSDAY, "recipe": LACHS, "offers": [
                {"item": "Paprika", "store": "lidl", "label": "-25 %"}
            ]},
        ],
    )
    await hass.async_block_till_done()
    assert result["planned_days"] == [MONDAY, THURSDAY]
    assert result["shopping"] == {"rewe": 4, "lidl": 1}
    assert hass.states.get("binary_sensor.kuchenplan_plan_fehlt").state == "off"
    assert hass.states.get("todo.kuchenplan_einkauf_rewe").state == "4"
    assert hass.states.get("todo.kuchenplan_einkauf_lidl").state == "1"
    assert len(events) == 1

    rewe = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert rewe["Eier"]["amount"] == "4 Stk."  # Stück and Stk. add up
    assert rewe["Lachsfilet"]["amount"] == "300 g"  # kg is converted
    assert rewe["Lachsfilet"]["buy_on"] == WEDNESDAY
    assert rewe["Thai-Basilikum"]["buy_on"] is None  # Monday is before the trip
    assert "Sojasauce" not in rewe  # Staples stay out
    lidl = by_name((await mcp.call("get_shopping_list", store="lidl"))["items"])
    assert lidl["Paprika"]["offer"] == "-25 %"

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"start_date_time": "2026-11-01 00:00:00", "duration": {"days": 7}},
        target={"entity_id": "calendar.kuchenplan_essensplan"},
        blocking=True,
        return_response=True,
    )
    summaries = [
        event["summary"]
        for event in response["calendar.kuchenplan_essensplan"]["events"]
    ]
    assert summaries == ["Pad Kra Pao (20 Min.)", "Lachs (30 Min.)"]
    assert hass.states.get("sensor.kuchenplan_morgen").state == "Pad Kra Pao (20 Min.)"
    assert hass.states.get("sensor.kuchenplan_morgen").attributes["rice"] is True
    assert hass.states.get("sensor.kuchenplan_frischekauf_offen").state == "1"


async def test_replanning_is_idempotent_and_keeps_ticks(
    hass: HomeAssistant, mcp: Client
) -> None:
    """Repeating a plan changes nothing, removing a meal removes its needs."""
    days = [
        {"date": MONDAY, "recipe": PAD_KRA_PAO},
        {"date": THURSDAY, "recipe": LACHS},
    ]
    await mcp.call("apply_week_plan", days=days)
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    await mcp.call("set_shopping_item_done", id=items["Hackfleisch"]["id"])
    await mcp.call("add_shopping_items", items=[{"name": "Kaffee", "store": "rewe"}])

    await mcp.call("apply_week_plan", days=days)
    items = by_name(
        (await mcp.call("get_shopping_list", store="rewe", include_done=True))["items"]
    )
    assert items["Hackfleisch"]["done"] is True
    assert items["Eier"]["amount"] == "4 Stk."
    assert "Kaffee" in items

    await mcp.call("apply_week_plan", days=[days[0]])
    items = by_name(
        (await mcp.call("get_shopping_list", store="rewe", include_done=True))["items"]
    )
    assert "Lachsfilet" not in items
    assert items["Eier"]["amount"] == "2 Stk."
    assert "Kaffee" in items


async def test_more_needed_reopens_only_the_difference(mcp: Client) -> None:
    """Something ticked comes back with what is still missing."""
    await mcp.call("apply_week_plan", days=[{"date": MONDAY, "recipe": PAD_KRA_PAO}])
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    await mcp.call("set_shopping_item_done", id=items["Eier"]["id"])

    await mcp.call("set_day", date=THURSDAY, recipe=LACHS)
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert items["Eier"]["amount"] == "2 Stk."
    assert items["Eier"]["done"] is False


async def test_swap_moves_the_fresh_trip(mcp: Client) -> None:
    """A fresh ingredient follows its meal to another day."""
    await mcp.call("apply_week_plan", days=[{"date": THURSDAY, "recipe": LACHS}])
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert items["Lachsfilet"]["buy_on"] == WEDNESDAY

    await mcp.call("swap_days", first=THURSDAY, second=MONDAY)
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert items["Lachsfilet"]["buy_on"] is None
    plan = await mcp.call("get_plan")
    assert [day["date"] for day in plan["days"]] == [MONDAY]


async def test_inventory_reduces_the_list_and_cooking_uses_it(
    hass: HomeAssistant, mcp: Client
) -> None:
    """Stock is subtracted, cooking takes it out once."""
    await mcp.call(
        "update_inventory",
        items=[
            {"name": "Eier", "amount": 3, "unit": "Stück"},
            {"name": "Hackfleisch", "amount": 1, "unit": "kg", "location": "Tiefkühler"},
        ],
    )
    await mcp.call(
        "apply_week_plan",
        days=[
            {"date": MONDAY, "recipe": PAD_KRA_PAO},
            {"date": THURSDAY, "recipe": LACHS},
        ],
    )
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert items["Eier"]["amount"] == "1 Stk."
    assert "Hackfleisch" not in items

    result = await mcp.call("mark_cooked", date=MONDAY, rating=3)
    assert "2 Stk. Eier" in result["taken_from_inventory"]
    again = await mcp.call("mark_cooked", date=MONDAY)
    assert again["taken_from_inventory"] == []

    inventory = by_name((await mcp.call("get_inventory"))["items"])
    assert inventory["Eier"]["amount"] == 1
    assert inventory["Hackfleisch"]["amount"] == 700


async def test_audit_replaces_a_location_and_clears_the_reminder(
    hass: HomeAssistant, mcp: Client
) -> None:
    """A count removes what is gone, only in the counted location."""
    assert hass.states.get("binary_sensor.kuchenplan_inventur_fallig").state == "on"
    await mcp.call(
        "update_inventory",
        items=[
            {"name": "Milch", "amount": 1, "unit": "l"},
            {"name": "Erbsen", "amount": 450, "unit": "g", "location": "Tiefkühler"},
        ],
    )
    result = await mcp.call(
        "record_inventory_audit",
        location="Kühlschrank",
        replace=True,
        items=[{"name": "Sahne", "amount": 200, "unit": "ml", "best_before": "2026-11-02"}],
    )
    await hass.async_block_till_done()
    assert result == {"counted": 2, "removed": 1}
    names = set(by_name((await mcp.call("get_inventory"))["items"]))
    assert names == {"Sahne", "Erbsen"}
    assert hass.states.get("binary_sensor.kuchenplan_inventur_fallig").state == "off"
    assert hass.states.get("sensor.kuchenplan_lauft_bald_ab").state == "1"

    context = await mcp.call("get_planning_context")
    assert context["expiring_soon"][0]["name"] == "Sahne"


async def test_failed_plan_changes_nothing(mcp: Client) -> None:
    """A broken day leaves the existing plan and recipes alone."""
    await mcp.call("apply_week_plan", days=[{"date": MONDAY, "recipe": PAD_KRA_PAO}])
    failed, error = await mcp.call_raw(
        "apply_week_plan",
        days=[
            {"date": TUESDAY, "recipe": LACHS},
            {"date": WEDNESDAY, "recipe_id": "gibt-es-nicht"},
        ],
    )
    assert failed
    assert "gibt-es-nicht" in error
    plan = await mcp.call("get_plan")
    assert [day["date"] for day in plan["days"]] == [MONDAY]
    assert (await mcp.call("search_recipes", query="Lachs"))["recipes"] == []


async def test_todo_entity_ticks_and_deletes(hass: HomeAssistant, mcp: Client) -> None:
    """The Home Assistant app works on the same lists."""
    await mcp.call("apply_week_plan", days=[{"date": MONDAY, "recipe": PAD_KRA_PAO}])
    await hass.services.async_call(
        "todo",
        "add_item",
        {"item": "Kaffee"},
        target={"entity_id": "todo.kuchenplan_einkauf_rewe"},
        blocking=True,
    )
    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": "Eier (2 Stk.)", "status": "completed"},
        target={"entity_id": "todo.kuchenplan_einkauf_rewe"},
        blocking=True,
    )
    await hass.services.async_call(
        "todo",
        "remove_item",
        {"item": "Hackfleisch (300 g)"},
        target={"entity_id": "todo.kuchenplan_einkauf_rewe"},
        blocking=True,
    )
    items = by_name(
        (await mcp.call("get_shopping_list", store="rewe", include_done=True))["items"]
    )
    assert items["Eier"]["done"] is True
    assert "Hackfleisch" not in items
    assert items["Kaffee"]["source"] == "manual"

    await mcp.call("apply_week_plan", days=[{"date": MONDAY, "recipe": PAD_KRA_PAO}])
    items = (await mcp.call("get_shopping_list", store="rewe"))["items"]
    assert "Hackfleisch" not in by_name(items)


async def test_data_survives_a_reload(hass: HomeAssistant, mcp: Client) -> None:
    """Plan and inventory are still there after a reload."""
    await mcp.call("apply_week_plan", days=[{"date": MONDAY, "recipe": PAD_KRA_PAO}])
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.kuchenplan_morgen").state == "Pad Kra Pao (20 Min.)"


async def test_services_and_websocket(
    hass: HomeAssistant, mcp: Client, hass_ws_client
) -> None:
    """Automations and the panel reach the same operations."""
    await hass.services.async_call(
        DOMAIN,
        "apply_week_plan",
        {"days": [{"date": MONDAY, "recipe": PAD_KRA_PAO}]},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("todo.kuchenplan_einkauf_rewe").state == "3"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    assert (await client.receive_json())["success"]
    snapshot = (await client.receive_json())["event"]
    assert snapshot["days"][0]["recipe"]["name"] == "Pad Kra Pao"
    assert [store["id"] for store in snapshot["stores"]] == ["rewe", "lidl"]

    async def call(operation: str, **args) -> tuple[dict, dict | None]:
        """Call an operation and return its result and the update it caused."""
        await client.send_json_auto_id(
            {"type": f"{DOMAIN}/call", "operation": operation, "args": args}
        )
        update = None
        while True:
            message = await client.receive_json()
            if message["type"] == "result":
                return message, update
            update = message

    result, update = await call("mark_cooked", date=MONDAY, rating=1)
    assert result["success"]
    assert update["event"]["days"][0]["rating"] == 1

    result, _ = await call("clear_day", date=TUESDAY)
    assert result["success"] is False


async def test_adhoc_meal_shops_and_cooks_without_touching_the_plan(
    hass: HomeAssistant, mcp: Client
) -> None:
    """A spontaneous meal joins the lists, cooking it ends up in the history."""
    await mcp.call("apply_week_plan", days=[{"date": MONDAY, "recipe": PAD_KRA_PAO}])
    await mcp.call("update_inventory", items=[{"name": "Paprika", "amount": 1, "unit": "Stk."}])

    meal = await mcp.call("add_adhoc_meal", recipe=LACHS)
    plan = await mcp.call("get_plan")
    assert [day["date"] for day in plan["days"]] == [MONDAY]
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert items["Lachsfilet"]["buy_on"] is None  # Fresh, but needed now
    assert items["Eier"]["amount"] == "4 Stk."
    assert items["Paprika"]["amount"] == "2 Stk."  # One is at home
    assert {item["name"] for item in meal["shopping"]} >= {"Lachsfilet", "Eier"}

    result = await mcp.call("mark_adhoc_cooked", id=meal["id"], rating=3)
    assert result["taken_from_inventory"] == ["1 Stk. Paprika"]
    items = by_name((await mcp.call("get_shopping_list", store="rewe"))["items"])
    assert "Lachsfilet" not in items
    assert items["Eier"]["amount"] == "2 Stk."

    context = await mcp.call("get_planning_context")
    assert context["adhoc_meals"] == []
    assert context["recent_meals"][-1]["title"] == "Lachs"
    lachs = next(item for item in context["recipes"] if item["name"] == "Lachs")
    assert lachs["last_cooked"] == "2026-11-01"
    assert lachs["average_rating"] == 3


async def test_adhoc_without_shopping_and_removal(mcp: Client) -> None:
    """With everything at home nothing is listed, removing frees the list again."""
    await mcp.call("upsert_recipe", **LACHS)
    meal = await mcp.call("add_adhoc_meal", recipe_id="lachs", shop=False, servings=4)
    assert meal["shopping"] == []
    assert (await mcp.call("get_shopping_list"))["items"] == []

    second = await mcp.call("add_adhoc_meal", recipe_id="lachs")
    assert (await mcp.call("get_shopping_list", store="rewe"))["items"]
    await mcp.call("remove_adhoc_meal", id=second["id"])
    assert (await mcp.call("get_shopping_list"))["items"] == []

    failed, error = await mcp.call_raw("add_adhoc_meal", recipe_id="gibt-es-nicht")
    assert failed
    assert "gibt-es-nicht" in error


async def test_old_stored_data_without_adhoc_still_loads(
    hass: HomeAssistant, mcp: Client, hass_storage
) -> None:
    """Data written before ad hoc meals existed keeps working."""
    await mcp.call("upsert_recipe", **LACHS)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass_storage[DOMAIN]["data"].pop("adhoc")
    hass_storage[DOMAIN]["data"].pop("cook_log")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (await mcp.call("search_recipes", query="Lachs"))["recipes"]


async def test_what_can_i_cook_ranks_by_what_is_at_home(mcp: Client) -> None:
    """Recipes that fit come first, what expires soon decides between them."""
    await mcp.call("upsert_recipe", **PAD_KRA_PAO)
    await mcp.call("upsert_recipe", **LACHS)
    await mcp.call(
        "update_inventory",
        items=[
            {"name": "Hackfleisch", "amount": 500, "unit": "g", "best_before": "2026-11-02"},
            {"name": "Thai-Basilikum", "amount": 1, "unit": "Bund"},
            {"name": "Eier", "amount": 1, "unit": "Stk."},
            {"name": "Paprika", "amount": 1, "unit": "kg"},
        ],
    )

    result = await mcp.call("what_can_i_cook")
    assert result["can_cook_now"] == []
    first, second = result["needs_a_little"]
    assert first["name"] == "Pad Kra Pao"
    assert first["missing"] == ["1 Stk. Eier"]  # Only what is still needed
    assert first["uses_expiring"] == ["Hackfleisch"]
    assert second["name"] == "Lachs"
    assert second["maybe_at_home"] == ["Paprika"]  # Other unit, cannot be compared
    assert "Lachsfilet" in " ".join(second["missing"])

    await mcp.call("update_inventory", items=[{"name": "Eier", "amount": 6, "unit": "Stk."}])
    result = await mcp.call("what_can_i_cook", max_missing=0)
    assert [item["name"] for item in result["can_cook_now"]] == ["Pad Kra Pao"]
    assert result["needs_a_little"] == []

    # Doubling the servings needs more than is at home.
    result = await mcp.call("what_can_i_cook", servings=4)
    pad = next(item for item in result["needs_a_little"] if item["name"] == "Pad Kra Pao")
    assert "100 g Hackfleisch" in pad["missing"]
