"""Sensors of the Küchenplan integration."""

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import KuechenplanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(
        [
            MealSensor(entry, "heute", "Heute", 0),
            MealSensor(entry, "morgen", "Morgen", 1),
            FreshShoppingSensor(entry),
            ExpiringSensor(entry),
        ]
    )


class MealSensor(KuechenplanEntity, SensorEntity):
    """The meal of a day relative to today."""

    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, entry: ConfigEntry, key: str, name: str, offset: int) -> None:
        """Initialize the sensor."""
        super().__init__(entry, key, name)
        self._offset = offset

    def _day(self) -> dict[str, Any] | None:
        return self.store.get_day(self.store.today() + timedelta(days=self._offset))

    @property
    def native_value(self) -> str | None:
        """Return the title, including the cooking time."""
        day = self._day()
        return day["label"] if day else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details for automations."""
        day = self._day()
        if day is None:
            return {}
        return {
            "date": day["date"],
            "title": day["title"],
            "minutes": day["minutes"],
            "servings": day["servings"],
            "status": day["status"],
            "rice": day["rice"],
            "note": day["note"],
        }


class FreshShoppingSensor(KuechenplanEntity, SensorEntity):
    """Items to buy on the fresh shopping trip."""

    _attr_icon = "mdi:basket"
    _attr_native_unit_of_measurement = "Artikel"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "frischekauf_offen", "Frischekauf offen")

    def _items(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.store.shopping
            if item["buy_on"] and not item["done"]
        ]

    @property
    def native_value(self) -> int:
        """Return the number of open items."""
        return len(self._items())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the items and the next trip."""
        items = self._items()
        return {
            "next_trip": min((item["buy_on"] for item in items), default=None),
            "items": [item["name"] for item in items],
        }


class ExpiringSensor(KuechenplanEntity, SensorEntity):
    """Things at home that expire soon."""

    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "Artikel"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "laeuft_bald_ab", "Läuft bald ab")

    @property
    def native_value(self) -> int:
        """Return the number of items."""
        return len(self.store.expiring())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the items."""
        return {
            "items": [
                {"name": item["name"], "best_before": item["best_before"]}
                for item in self.store.expiring()
            ]
        }
