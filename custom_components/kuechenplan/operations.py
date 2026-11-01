"""Operations offered over MCP, as services and to the panel, defined only once."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import probatio as p

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonObjectType

from .const import (
    EVENT_MEAL_COOKED,
    EVENT_PLAN_APPLIED,
    LOCATIONS,
    PLAN_HORIZON_DAYS,
    STATUS_COOKED,
    STATUS_SKIPPED,
)
from .store import KuechenplanStore, name_key, parse_date

AMOUNT = p.Any(int, float, None)
DATE_HELP = "Date as YYYY-MM-DD"

INGREDIENT = p.Schema(
    {
        p.Required("name"): p.All(str, p.Length(min=1, max=120)),
        p.Optional(
            "amount", description="Amount for the recipe's servings, null for 'etwas'"
        ): AMOUNT,
        p.Optional("unit", description="For example g, kg, ml, l, Stk., EL, Bund"): p.Any(
            str, None
        ),
        p.Optional("store", description="Store ID where this is bought"): p.Any(
            str, None
        ),
        p.Optional("section", description="Aisle, see the store's sections"): p.Any(
            str, None
        ),
        p.Optional(
            "fresh",
            description="Spoils quickly, so meals after the fresh shopping day get "
            "it on that trip",
        ): bool,
        p.Optional(
            "staple",
            description="Usually at home, like oil or salt: shown in the recipe, "
            "never put on the shopping list",
        ): bool,
    }
)
STEP = p.Schema(
    {
        p.Required("text"): p.All(str, p.Length(min=1, max=1000)),
        p.Optional("minutes", description="Offers a timer for this step"): p.All(
            int, p.Range(min=1, max=600)
        ),
    }
)
RECIPE = p.Schema(
    {
        p.Optional("id", description="Omit to derive it from the name"): str,
        p.Required("name"): p.All(str, p.Length(min=1, max=120)),
        p.Optional("summary", description="One short line"): str,
        p.Required("servings"): p.All(int, p.Range(min=1, max=50)),
        p.Required("minutes", description="Total cooking time"): p.All(
            int, p.Range(min=1, max=1440)
        ),
        p.Required("ingredients"): [INGREDIENT],
        p.Required("steps"): [STEP],
        p.Optional("tags"): [str],
        p.Optional("rice", description="Needs the rice cooker"): bool,
        p.Optional("source", description="Where the recipe comes from"): p.Any(
            str, None
        ),
    }
)
OFFER = p.Schema(
    {
        p.Required("item", description="Ingredient the offer applies to"): str,
        p.Optional("store", description="Store ID, moves the item to that list"): str,
        p.Optional("label", description="For example '-25 %' or '1,99 €'"): str,
    }
)
DAY = p.Schema(
    {
        p.Required("date", description=DATE_HELP): str,
        p.Optional("recipe", description="A new or changed recipe"): RECIPE,
        p.Optional("recipe_id", description="A stored recipe"): str,
        p.Optional("title", description="A meal without recipe, like 'Reste'"): str,
        p.Optional("servings"): p.All(int, p.Range(min=1, max=50)),
        p.Optional("note"): str,
        p.Optional(
            "offers", description="Only offers verified in a current leaflet"
        ): [OFFER],
    }
)
INVENTORY_ITEM = p.Schema(
    {
        p.Optional("id"): str,
        p.Optional("name"): p.All(str, p.Length(min=1, max=120)),
        p.Optional("amount", description="New amount, 0 removes the item"): AMOUNT,
        p.Optional("unit"): p.Any(str, None),
        p.Optional("location"): p.In(LOCATIONS),
        p.Optional("best_before", description=DATE_HELP): p.Any(str, None),
        p.Optional("remove"): bool,
    }
)


@dataclass(frozen=True)
class Operation:
    """One thing that can be done with the household data."""

    name: str
    description: str
    schema: p.Schema
    handler: Callable[[KuechenplanStore, dict[str, Any]], JsonObjectType]
    read_only: bool = False

    def run(self, store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
        """Validate the arguments and run the operation."""
        try:
            validated = self.schema(args)
        except p.Invalid as err:
            raise HomeAssistantError(str(err)) from err
        result = self.handler(store, validated)
        _fire_events(store.hass, self.name, validated)
        return result


@callback
def _fire_events(hass: HomeAssistant, operation: str, args: dict[str, Any]) -> None:
    """Announce what automations may want to react to."""
    if operation in ("apply_week_plan", "set_day", "swap_days", "clear_day"):
        hass.bus.async_fire(EVENT_PLAN_APPLIED, {"operation": operation})
    elif operation == "mark_cooked":
        hass.bus.async_fire(
            EVENT_MEAL_COOKED,
            {"date": args["date"], "status": args.get("status", STATUS_COOKED)},
        )
    elif operation == "mark_adhoc_cooked":
        hass.bus.async_fire(EVENT_MEAL_COOKED, {"status": STATUS_COOKED})


def _get_plan(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    today = store.today()
    start = parse_date(args["start"]) if args.get("start") else today
    end = (
        parse_date(args["end"])
        if args.get("end")
        else start + timedelta(days=PLAN_HORIZON_DAYS)
    )
    return {"days": store.days_between(start, end)}


def _get_recipe(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    if (recipe := store.recipes.get(args["recipe_id"])) is None:
        raise HomeAssistantError(f"Unknown recipe: {args['recipe_id']}")
    return recipe


def _search_recipes(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    query = name_key(args.get("query", ""))
    return {
        "recipes": [
            {
                "id": recipe["id"],
                "name": recipe["name"],
                "minutes": recipe["minutes"],
                "tags": recipe["tags"],
            }
            for recipe in store.recipes.values()
            if query in name_key(recipe["name"])
            or any(query in name_key(tag) for tag in recipe["tags"])
            or any(query in name_key(item["name"]) for item in recipe["ingredients"])
        ]
    }


def _get_shopping(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return {
        "items": [
            store.shopping_view(item)
            for item in store.shopping
            if args.get("store") in (None, item["store"])
            and (args.get("include_done", False) or not item["done"])
        ]
    }


def _get_inventory(store: KuechenplanStore, _: dict[str, Any]) -> JsonObjectType:
    return {
        "items": store.sorted_inventory(),
        "expiring_soon": store.expiring(),
        "audit": store.audit_view(),
    }


def _what_can_i_cook(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return store.what_can_i_cook(args.get("max_missing", 3), args.get("servings"))


def _apply_week_plan(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return store.async_apply_plan(args["days"], args.get("replace", True))


def _set_day(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return store.async_apply_plan([args], replace=False)


def _clear_day(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_clear_day(parse_date(args["date"]))
    return {"success": True}


def _swap_days(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_swap_days(parse_date(args["first"]), parse_date(args["second"]))
    return {"success": True}


def _mark_cooked(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return store.async_mark_cooked(
        parse_date(args["date"]),
        args.get("status", STATUS_COOKED),
        args.get("rating"),
        args.get("comment"),
        args.get("servings"),
    )


def _add_adhoc(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    meal = store.async_add_adhoc(
        args.get("recipe_id"),
        args.get("recipe"),
        args.get("servings"),
        args.get("shop", True),
    )
    return {
        "id": meal["id"],
        "title": meal["title"],
        "servings": meal["servings"],
        "shopping": [
            store.shopping_view(item)
            for item in store.shopping
            if meal["title"] in item["for"] and not item["done"]
        ],
    }


def _remove_adhoc(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_remove_adhoc(args["id"])
    return {"success": True}


def _cook_adhoc(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return store.async_cook_adhoc(
        args["id"], args.get("rating"), args.get("comment"), args.get("servings")
    )


def _upsert_recipe(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return {"recipe_id": store.async_upsert_recipe(args)}


def _add_shopping(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return {
        "items": [
            store.shopping_view(store.async_add_shopping_item(**item))
            for item in args["items"]
        ]
    }


def _set_shopping_done(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_set_shopping_done(args["id"], args.get("done", True))
    return {"success": True}


def _remove_shopping(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_remove_shopping_items(args["ids"])
    return {"success": True}


def _set_store_sections(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_set_store_sections(args["store"], args["sections"])
    return {"success": True}


def _update_inventory(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_update_inventory(args["items"])
    return {"success": True, "count": len(store.inventory)}


def _record_audit(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    return store.async_record_audit(
        args.get("items"), args.get("location"), args.get("replace", False)
    )


def _set_preferences(store: KuechenplanStore, args: dict[str, Any]) -> JsonObjectType:
    store.async_set_preferences(args["text"])
    return {"success": True}


OPERATIONS: dict[str, Operation] = {
    operation.name: operation
    for operation in (
        Operation(
            "get_planning_context",
            "Start here before planning. Returns date, preferences, stores and "
            "aisles, upcoming plan, recent meals with ratings, known recipes, "
            "inventory with what expires soon, and open shopping items.",
            p.Schema({}),
            lambda store, _: store.planning_context(),
            read_only=True,
        ),
        Operation(
            "get_plan",
            "Return planned days with full recipes. Defaults to the next two weeks.",
            p.Schema(
                {
                    p.Optional("start", description=DATE_HELP): str,
                    p.Optional("end", description=DATE_HELP): str,
                }
            ),
            _get_plan,
            read_only=True,
        ),
        Operation(
            "get_recipe",
            "Return a stored recipe.",
            p.Schema({p.Required("recipe_id"): str}),
            _get_recipe,
            read_only=True,
        ),
        Operation(
            "search_recipes",
            "Find stored recipes by name, tag or ingredient.",
            p.Schema({p.Optional("query"): str}),
            _search_recipes,
            read_only=True,
        ),
        Operation(
            "get_shopping_list",
            "Return the shopping list, optionally for one store.",
            p.Schema(
                {p.Optional("store"): str, p.Optional("include_done"): bool}
            ),
            _get_shopping,
            read_only=True,
        ),
        Operation(
            "get_inventory",
            "Return what is at home, whatever expires first on top, and when the "
            "last count was.",
            p.Schema({}),
            _get_inventory,
            read_only=True,
        ),
        Operation(
            "what_can_i_cook",
            "Answer 'what can I cook with what is at home?'. Ranks stored recipes, what "
            "expires soon first, and returns the inventory. If nothing fits well, suggest "
            "new dishes from the inventory and offer to save one with add_adhoc_meal. If "
            "the inventory is empty or the last count is old, say so and suggest a count.",
            p.Schema(
                {
                    p.Optional(
                        "max_missing", description="Allowed missing ingredients, default 3"
                    ): p.All(int, p.Range(min=0, max=20)),
                    p.Optional("servings"): p.All(int, p.Range(min=1, max=50)),
                }
            ),
            _what_can_i_cook,
            read_only=True,
        ),
        Operation(
            "apply_week_plan",
            "Write the plan for one or more days. Calendar, shopping lists, sensors "
            "and the kitchen display follow from this; never write those directly. "
            "Safe to repeat. Other planned days in the same weeks are removed unless "
            "replace is false, cooked days are kept. The lists subtract the inventory "
            "and keep what was already ticked off and what people added themselves.",
            p.Schema(
                {
                    p.Required("days"): p.All([DAY], p.Length(min=1, max=31)),
                    p.Optional("replace"): bool,
                }
            ),
            _apply_week_plan,
        ),
        Operation(
            "set_day",
            "Change a single day, leaving the rest of the week alone.",
            DAY,
            _set_day,
        ),
        Operation(
            "clear_day",
            "Remove a planned day.",
            p.Schema({p.Required("date", description=DATE_HELP): str}),
            _clear_day,
        ),
        Operation(
            "swap_days",
            "Swap the meals of two days. The fresh shopping trip follows the meal.",
            p.Schema(
                {
                    p.Required("first", description=DATE_HELP): str,
                    p.Required("second", description=DATE_HELP): str,
                }
            ),
            _swap_days,
        ),
        Operation(
            "mark_cooked",
            "Record that a meal was cooked or skipped, with an optional rating. "
            "Cooking takes the ingredients out of the inventory once.",
            p.Schema(
                {
                    p.Required("date", description=DATE_HELP): str,
                    p.Optional("status"): p.In([STATUS_COOKED, STATUS_SKIPPED]),
                    p.Optional(
                        "rating", description="3 = again, 2 = fine, 1 = never again"
                    ): p.All(int, p.Range(min=1, max=3)),
                    p.Optional("comment"): str,
                    p.Optional("servings", description="Servings actually cooked"): p.All(
                        int, p.Range(min=1, max=50)
                    ),
                }
            ),
            _mark_cooked,
        ),
        Operation(
            "add_adhoc_meal",
            "Cook something spontaneously, without touching the week plan. Takes a "
            "stored recipe or a new one. What is missing lands on the shopping lists "
            "right away and the kitchen display offers to cook it. With shop false "
            "nothing is added to the lists, for when everything is at home.",
            p.Schema(
                {
                    p.Optional("recipe_id", description="A stored recipe"): str,
                    p.Optional("recipe", description="A new or changed recipe"): RECIPE,
                    p.Optional("servings"): p.All(int, p.Range(min=1, max=50)),
                    p.Optional("shop"): bool,
                }
            ),
            _add_adhoc,
        ),
        Operation(
            "remove_adhoc_meal",
            "Drop a spontaneous meal and what it still needed on the lists.",
            p.Schema({p.Required("id"): str}),
            _remove_adhoc,
        ),
        Operation(
            "mark_adhoc_cooked",
            "Record a spontaneous meal as cooked, with an optional rating. Takes the "
            "ingredients out of the inventory.",
            p.Schema(
                {
                    p.Required("id"): str,
                    p.Optional(
                        "rating", description="3 = again, 2 = fine, 1 = never again"
                    ): p.All(int, p.Range(min=1, max=3)),
                    p.Optional("comment"): str,
                    p.Optional("servings", description="Servings actually cooked"): p.All(
                        int, p.Range(min=1, max=50)
                    ),
                }
            ),
            _cook_adhoc,
        ),
        Operation(
            "upsert_recipe",
            "Store a recipe without planning it, or change one.",
            RECIPE,
            _upsert_recipe,
        ),
        Operation(
            "add_shopping_items",
            "Add items that do not come from a recipe.",
            p.Schema(
                {
                    p.Required("items"): [
                        p.Schema(
                            {
                                p.Required("name"): p.All(
                                    str, p.Length(min=1, max=120)
                                ),
                                p.Optional("store"): p.Any(str, None),
                                p.Optional("amount"): AMOUNT,
                                p.Optional("unit"): p.Any(str, None),
                                p.Optional("section"): p.Any(str, None),
                                p.Optional("buy_on", description=DATE_HELP): p.Any(
                                    str, None
                                ),
                            }
                        )
                    ]
                }
            ),
            _add_shopping,
        ),
        Operation(
            "set_shopping_item_done",
            "Tick or untick a shopping item.",
            p.Schema({p.Required("id"): str, p.Optional("done"): bool}),
            _set_shopping_done,
        ),
        Operation(
            "remove_shopping_items",
            "Remove shopping items. Items from the plan stay away unless more is "
            "needed later.",
            p.Schema({p.Required("ids"): [str]}),
            _remove_shopping,
        ),
        Operation(
            "set_store_sections",
            "Set the order in which a store's aisles are walked.",
            p.Schema({p.Required("store"): str, p.Required("sections"): [str]}),
            _set_store_sections,
        ),
        Operation(
            "update_inventory",
            "Add, change or remove things at home, by id or by name. Use this for "
            "single changes, like 'the milk is empty'.",
            p.Schema({p.Required("items"): [INVENTORY_ITEM]}),
            _update_inventory,
        ),
        Operation(
            "record_inventory_audit",
            "Record a finished count of the fridge, freezer or pantry, for example "
            "after someone listed the contents or sent a photo. With replace, "
            "everything in the location that is not listed is removed. Confirm with "
            "the person before replacing based on a photo.",
            p.Schema(
                {
                    p.Optional("items"): [INVENTORY_ITEM],
                    p.Optional("location"): p.In(LOCATIONS),
                    p.Optional("replace"): bool,
                }
            ),
            _record_audit,
        ),
        Operation(
            "set_preferences",
            "Replace the notes on what to keep in mind when planning: tastes, "
            "allergies, portion sizes, weekly rhythm. Read them first, this overwrites.",
            p.Schema({p.Required("text"): p.All(str, p.Length(max=4000))}),
            _set_preferences,
        ),
    )
}
