# Feature: Grid Charging SoC Limit

## Problem

Der "Netzladen" Mode lädt **immer bis 100%** SoC.

**Was passiert:**
- Batterien werden bis zur maximalen Kapazität geladen
- Kann Batterie-Lebensdauer reduzieren
- Keine Kontrolle über Ziel-Ladezustand
- Nutzer wollen oft nur bis 80-90% laden

**Aktueller Code:**
```python
case SmartMode.GRID_CHARGING:
    grid_power = self.config_entry.data.get(CONF_GRID_CHARGE_POWER, 800)
    await self.powerCharge(devices, 0, -grid_power, False)
    # Lädt bis Batterie voll ist!
```

---

## Lösung

**Konfigurierbares SoC-Limit** für Netzladen Mode.

**Wie es funktioniert:**
```python
# Neue Entity in Manager Konfiguration
number.grid_charge_target_soc:
  - Bereich: 50-100%
  - Standard: 90%
  - Icon: mdi:battery-charging-90

# In grid_charging Mode:
for device in devices:
    if device.soc >= target_soc:
        # Stoppe Laden für dieses Gerät
        await device.power_off()
    else:
        # Lade weiter
        await device.power_charge(power)
```

---

## Vorteile

✅ **Batterie-Schonung**
- Moderne Li-Ion Batterien leben länger bei 80-90% statt 100%
- Reduziert Stress auf Zellen

✅ **Flexibilität**
- Nutzer kann selbst entscheiden
- Anpassbar je nach Bedarf

✅ **Kostenoptimierung**
- Nicht mehr laden als nötig
- Spart Strom bei NT

✅ **Sicherheit**
- Nicht überladen bei langen NT-Phasen

---

## Anwendungsfall

**Szenario 1: Batterie-Schonung**
```
Nutzer-Einstellung:
- Netzladen Leistung: 800W
- Netzladen Ziel-SoC: 85%

NT startet 22:30:
- Batterien bei 30%
- Lädt bis 85%
- Stoppt automatisch
- Rest der Nacht: Standby

Batterie-Lebensdauer: +20-30%!
```

**Szenario 2: Kurze NT-Phase**
```
Problem: NT nur 4 Stunden, Batterien brauchen 6h für 100%

Lösung:
- Ziel-SoC: 80%
- Schafft es in 4 Stunden
- Besser 80% als nur 70% erreichen
```

**Szenario 3: Notfall-Modus**
```
Bei Unwetter-Warnung:
- Ziel-SoC: 100% (volle Kapazität)
- Für längeren Stromausfall vorbereitet
```

---

## Implementierung

### Neue Entity:
```python
# In manager.py
self.gridChargeTargetSoc = ZendureNumber(
    self, "grid_charge_target_soc",
    save_callback(CONF_GRID_CHARGE_TARGET_SOC),
    None, "%", None,
    100, 50,  # 50-100%
    NumberMode.BOX, 1, True
)
self.gridChargeTargetSoc._attr_native_value = 90.0
self.gridChargeTargetSoc._attr_icon = "mdi:battery-charging-90"
self.gridChargeTargetSoc._attr_entity_category = EntityCategory.CONFIG
```

### Logik in powerChanged():
```python
case SmartMode.GRID_CHARGING:
    grid_power = self.config_entry.data.get(CONF_GRID_CHARGE_POWER, 800)
    target_soc = self.config_entry.data.get(CONF_GRID_CHARGE_TARGET_SOC, 90)
    
    # Prüfe jedes Gerät einzeln
    for device in devices:
        if device.electricLevel.asInt >= target_soc:
            # Ziel erreicht - stoppe dieses Gerät
            await device.power_off()
        else:
            # Lade weiter
            await device.power_charge(-grid_power)
```

---

## Übersetzungen

**Deutsch:**
```json
"grid_charge_target_soc": {
  "name": "Netzladen Ziel-SoC"
}
```

**Englisch:**
```json
"grid_charge_target_soc": {
  "name": "Grid Charging Target SoC"
}
```

---

## Automation-Integration

**Verschiedene Ziele für verschiedene Situationen:**

```yaml
# Normal: 85% für Batterie-Schonung
- service: number.set_value
  target:
    entity_id: number.zendure_manager_grid_charge_target_soc
  data:
    value: 85

# Vor Unwetter: 100% für Notfall
- service: number.set_value
  target:
    entity_id: number.zendure_manager_grid_charge_target_soc
  data:
    value: 100
```

---

## Best Practices

**Empfohlene Werte:**

| Nutzung | Ziel-SoC | Grund |
|---------|----------|-------|
| **Täglich** | 80-85% | Optimale Lebensdauer |
| **Wochenende** | 90% | Mehr Reserve |
| **Notfall** | 100% | Volle Kapazität |
| **Sommer** | 75% | Weniger Bedarf |
| **Winter** | 90% | Mehr Verbrauch |

**Batterie-Hersteller Empfehlung:**
- Täglicher Betrieb: 20-80% (bestes für Lebensdauer)
- Gelegentlich 100%: OK
- Dauerhaft 100%: Reduziert Lebensdauer

---

## Status

**Branch:** `feature/grid-charging-soc-limit`  
**Basis:** `release/auto-calibration` (v1.5.1)  
**Implementierung:** Offen  
**Testing:** Ausstehend

---

_Batterie-Lebensdauer-Optimierung basierend auf Li-Ion Best Practices_
