# Feature: Intelligente NT-Automation mit Wetterprognose

## Problem

NT-Laden lädt **immer gleich viel**, unabhängig vom Wetter morgen.

**Aktuell:**
- Jede Nacht bis 90% laden
- Egal ob morgen Sonne oder Regen kommt
- Verschwendet Geld wenn nicht nötig

**Beispiel:**
```
Heute Nacht: Lädt bis 90%
Morgen: Sonnig, 8kWh Solar-Produktion
→ Batterien mittags schon voll
→ 40% der NT-Ladung war unnötig!
```

---

## Lösung

**Adaptive NT-Ladung** basierend auf Wettervorhersage.

**Logik:**
```python
# Hole Wetter-Prognose für morgen
solar_forecast = get_tomorrow_solar_forecast()  # kWh

# Berechne benötigte Ladung
if solar_forecast > 6:
    # Viel Sonne erwartet
    target_soc = 50%  # Lade nur wenig
elif solar_forecast > 3:
    # Mittlere Sonne
    target_soc = 70%
else:
    # Wenig Sonne (Regen/Winter)
    target_soc = 95%  # Lade voll!
```

---

## Vorteile

✅ **Kosten-Optimierung**
- Lädt nur was wirklich nötig ist
- Spart bis zu 50% NT-Kosten

✅ **Batterie-Schonung**
- Weniger Ladezyklen
- Längere Lebensdauer

✅ **Intelligente Automation**
- Passt sich automatisch an
- Nutzer muss nichts machen

✅ **Wetter-Integration**
- Nutzt vorhandene HA-Daten
- Z.B. Solcast, Forecast.Solar

---

## Anwendungsfall

**Winter vs. Sommer:**
```
Winter (Dezember):
  Prognose: 2kWh Solar
  → NT: Lade bis 95%
  → Wichtig weil wenig Solar

Sommer (Juli):
  Prognose: 12kWh Solar  
  → NT: Lade nur bis 50%
  → Spart Geld, Solar reicht eh
```

**Wetteränderung:**
```
Normalerweise sonnig:
  → NT: 60% reicht

Regenperiode erwartet:
  → NT: 90% laden
  → Automatische Anpassung!
```

---

## Integration

**Unterstützte Forecast-Quellen:**
- Solcast (solcast_pv_forecast)
- Forecast.Solar
- Met.no
- Eigene Sensoren

**Konfiguration:**
```python
# Neue Entities
select.nt_forecast_source:
  - "Solcast"
  - "Forecast.Solar"
  - "Manuell (fester SoC)"

number.nt_solar_threshold_high:  # > 6kWh → Lade nur 50%
number.nt_solar_threshold_med:   # 3-6kWh → Lade 70%
number.nt_solar_threshold_low:   # < 3kWh → Lade 95%
```

---

## Beispiel-Automation

```yaml
# Automatisch adaptives NT-Laden
- alias: "Smart NT Laden"
  trigger:
    - platform: time
      at: "22:00:00"  # 30 Min vor NT
  action:
    # Hole Solar-Prognose
    - variables:
        solar_tomorrow: "{{ states('sensor.solcast_pv_forecast_tomorrow') | float }}"
    
    # Berechne Ziel-SoC
    - variables:
        target_soc: >
          {% if solar_tomorrow > 6 %}50
          {% elif solar_tomorrow > 3 %}70
          {% else %}95{% endif %}
    
    # Setze Ziel
    - service: number.set_value
      target:
        entity_id: number.zendure_manager_grid_charge_target_soc
      data:
        value: "{{ target_soc }}"
    
    # Starte NT um 22:30
    - delay: "00:30:00"
    - service: select.select_option
      data:
        entity_id: select.zendure_manager_operation
        option: "grid_charging"
```

---

## Status

**Branch:** `feature/smart-nt-weather`  
**Erfordert:** feature/grid-charging-soc-limit
