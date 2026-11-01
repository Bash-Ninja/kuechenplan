"""Constants for the Küchenplan integration."""

DOMAIN = "kuechenplan"
NAME = "Küchenplan"

CONF_STORES = "stores"
CONF_PLAN_WEEKDAYS = "plan_weekdays"
CONF_FRESH_WEEKDAY = "fresh_weekday"
CONF_AUDIT_INTERVAL = "audit_interval_days"

DEFAULT_STORES = "REWE, Lidl"
DEFAULT_PLAN_WEEKDAYS = ["0", "1", "2", "3", "4"]
DEFAULT_FRESH_WEEKDAY = "2"
DEFAULT_AUDIT_INTERVAL = 14

SIGNAL_UPDATED = f"{DOMAIN}_updated"
EVENT_PLAN_APPLIED = f"{DOMAIN}_plan_applied"
EVENT_MEAL_COOKED = f"{DOMAIN}_meal_cooked"

PANEL_URL_PATH = "kuechenplan"
PANEL_COMPONENT = "kuechenplan-panel"
STATIC_URL = "/kuechenplan_static"

LOCATIONS = ["Kühlschrank", "Tiefkühler", "Vorrat"]
DEFAULT_LOCATION = "Kühlschrank"
DEFAULT_SECTIONS = [
    "Obst und Gemüse",
    "Brot und Backwaren",
    "Kühlregal",
    "Käse",
    "Fleisch und Fisch",
    "Nudeln und Reis",
    "Konserven und Saucen",
    "Gewürze und Öl",
    "Tiefkühl",
    "Getränke",
    "Drogerie",
    "Sonstiges",
]
FALLBACK_SECTION = "Sonstiges"

STATUS_PLANNED = "planned"
STATUS_COOKED = "cooked"
STATUS_SKIPPED = "skipped"

EXPIRING_DAYS = 2
PLAN_HORIZON_DAYS = 14
HISTORY_DAYS = 400
RECENT_MEAL_DAYS = 28
MANUAL_DONE_RETENTION_DAYS = 3
ADHOC_RETENTION_DAYS = 7
