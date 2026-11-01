"""Shopping lists of the Küchenplan integration, one per store."""

from datetime import date
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import KuechenplanEntity
from .store import format_amount


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one list per store."""
    async_add_entities(
        ShoppingList(entry, store, name)
        for store, name in entry.runtime_data.settings.stores.items()
    )


def _todo_item(item: dict[str, Any]) -> TodoItem:
    """Return a shopping item as a to-do item."""
    amount = format_amount(item["amount"], item["unit"])
    details = [
        part
        for part in (
            item["section"],
            ", ".join(item["for"]),
            item["offer"],
            "Vielleicht noch zu Hause" if item["maybe_home"] else None,
        )
        if part
    ]
    return TodoItem(
        uid=item["id"],
        summary=f"{item['name']} ({amount})" if amount else item["name"],
        status=TodoItemStatus.COMPLETED if item["done"] else TodoItemStatus.NEEDS_ACTION,
        due=date.fromisoformat(item["buy_on"]) if item["buy_on"] else None,
        description=" · ".join(details) or None,
    )


class ShoppingList(KuechenplanEntity, TodoListEntity):
    """The shopping list of one store, sorted in walking order."""

    _attr_icon = "mdi:cart-outline"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
    )

    def __init__(self, entry: ConfigEntry, store_id: str, name: str) -> None:
        """Initialize the list."""
        super().__init__(entry, f"einkauf_{store_id}", f"Einkauf {name}")
        self._store_id = store_id

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the items of this store."""
        return [
            _todo_item(item)
            for item in self.store.shopping
            if item["store"] == self._store_id
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item."""
        self.store.async_add_shopping_item(
            item.summary or "",
            self._store_id,
            buy_on=item.due.isoformat() if isinstance(item.due, date) else None,
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick an item, and rename it if it did not come from the plan."""
        assert item.uid
        self.store.async_update_manual_item(
            item.uid,
            item.summary,
            item.due.isoformat() if isinstance(item.due, date) else None,
        )
        self.store.async_set_shopping_done(
            item.uid, item.status == TodoItemStatus.COMPLETED
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Remove items."""
        self.store.async_remove_shopping_items(uids)
