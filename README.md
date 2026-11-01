# Küchenplan

Home-Assistant-Integration für den Essensalltag: Ein Assistent wie Claude plant über MCP, und
Kalender, Einkaufslisten, Sensoren und die Küchen-Ansicht folgen automatisch aus diesem einen Plan.

- **Tablet und Handy:** Eigener Eintrag in der Seitenleiste mit Woche, Kochmodus (Portionen, Timer,
  Bildschirm bleibt an), Einkauf und Kühlschrank.
- **Einkauf:** Eine To-do-Liste pro Laden, nach Gang sortiert. Gleiche Zutaten werden zusammengerechnet,
  der Vorrat wird abgezogen, Abgehaktes und eigene Einträge bleiben beim Neuplanen erhalten.
- **Frischekauf:** Frische Zutaten für Mahlzeiten nach dem Frischetag wandern auf diesen Tag und
  ziehen mit um, wenn Tage getauscht werden.
- **Spontan kochen:** Rezept antippen, Fehlendes landet sofort auf der Einkaufsliste, danach direkt in den
  Kochmodus. Der Wochenplan bleibt unberührt, gekocht wird trotzdem für künftige Pläne gemerkt.
- **Was kann ich kochen?** Rezepte nach dem sortiert, was da ist und was bald abläuft, in der App und über
  das Tool `what_can_i_cook`, mit dem Claude auch neue Gerichte aus dem Vorrat vorschlagen kann.
- **Inventur:** Geführte Zählung in der App, oder per Chat und Foto über Claude. Was bald abläuft,
  bekommt der Planer zuerst genannt.

Alles liegt im Klartext in `.storage/kuechenplan`, also auch in HA-Backups.

## Einrichtung

Benötigt Home Assistant 2026.10 oder neuer.

1. `custom_components/kuechenplan` nach `/config/custom_components/` kopieren oder über HACS als
   benutzerdefiniertes Repository installieren, dann HA neu starten.
2. Integration „Küchenplan“ hinzufügen: Läden, Kochtage, Frischetag und Inventur-Abstand angeben.
3. In der Integration „Model Context Protocol Server“ zusätzlich die API „Küchenplan“ auswählen.
   Der Connector unter `<externe HA-URL>/api/mcp` bietet dann die Tools an.

## MCP-Tools

| Zweck | Tools |
|---|---|
| Lesen | `get_planning_context`, `get_plan`, `get_recipe`, `search_recipes`, `get_shopping_list`, `get_inventory`, `what_can_i_cook` |
| Planen | `apply_week_plan`, `set_day`, `clear_day`, `swap_days`, `mark_cooked`, `upsert_recipe`, `set_preferences` |
| Spontan | `add_adhoc_meal`, `remove_adhoc_meal`, `mark_adhoc_cooked` |
| Einkauf | `add_shopping_items`, `set_shopping_item_done`, `remove_shopping_items`, `set_store_sections` |
| Vorrat | `update_inventory`, `record_inventory_audit` |

Alle Tools gibt es auch als Dienste `kuechenplan.<tool>`, zum Beispiel für Automationen oder ha-mcp.

## Für Automationen

- `sensor.kuchenplan_heute`, `sensor.kuchenplan_morgen`: Gericht mit Kochzeit, Details als Attribute
- `sensor.kuchenplan_frischekauf_offen`, `sensor.kuchenplan_lauft_bald_ab`: Anzahl mit Liste als Attribut
- `binary_sensor.kuchenplan_plan_fehlt`, `binary_sensor.kuchenplan_reistag`,
  `binary_sensor.kuchenplan_inventur_fallig`
- `calendar.kuchenplan_essensplan`, `todo.kuchenplan_einkauf_<laden>`
- Ereignisse `kuechenplan_plan_applied` und `kuechenplan_meal_cooked`
- Direktlinks für Push-Nachrichten: `/kuechenplan?view=einkauf&store=rewe`, `view=kuehlschrank`, `view=kochen`

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install uv
VIRTUAL_ENV=.venv .venv/bin/uv pip install homeassistant==2026.10.4 pytest-homeassistant-custom-component \
  mcp==1.28.1 aiohttp_sse==2.2.0 anyio==4.14.2 home-assistant-frontend==20260930.5 Pillow \
  gazetteer-matcher hassil home-assistant-intents
.venv/bin/python -m pytest
```

## Lizenzen

Die Schriften in `frontend/fonts` (Bricolage Grotesque, Instrument Sans) stehen unter der SIL Open Font License 1.1.
