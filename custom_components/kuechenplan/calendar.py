"""Calendar of the Küchenplan integration, derived from the plan."""

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import PLAN_HORIZON_DAYS
from .entity import KuechenplanEntity
from .store import format_amount


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar."""
    async_add_entities([MealCalendar(entry)])


def _description(day: dict[str, Any]) -> str:
    """Return the text of a calendar event."""
    lines = [day["note"]] if day["note"] else []
    recipe = day["recipe"]
    if recipe:
        factor = (day["servings"] or recipe["servings"]) / recipe["servings"]
        lines.append(f"{day['servings']} Portionen")
        lines.extend(
            "- "
            + " ".join(
                part
                for part in (
                    format_amount(
                        None
                        if item["amount"] is None
                        else item["amount"] * factor,
                        item["unit"],
                    ),
                    item["name"],
                )
                if part
            )
            for item in recipe["ingredients"]
        )
        lines.extend(
            f"{number}. {step['text']}"
            for number, step in enumerate(recipe["steps"], start=1)
        )
    return "\n".join(lines)


def _event(day: dict[str, Any]) -> CalendarEvent:
    """Return the all-day event of a day."""
    start = date.fromisoformat(day["date"])
    return CalendarEvent(
        start=start,
        end=start + timedelta(days=1),
        summary=day["label"],
        description=_description(day),
        uid=day["date"],
    )


class MealCalendar(KuechenplanEntity, CalendarEntity):
    """All-day events for the planned meals."""

    _attr_icon = "mdi:calendar-today"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the calendar."""
        super().__init__(entry, "essensplan", "Essensplan")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next meal."""
        today = dt_util.now().date()
        days = self.store.days_between(today, today + timedelta(days=PLAN_HORIZON_DAYS))
        return _event(days[0]) if days else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the meals of a period."""
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        return [_event(day) for day in self.store.days_between(start, end)]
