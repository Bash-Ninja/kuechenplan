"""Household data of the Küchenplan integration and the logic working on it."""

from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha1
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.ulid import ulid_now

from .const import (
    ADHOC_RETENTION_DAYS,
    DEFAULT_LOCATION,
    DEFAULT_SECTIONS,
    DOMAIN,
    EXPIRING_DAYS,
    FALLBACK_SECTION,
    HISTORY_DAYS,
    LOCATIONS,
    MANUAL_DONE_RETENTION_DAYS,
    PLAN_HORIZON_DAYS,
    RECENT_MEAL_DAYS,
    SIGNAL_UPDATED,
    STATUS_COOKED,
    STATUS_PLANNED,
)

STORAGE_VERSION = 1
SAVE_DELAY = 1
EPSILON = 0.001

# Everything is stored in a base unit, so 500 g and 1 kg add up.
UNITS = {
    "g": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("ml", 1),
    "l": ("ml", 1000),
    "stk": ("Stk.", 1),
    "stk.": ("Stk.", 1),
    "stück": ("Stk.", 1),
    "stueck": ("Stk.", 1),
}


@dataclass(frozen=True)
class Settings:
    """Settings from the config entry."""

    stores: dict[str, str]
    plan_weekdays: list[int]
    fresh_weekday: int
    audit_interval_days: int


def name_key(name: str) -> str:
    """Return the form of a name used to compare it."""
    return " ".join(name.casefold().split())


def normalize_amount(
    amount: float | None, unit: str | None
) -> tuple[float | None, str | None]:
    """Convert an amount to its base unit."""
    if not unit or not unit.strip():
        return amount, None
    unit = unit.strip()
    base, factor = UNITS.get(unit.casefold(), (unit, 1))
    return (None if amount is None else round(amount * factor, 3)), base


def format_amount(amount: float | None, unit: str | None) -> str:
    """Return an amount for display."""
    if amount is None:
        return unit or ""
    if unit == "g" and amount >= 1000:
        amount, unit = amount / 1000, "kg"
    elif unit == "ml" and amount >= 1000:
        amount, unit = amount / 1000, "l"
    text = f"{round(amount, 2):g}".replace(".", ",")
    return f"{text} {unit}" if unit else text


def parse_date(value: str) -> date:
    """Parse an ISO date from a caller."""
    try:
        return date.fromisoformat(value)
    except ValueError as err:
        raise HomeAssistantError(f"Invalid date, expected YYYY-MM-DD: {value}") from err


class KuechenplanStore:
    """Hold recipes, plan, shopping and inventory, and keep them consistent."""

    def __init__(self, hass: HomeAssistant, settings: Settings) -> None:
        """Initialize the store."""
        self.hass = hass
        self.settings = settings
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, DOMAIN, private=True
        )
        self.recipes: dict[str, dict[str, Any]] = {}
        self.days: dict[str, dict[str, Any]] = {}
        self.manual: list[dict[str, Any]] = []
        self.bought: dict[str, float] = {}
        self.hidden: dict[str, float] = {}
        self.inventory: list[dict[str, Any]] = []
        self.audit: dict[str, Any] = {"last_at": None, "counted": 0}
        self.preferences = ""
        self.store_sections: dict[str, list[str]] = {}
        self.adhoc: list[dict[str, Any]] = []
        self.cook_log: list[dict[str, Any]] = []
        self.shopping: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        """Load the stored data."""
        if (data := await self._store.async_load()) is not None:
            self.recipes = data["recipes"]
            self.days = data["days"]
            self.manual = data["manual"]
            self.bought = data["bought"]
            self.hidden = data["hidden"]
            self.inventory = data["inventory"]
            self.audit = data["audit"]
            self.preferences = data["preferences"]
            self.store_sections = data["store_sections"]
            self.adhoc = data.get("adhoc", [])
            self.cook_log = data.get("cook_log", [])
        self.async_refresh(notify=False)

    @callback
    def async_refresh(self, notify: bool = True) -> None:
        """Bring date dependent data up to date, runs at startup and midnight."""
        cutoff = (self.today() - timedelta(days=HISTORY_DAYS)).isoformat()
        self.days = {key: day for key, day in self.days.items() if key >= cutoff}
        self.cook_log = [meal for meal in self.cook_log if meal["date"] >= cutoff]
        stale = (
            dt_util.utcnow() - timedelta(days=ADHOC_RETENTION_DAYS)
        ).isoformat()
        self.adhoc = [meal for meal in self.adhoc if meal["created_at"] >= stale]
        self._rebuild_shopping()
        if notify:
            self._async_changed()

    @staticmethod
    def today() -> date:
        """Return the local date."""
        return dt_util.now().date()

    # --- Plan ---

    def _meal_recipe(self, day: dict[str, Any]) -> dict[str, Any] | None:
        """Return the recipe of a planned day."""
        return self.recipes.get(day["recipe_id"]) if day.get("recipe_id") else None

    def day_view(self, day: dict[str, Any]) -> dict[str, Any]:
        """Return a day with its recipe, ready for display."""
        recipe = self._meal_recipe(day)
        title = recipe["name"] if recipe else day.get("title") or "Unbekannt"
        minutes = recipe["minutes"] if recipe else None
        return {
            **day,
            "title": title,
            "label": f"{title} ({minutes} Min.)" if minutes else title,
            "minutes": minutes,
            "rice": bool(recipe and recipe.get("rice")),
            "recipe": recipe,
        }

    def get_day(self, when: date) -> dict[str, Any] | None:
        """Return a day for display, or None if nothing is planned."""
        day = self.days.get(when.isoformat())
        return self.day_view(day) if day else None

    def days_between(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return the planned days of a period, both ends included."""
        return [
            self.day_view(self.days[key])
            for key in sorted(self.days)
            if start.isoformat() <= key <= end.isoformat()
        ]

    def next_plan_day(self) -> date:
        """Return the next day after today that should have a meal."""
        when = self.today() + timedelta(days=1)
        for _ in range(7):
            if when.weekday() in self.settings.plan_weekdays:
                break
            when += timedelta(days=1)
        return when

    def plan_missing(self) -> bool:
        """Return if the next day that should have a meal has none."""
        return self.next_plan_day().isoformat() not in self.days

    @callback
    def async_upsert_recipe(self, recipe: dict[str, Any]) -> str:
        """Add or replace a recipe and return its ID."""
        recipe_id = self._store_recipe(recipe)
        self._rebuild_shopping()
        self._async_changed()
        return recipe_id

    def _store_recipe(self, recipe: dict[str, Any]) -> str:
        """Normalize and store a recipe."""
        recipe_id = recipe.get("id") or slugify(recipe["name"])
        ingredients = []
        for ingredient in recipe["ingredients"]:
            amount, unit = normalize_amount(
                ingredient.get("amount"), ingredient.get("unit")
            )
            ingredients.append(
                {
                    "name": ingredient["name"],
                    "amount": amount,
                    "unit": unit,
                    "store": self._known_store(ingredient.get("store")),
                    "section": ingredient.get("section") or FALLBACK_SECTION,
                    "fresh": ingredient.get("fresh", False),
                    "staple": ingredient.get("staple", False),
                }
            )
        self.recipes[recipe_id] = {
            "id": recipe_id,
            "name": recipe["name"],
            "summary": recipe.get("summary", ""),
            "servings": recipe["servings"],
            "minutes": recipe["minutes"],
            "ingredients": ingredients,
            "steps": recipe["steps"],
            "tags": recipe.get("tags", []),
            "rice": recipe.get("rice", False),
            "source": recipe.get("source"),
        }
        return recipe_id

    def _known_store(self, store: str | None) -> str:
        """Return a valid store ID, accepting IDs and names."""
        stores = self.settings.stores
        if store:
            wanted = slugify(store)
            if wanted in stores:
                return wanted
        return next(iter(stores))

    def _build_day(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Turn a day from a caller into a stored day."""
        if entry.get("recipe"):
            recipe_id = self._store_recipe(entry["recipe"])
        elif recipe_id := entry.get("recipe_id"):
            if recipe_id not in self.recipes:
                raise HomeAssistantError(f"Unknown recipe: {recipe_id}")
        elif not entry.get("title"):
            raise HomeAssistantError(
                f"{entry['date']}: needs one of recipe, recipe_id or title"
            )
        recipe = self.recipes.get(recipe_id) if recipe_id else None
        return {
            "date": parse_date(entry["date"]).isoformat(),
            "recipe_id": recipe_id,
            "title": entry.get("title") if recipe is None else None,
            "servings": entry.get("servings")
            or (recipe["servings"] if recipe else None),
            "note": entry.get("note", ""),
            "offers": entry.get("offers", []),
            "status": STATUS_PLANNED,
            "rating": None,
            "comment": None,
        }

    @callback
    def async_apply_plan(
        self, entries: list[dict[str, Any]], replace: bool = True
    ) -> dict[str, Any]:
        """Write several days, replacing the rest of the weeks they belong to."""
        dates = [parse_date(entry["date"]).isoformat() for entry in entries]
        if len(set(dates)) != len(dates):
            raise HomeAssistantError("Every date may appear only once")
        # Build first, so a broken day leaves the existing plan untouched.
        previous = dict(self.recipes)
        try:
            built = [self._build_day(entry) for entry in entries]
        except HomeAssistantError:
            self.recipes = previous
            raise

        if replace:
            for key in {self._monday(value) for value in dates}:
                monday = date.fromisoformat(key)
                for offset in range(7):
                    day_key = (monday + timedelta(days=offset)).isoformat()
                    day = self.days.get(day_key)
                    if day and day["status"] == STATUS_PLANNED and day_key not in dates:
                        del self.days[day_key]

        kept = []
        for day in built:
            existing = self.days.get(day["date"])
            if existing and existing["status"] != STATUS_PLANNED:
                kept.append(day["date"])
                continue
            self.days[day["date"]] = day

        self._rebuild_shopping()
        self._async_changed()
        return {
            "planned_days": [day["date"] for day in built if day["date"] not in kept],
            "kept_already_cooked": kept,
            "shopping": self._shopping_counts(),
        }

    @staticmethod
    def _monday(value: str) -> str:
        """Return the Monday of the week of a date."""
        when = date.fromisoformat(value)
        return (when - timedelta(days=when.weekday())).isoformat()

    @callback
    def async_clear_day(self, when: date) -> None:
        """Remove a planned day."""
        if self.days.pop(when.isoformat(), None) is None:
            raise HomeAssistantError(f"Nothing planned on {when}")
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_swap_days(self, first: date, second: date) -> None:
        """Swap two days, one of them may be empty."""
        first_key, second_key = first.isoformat(), second.isoformat()
        first_day = self.days.pop(first_key, None)
        second_day = self.days.pop(second_key, None)
        if first_day is None and second_day is None:
            raise HomeAssistantError("Both days are empty")
        if first_day is not None:
            self.days[second_key] = {**first_day, "date": second_key}
        if second_day is not None:
            self.days[first_key] = {**second_day, "date": first_key}
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_mark_cooked(
        self,
        when: date,
        status: str = STATUS_COOKED,
        rating: int | None = None,
        comment: str | None = None,
        servings: int | None = None,
    ) -> dict[str, Any]:
        """Record what happened to a meal and use up the ingredients once."""
        day = self.days.get(when.isoformat())
        if day is None:
            raise HomeAssistantError(f"Nothing planned on {when}")
        used: list[str] = []
        if status == STATUS_COOKED and day["status"] != STATUS_COOKED:
            used = self._consume_inventory(day, servings)
        day["status"] = status
        if servings:
            day["servings"] = servings
        if rating is not None:
            day["rating"] = rating
        if comment is not None:
            day["comment"] = comment
        self._rebuild_shopping()
        self._async_changed()
        return {"status": status, "taken_from_inventory": used}

    def _consume_inventory(
        self, day: dict[str, Any], servings: int | None = None
    ) -> list[str]:
        """Take the ingredients of a cooked meal out of the inventory."""
        recipe = self._meal_recipe(day)
        if recipe is None:
            return []
        factor = (servings or day["servings"] or recipe["servings"]) / recipe["servings"]
        used = []
        for ingredient in recipe["ingredients"]:
            if ingredient["amount"] is None:
                continue
            remaining = ingredient["amount"] * factor
            matches = sorted(
                (
                    item
                    for item in self.inventory
                    if name_key(item["name"]) == name_key(ingredient["name"])
                    and item["unit"] == ingredient["unit"]
                    and item["amount"] is not None
                ),
                key=lambda item: item["best_before"] or "9999",
            )
            for item in matches:
                taken = min(item["amount"], remaining)
                item["amount"] = round(item["amount"] - taken, 3)
                remaining -= taken
                used.append(f"{format_amount(taken, item['unit'])} {item['name']}")
                if item["amount"] <= EPSILON:
                    self.inventory.remove(item)
                if remaining <= EPSILON:
                    break
        return used

    # --- Ad hoc meals ---

    def adhoc_view(self, meal: dict[str, Any]) -> dict[str, Any]:
        """Return an ad hoc meal with its recipe, ready for display."""
        recipe = self.recipes[meal["recipe_id"]]
        return {
            **meal,
            "title": recipe["name"],
            "minutes": recipe["minutes"],
            "rice": recipe["rice"],
            "recipe": recipe,
        }

    @callback
    def async_add_adhoc(
        self,
        recipe_id: str | None = None,
        recipe: dict[str, Any] | None = None,
        servings: int | None = None,
        shop: bool = True,
    ) -> dict[str, Any]:
        """Add a meal outside the plan, its ingredients join the shopping lists."""
        if recipe:
            recipe_id = self._store_recipe(recipe)
        if not recipe_id or recipe_id not in self.recipes:
            raise HomeAssistantError(f"Unknown recipe: {recipe_id}")
        meal = {
            "id": ulid_now(),
            "recipe_id": recipe_id,
            "servings": servings or self.recipes[recipe_id]["servings"],
            "shop": shop,
            "created_at": dt_util.utcnow().isoformat(),
        }
        self.adhoc.append(meal)
        self._rebuild_shopping()
        self._async_changed()
        return self.adhoc_view(meal)

    def _find_adhoc(self, meal_id: str) -> dict[str, Any]:
        """Return an ad hoc meal."""
        for meal in self.adhoc:
            if meal["id"] == meal_id:
                return meal
        raise HomeAssistantError(f"Unknown ad hoc meal: {meal_id}")

    @callback
    def async_remove_adhoc(self, meal_id: str) -> None:
        """Drop an ad hoc meal and what it still needed."""
        self.adhoc.remove(self._find_adhoc(meal_id))
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_cook_adhoc(
        self,
        meal_id: str,
        rating: int | None = None,
        comment: str | None = None,
        servings: int | None = None,
    ) -> dict[str, Any]:
        """Record an ad hoc meal as cooked and use up the ingredients."""
        meal = self._find_adhoc(meal_id)
        used = self._consume_inventory(meal, servings)
        self.adhoc.remove(meal)
        self.cook_log.append(
            {
                "date": self.today().isoformat(),
                "recipe_id": meal["recipe_id"],
                "title": self.recipes[meal["recipe_id"]]["name"],
                "servings": servings or meal["servings"],
                "status": STATUS_COOKED,
                "rating": rating,
                "comment": comment,
                "note": "",
            }
        )
        self._rebuild_shopping()
        self._async_changed()
        return {"status": STATUS_COOKED, "taken_from_inventory": used}

    # --- Shopping ---

    def sections(self, store: str) -> list[str]:
        """Return the sections of a store in walking order."""
        return self.store_sections.get(store, DEFAULT_SECTIONS)

    def _buy_on(self, meal: date, fresh: bool, today: date) -> str | None:
        """Return when an ingredient should be bought, None means the next trip."""
        if not fresh:
            return None
        trip = meal - timedelta(days=(meal.weekday() - self.settings.fresh_weekday) % 7)
        return trip.isoformat() if today <= trip < meal else None

    def _rebuild_shopping(self) -> None:
        """Derive the shopping lists from plan, inventory and what was bought."""
        today = self.today()
        stock: dict[tuple[str, str | None], float] = {}
        maybe_home: set[str] = set()
        for item in self.inventory:
            if item["amount"] is None:
                maybe_home.add(name_key(item["name"]))
            else:
                key = (name_key(item["name"]), item["unit"])
                stock[key] = stock.get(key, 0) + item["amount"]

        rows: dict[tuple[str, str | None], dict[str, Any]] = {}
        # Ad hoc meals come first, they are cooked before anything planned.
        for meal in self.adhoc:
            recipe = self.recipes.get(meal["recipe_id"])
            if not recipe or not meal["shop"]:
                continue
            factor = meal["servings"] / recipe["servings"]
            now = {"date": today.isoformat(), "offers": []}
            for ingredient in recipe["ingredients"]:
                if not ingredient["staple"]:
                    self._add_need(
                        rows, now, recipe, ingredient, factor, stock, maybe_home, today
                    )
        for key in sorted(self.days):
            day = self.days[key]
            recipe = self._meal_recipe(day)
            if key < today.isoformat() or day["status"] != STATUS_PLANNED or not recipe:
                continue
            factor = (day["servings"] or recipe["servings"]) / recipe["servings"]
            for ingredient in recipe["ingredients"]:
                if not ingredient["staple"]:
                    self._add_need(
                        rows, day, recipe, ingredient, factor, stock, maybe_home, today
                    )

        needs: dict[str, float] = {}
        for row in rows.values():
            needs[row["base"]] = needs.get(row["base"], 0) + row["qty"]
        self.bought = {
            base: min(value, needs[base])
            for base, value in self.bought.items()
            if base in needs and value > EPSILON
        }
        self.hidden = {
            base: min(value, needs[base])
            for base, value in self.hidden.items()
            if base in needs and value > EPSILON
        }

        cutoff = (
            dt_util.utcnow() - timedelta(days=MANUAL_DONE_RETENTION_DAYS)
        ).isoformat()
        self.manual = [
            item
            for item in self.manual
            if not (item["done"] and item["done_at"] and item["done_at"] < cutoff)
        ]
        self.shopping = sorted(
            [*self._allocate(rows), *self.manual], key=self._sort_key
        )

    def _add_need(
        self,
        rows: dict[tuple[str, str | None], dict[str, Any]],
        day: dict[str, Any],
        recipe: dict[str, Any],
        ingredient: dict[str, Any],
        factor: float,
        stock: dict[tuple[str, str | None], float],
        maybe_home: set[str],
        today: date,
    ) -> None:
        """Add what one ingredient of one meal still needs to the rows."""
        name = name_key(ingredient["name"])
        amount = ingredient["amount"]
        unit = ingredient["unit"]
        from_stock = 0.0
        if amount is not None:
            amount = round(amount * factor, 3)
            from_stock = min(amount, stock.get((name, unit), 0))
            stock[(name, unit)] = stock.get((name, unit), 0) - from_stock
            amount = round(amount - from_stock, 3)
            if amount <= EPSILON:
                return
        elif any(key[0] == name and value > EPSILON for key, value in stock.items()):
            return
        other_unit = any(
            key[0] == name and key[1] != unit and value > EPSILON
            for key, value in stock.items()
        )

        store = ingredient["store"]
        offer = None
        for candidate in day.get("offers", []):
            wanted = name_key(candidate["item"])
            if wanted in name or name in wanted:
                offer = candidate.get("label") or "Angebot"
                store = self._known_store(candidate.get("store") or store)
                break

        base = f"{name}|{unit or ''}|{store}"
        buy_on = self._buy_on(
            date.fromisoformat(day["date"]), ingredient["fresh"], today
        )
        row = rows.setdefault(
            (base, buy_on),
            {
                "id": sha1(f"{base}|{buy_on}".encode()).hexdigest()[:16],
                "base": base,
                "source": "plan",
                "name": ingredient["name"],
                "amount": None,
                "unit": unit,
                "qty": 0.0,
                "store": store,
                "section": ingredient["section"],
                "buy_on": buy_on,
                "offer": None,
                "for": [],
                "from_stock": 0.0,
                "maybe_home": name in maybe_home or other_unit,
                "done": False,
            },
        )
        row["qty"] = round(row["qty"] + (amount if amount is not None else 1), 3)
        if amount is not None:
            row["amount"] = row["qty"]
        row["from_stock"] = round(row["from_stock"] + from_stock, 3)
        row["offer"] = row["offer"] or offer
        if recipe["name"] not in row["for"]:
            row["for"].append(recipe["name"])

    def _allocate(
        self, rows: dict[tuple[str, str | None], dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply what was already bought or removed, earliest trip first."""
        hidden = dict(self.hidden)
        bought = dict(self.bought)
        result = []
        for row in sorted(rows.values(), key=lambda row: row["buy_on"] or ""):
            base = row["base"]
            skipped = min(hidden.get(base, 0), row["qty"])
            hidden[base] = hidden.get(base, 0) - skipped
            qty = round(row["qty"] - skipped, 3)
            if qty <= EPSILON:
                continue
            covered = min(bought.get(base, 0), qty)
            bought[base] = bought.get(base, 0) - covered
            if qty - covered <= EPSILON:
                row["done"] = True
            else:
                qty = round(qty - covered, 3)
            row["qty"] = qty
            if row["amount"] is not None:
                row["amount"] = qty
            result.append(row)
        return result

    def _sort_key(self, item: dict[str, Any]) -> tuple[Any, ...]:
        """Sort by store, trip and walking order."""
        sections = self.sections(item["store"])
        section = item["section"]
        return (
            item["store"],
            item["buy_on"] or "",
            sections.index(section) if section in sections else len(sections),
            name_key(item["name"]),
        )

    def _shopping_counts(self) -> dict[str, int]:
        """Return the number of open items per store."""
        return {
            store: sum(
                1 for item in self.shopping if item["store"] == store and not item["done"]
            )
            for store in self.settings.stores
        }

    def _known_section(self, name: str) -> str:
        """Guess a section from the recipes that use an ingredient."""
        wanted = name_key(name)
        for recipe in self.recipes.values():
            for ingredient in recipe["ingredients"]:
                if name_key(ingredient["name"]) == wanted:
                    return ingredient["section"]
        return FALLBACK_SECTION

    @callback
    def async_add_shopping_item(
        self,
        name: str,
        store: str | None = None,
        amount: float | None = None,
        unit: str | None = None,
        section: str | None = None,
        buy_on: str | None = None,
    ) -> dict[str, Any]:
        """Add an item that does not come from the plan."""
        amount, unit = normalize_amount(amount, unit)
        item = {
            "id": ulid_now(),
            "source": "manual",
            "name": name,
            "amount": amount,
            "unit": unit,
            "store": self._known_store(store),
            "section": section or self._known_section(name),
            "buy_on": buy_on,
            "offer": None,
            "for": [],
            "from_stock": 0.0,
            "maybe_home": False,
            "done": False,
            "done_at": None,
        }
        self.manual.append(item)
        self._rebuild_shopping()
        self._async_changed()
        return item

    def _find_shopping(self, item_id: str) -> dict[str, Any]:
        """Return a shopping item."""
        for item in self.shopping:
            if item["id"] == item_id:
                return item
        raise HomeAssistantError(f"Unknown shopping item: {item_id}")

    @callback
    def async_set_shopping_done(self, item_id: str, done: bool) -> None:
        """Tick or untick a shopping item."""
        item = self._find_shopping(item_id)
        if item["done"] == done:
            return
        if item["source"] == "manual":
            item["done"] = done
            item["done_at"] = dt_util.utcnow().isoformat() if done else None
        else:
            current = self.bought.get(item["base"], 0)
            change = item["qty"] if done else -item["qty"]
            self.bought[item["base"]] = max(0, round(current + change, 3))
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_update_manual_item(
        self, item_id: str, name: str | None, buy_on: str | None
    ) -> None:
        """Change an item that does not come from the plan."""
        item = self._find_shopping(item_id)
        if item["source"] != "manual":
            return
        if name:
            item["name"] = name
        item["buy_on"] = buy_on
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_remove_shopping_items(self, item_ids: list[str]) -> None:
        """Remove shopping items, plan items stay away until the need grows."""
        for item_id in item_ids:
            item = self._find_shopping(item_id)
            if item["source"] == "manual":
                self.manual.remove(item)
                continue
            base = item["base"]
            if item["done"]:
                self.bought[base] = max(0, self.bought.get(base, 0) - item["qty"])
            self.hidden[base] = round(self.hidden.get(base, 0) + item["qty"], 3)
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_set_store_sections(self, store: str, sections: list[str]) -> None:
        """Set the walking order of a store."""
        if store not in self.settings.stores:
            raise HomeAssistantError(f"Unknown store: {store}")
        self.store_sections[store] = sections
        self._rebuild_shopping()
        self._async_changed()

    # --- Inventory ---

    def _find_inventory(
        self, item_id: str | None, name: str | None, location: str | None
    ) -> dict[str, Any] | None:
        """Find an inventory item by ID, or by name within a location."""
        for item in self.inventory:
            if item_id:
                if item["id"] == item_id:
                    return item
            elif (
                name
                and name_key(item["name"]) == name_key(name)
                and (location is None or item["location"] == location)
            ):
                return item
        return None

    def _update_inventory(self, change: dict[str, Any]) -> str | None:
        """Apply one inventory change and return the ID of the item left."""
        item_id = change.get("id")
        name = change.get("name")
        location = change.get("location")
        if not item_id and not name:
            raise HomeAssistantError("An inventory item needs an id or a name")
        if location is not None and location not in LOCATIONS:
            raise HomeAssistantError(f"Location must be one of {LOCATIONS}")
        item = self._find_inventory(item_id, name, location)
        if item_id and item is None:
            raise HomeAssistantError(f"Unknown inventory item: {item_id}")

        amount, unit = normalize_amount(
            change.get("amount"),
            change.get("unit") or (item["unit"] if item else None),
        )
        if change.get("remove") or (amount is not None and amount <= 0):
            if item:
                self.inventory.remove(item)
            return None

        now = dt_util.utcnow().isoformat()
        if item is None:
            item = {
                "id": ulid_now(),
                "name": name,
                "amount": amount,
                "unit": unit,
                "location": location or DEFAULT_LOCATION,
                "best_before": None,
                "updated_at": now,
            }
            self.inventory.append(item)
        else:
            if name:
                item["name"] = name
            if "amount" in change:
                item["amount"] = amount
                item["unit"] = unit
            if location:
                item["location"] = location
            item["updated_at"] = now
        if "best_before" in change:
            best_before = change["best_before"]
            item["best_before"] = (
                parse_date(best_before).isoformat() if best_before else None
            )
        return item["id"]

    @callback
    def async_update_inventory(self, changes: list[dict[str, Any]]) -> None:
        """Apply inventory changes."""
        for change in changes:
            self._update_inventory(change)
        self._rebuild_shopping()
        self._async_changed()

    @callback
    def async_record_audit(
        self,
        items: list[dict[str, Any]] | None = None,
        location: str | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Record a finished count, optionally replacing what was known."""
        kept = {
            item_id
            for change in items or []
            if (item_id := self._update_inventory(change))
        }
        removed = 0
        if replace:
            for item in list(self.inventory):
                if item["id"] not in kept and location in (None, item["location"]):
                    self.inventory.remove(item)
                    removed += 1
        self.audit = {
            "last_at": dt_util.utcnow().isoformat(),
            "counted": len(self.inventory),
        }
        self._rebuild_shopping()
        self._async_changed()
        return {"counted": len(self.inventory), "removed": removed}

    def sorted_inventory(self) -> list[dict[str, Any]]:
        """Return the inventory, whatever expires first on top."""
        return sorted(
            self.inventory,
            key=lambda item: (item["best_before"] or "9999", name_key(item["name"])),
        )

    def expiring(self) -> list[dict[str, Any]]:
        """Return what expires soon or has expired."""
        limit = (self.today() + timedelta(days=EXPIRING_DAYS)).isoformat()
        return [
            item
            for item in self.sorted_inventory()
            if item["best_before"] and item["best_before"] <= limit
        ]

    def days_since_audit(self) -> int | None:
        """Return the days since the last count, None if there never was one."""
        if not self.audit["last_at"]:
            return None
        last = dt_util.parse_datetime(self.audit["last_at"], raise_on_error=True)
        return (dt_util.utcnow() - last).days

    def audit_due(self) -> bool:
        """Return if a count is due."""
        since = self.days_since_audit()
        return since is None or since >= self.settings.audit_interval_days

    # --- Preferences and views ---

    @callback
    def async_set_preferences(self, text: str) -> None:
        """Store what the planner should keep in mind."""
        self.preferences = text
        self._async_changed()

    def audit_view(self) -> dict[str, Any]:
        """Return the state of the counts."""
        return {
            **self.audit,
            "days_since": self.days_since_audit(),
            "interval_days": self.settings.audit_interval_days,
            "due": self.audit_due(),
        }

    def stores_view(self) -> list[dict[str, Any]]:
        """Return the stores with their walking order."""
        return [
            {"id": store, "name": name, "sections": self.sections(store)}
            for store, name in self.settings.stores.items()
        ]

    def snapshot(self) -> dict[str, Any]:
        """Return everything the panel shows."""
        today = self.today()
        return {
            "today": today.isoformat(),
            "days": self.days_between(
                today - timedelta(days=1), today + timedelta(days=PLAN_HORIZON_DAYS)
            ),
            "next_plan_day": self.next_plan_day().isoformat(),
            "plan_missing": self.plan_missing(),
            "plan_weekdays": self.settings.plan_weekdays,
            "stores": self.stores_view(),
            "shopping": self.shopping,
            "inventory": self.sorted_inventory(),
            "expiring": self.expiring(),
            "locations": LOCATIONS,
            "audit": self.audit_view(),
            "adhoc": [self.adhoc_view(meal) for meal in self.adhoc],
            "recipes": [
                {
                    **self.recipes[item["id"]],
                    **item,
                    **self.recipe_availability(self.recipes[item["id"]]),
                }
                for item in sorted(
                    self._recipe_stats(), key=lambda item: name_key(item["name"])
                )
            ],
        }

    def recipe_availability(
        self, recipe: dict[str, Any], servings: int | None = None
    ) -> dict[str, Any]:
        """Compare a recipe with the inventory."""
        factor = (servings or recipe["servings"]) / recipe["servings"]
        expiring = {name_key(item["name"]) for item in self.expiring()}
        stock_per_ingredient = []
        missing = []
        maybe = []
        uses_expiring = []
        for ingredient in recipe["ingredients"]:
            key = name_key(ingredient["name"])
            stock = [item for item in self.inventory if name_key(item["name"]) == key]
            same_unit = [
                item
                for item in stock
                if item["unit"] == ingredient["unit"] and item["amount"] is not None
            ]
            have = sum(item["amount"] for item in same_unit)
            optional = ingredient["staple"] or "optional" in key
            stock_per_ingredient.append(
                {
                    "have": have,
                    "present": bool(same_unit),
                    "maybe": bool(stock) and not same_unit,
                    "optional": optional,
                }
            )
            if stock and key in expiring:
                uses_expiring.append(ingredient["name"])
            if optional:
                continue
            need = ingredient["amount"]
            need = None if need is None else need * factor
            if stock and not same_unit:
                maybe.append(ingredient["name"])
            elif not same_unit or (need is not None and have < need - EPSILON):
                still = None if need is None else need - have
                amount = format_amount(still, ingredient["unit"])
                missing.append(
                    f"{amount} {ingredient['name']}" if amount else ingredient["name"]
                )
        return {
            "stock": stock_per_ingredient,
            "missing": missing,
            "maybe": maybe,
            "uses_expiring": uses_expiring,
        }

    def what_can_i_cook(
        self, max_missing: int = 3, servings: int | None = None
    ) -> dict[str, Any]:
        """Rank the stored recipes by how well they fit what is at home."""
        options = []
        for stats in self._recipe_stats():
            availability = self.recipe_availability(
                self.recipes[stats["id"]], servings
            )
            if len(availability["missing"]) <= max_missing:
                options.append(
                    {
                        **stats,
                        "servings": servings or self.recipes[stats["id"]]["servings"],
                        "missing": availability["missing"],
                        "maybe_at_home": availability["maybe"],
                        "uses_expiring": availability["uses_expiring"],
                    }
                )
        options.sort(
            key=lambda item: (
                item["average_rating"] is not None and item["average_rating"] < 1.5,
                len(item["missing"]),
                -len(item["uses_expiring"]),
                item["last_cooked"] or "",
            )
        )
        return {
            "can_cook_now": [item for item in options if not item["missing"]],
            "needs_a_little": [item for item in options if item["missing"]],
            "inventory": self.sorted_inventory(),
            "expiring_soon": self.expiring(),
            "audit": self.audit_view(),
        }

    def _recipe_stats(self) -> list[dict[str, Any]]:
        """Return the stored recipes with how they went so far."""
        history = sorted(
            [*self.days.values(), *self.cook_log], key=lambda day: day["date"]
        )
        recipes = []
        for recipe in self.recipes.values():
            own = [day for day in history if day.get("recipe_id") == recipe["id"]]
            cooked = [day for day in own if day["status"] == STATUS_COOKED]
            ratings = [day["rating"] for day in cooked if day["rating"]]
            recipes.append(
                {
                    "id": recipe["id"],
                    "name": recipe["name"],
                    "minutes": recipe["minutes"],
                    "tags": recipe["tags"],
                    "last_cooked": cooked[-1]["date"] if cooked else None,
                    "average_rating": round(sum(ratings) / len(ratings), 1)
                    if ratings
                    else None,
                }
            )
        return recipes

    def planning_context(self) -> dict[str, Any]:
        """Return everything a planner needs to know."""
        today = self.today()
        recent = self.days_between(today - timedelta(days=RECENT_MEAL_DAYS), today)
        since = (today - timedelta(days=RECENT_MEAL_DAYS)).isoformat()
        return {
            "today": today.isoformat(),
            "weekday": today.strftime("%A"),
            "plan_weekdays": self.settings.plan_weekdays,
            "fresh_shopping_weekday": self.settings.fresh_weekday,
            "next_plan_day": self.next_plan_day().isoformat(),
            "preferences": self.preferences,
            "stores": self.stores_view(),
            "upcoming_plan": [
                self._compact_day(day)
                for day in self.days_between(
                    today, today + timedelta(days=PLAN_HORIZON_DAYS)
                )
            ],
            "recent_meals": [
                self._compact_day(day)
                for day in recent
                if day["status"] != STATUS_PLANNED or day["date"] < today.isoformat()
            ]
            + [
                self._compact_day(meal)
                for meal in self.cook_log
                if meal["date"] >= since
            ],
            "adhoc_meals": [
                {
                    "id": meal["id"],
                    "recipe_id": meal["recipe_id"],
                    "servings": meal["servings"],
                }
                for meal in self.adhoc
            ],
            "recipes": self._recipe_stats(),
            "inventory": self.sorted_inventory(),
            "expiring_soon": self.expiring(),
            "audit": self.audit_view(),
            "open_shopping": [
                self.shopping_view(item) for item in self.shopping if not item["done"]
            ],
        }

    @staticmethod
    def _compact_day(day: dict[str, Any]) -> dict[str, Any]:
        """Return a day without its full recipe."""
        return {
            "date": day["date"],
            "title": day["title"],
            "recipe_id": day.get("recipe_id"),
            "servings": day["servings"],
            "status": day["status"],
            "rating": day["rating"],
            "comment": day["comment"],
            "note": day["note"],
        }

    @staticmethod
    def shopping_view(item: dict[str, Any]) -> dict[str, Any]:
        """Return a shopping item for callers."""
        return {
            "id": item["id"],
            "name": item["name"],
            "amount": format_amount(item["amount"], item["unit"]),
            "store": item["store"],
            "section": item["section"],
            "buy_on": item["buy_on"],
            "offer": item["offer"],
            "for": item["for"],
            "source": item["source"],
            "done": item["done"],
        }

    async def async_save(self) -> None:
        """Write pending changes now, a reload would otherwise lose them."""
        await self._store.async_save(self._data_to_save())

    @callback
    def _async_changed(self) -> None:
        """Schedule a save and notify listeners."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    def _data_to_save(self) -> dict[str, Any]:
        """Return the data to store, the shopping rows are derived."""
        return {
            "recipes": self.recipes,
            "days": self.days,
            "manual": self.manual,
            "bought": self.bought,
            "hidden": self.hidden,
            "inventory": self.inventory,
            "audit": self.audit,
            "preferences": self.preferences,
            "store_sections": self.store_sections,
            "adhoc": self.adhoc,
            "cook_log": self.cook_log,
        }
