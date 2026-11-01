"""Binary sensors of the Küchenplan integration."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import KuechenplanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        [PlanMissingSensor(entry), RiceDaySensor(entry), AuditDueSensor(entry)]
    )


class PlanMissingSensor(KuechenplanEntity, BinarySensorEntity):
    """The next day that should have a meal has none."""

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "plan_fehlt", "Plan fehlt")

    @property
    def is_on(self) -> bool:
        """Return if the plan is missing."""
        return self.store.plan_missing()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the day concerned."""
        return {"next_plan_day": self.store.next_plan_day().isoformat()}


class RiceDaySensor(KuechenplanEntity, BinarySensorEntity):
    """Today's meal needs the rice cooker."""

    _attr_icon = "mdi:rice"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "reistag", "Reistag")

    @property
    def is_on(self) -> bool:
        """Return if today's meal needs rice."""
        day = self.store.get_day(self.store.today())
        return bool(day and day["rice"] and day["status"] == "planned")


class AuditDueSensor(KuechenplanEntity, BinarySensorEntity):
    """The inventory should be counted again."""

    _attr_icon = "mdi:fridge-alert"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "inventur_faellig", "Inventur fällig")

    @property
    def is_on(self) -> bool:
        """Return if a count is due."""
        return self.store.audit_due()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return when the last count was."""
        return {
            "last_at": self.store.audit["last_at"],
            "days_since": self.store.days_since_audit(),
        }
