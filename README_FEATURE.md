# Feature: Custom Lovelace Cards

## Problem

Standard Home Assistant Cards zeigen nur **Zahlen und Stati**.

**Aktuell:**
- Nutzer muss viele einzelne Entity-Cards erstellen
- Keine visuelle Darstellung des Energie-Flusses
- Schwer zu verstehen was gerade passiert
- Komplizierte Lovelace-Konfiguration nötig

**Beispiel Standard-UI:**
```
Sensor: Zendure Manager Power: 450 W
Sensor: Solar Input: 1200 W
Sensor: Battery Output: 350 W
Sensor: Available kWh: 3.2 kWh
Select: Operation Mode: smart
...
```
→ Viele Zeilen, keine Übersicht!

---

## Lösung

**3 Custom Cards** für optimale Visualisierung.

### 1. Zendure Power Flow Card
Grafische Darstellung des Energie-Flusses

### 2. Zendure Battery Overview Card
Alle Batterien auf einen Blick

### 3. Zendure Quick Control Card
Schneller Zugriff auf wichtigste Funktionen

---

## Card 1: Power Flow Card

**Design:**
```
┌─────────────────────────────────────────────┐
│     Zendure Energie-Fluss                   │
├─────────────────────────────────────────────┤
│                                             │
│     🌞 Solar                                │
│      1200W                                  │
│        ↓                                    │
│     🔋 Batterie  ←→  🏠 Haus                │
│     85% (4.8kWh)     800W                   │
│        ↓                                    │
│     ⚡ Netz                                 │
│      -400W (Überschuss)                     │
│                                             │
│  Status: Smart Matching                     │
└─────────────────────────────────────────────┘
```

**Features:**
- Animierte Pfeile zeigen Richtung
- Farben: Grün (laden), Gelb (entladen), Grau (idle)
- Auto-Update bei Änderungen
- Klick auf Element → Mehr Details

---

## Card 2: Battery Overview Card

**Design:**
```
┌─────────────────────────────────────────────┐
│     Batterien Übersicht                     │
├─────────────────────────────────────────────┤
│                                             │
│  🔋 Hyper 2000 #1        🟢 Online          │
│  ████████████░░░░ 85%    🌡️ 24°C            │
│  2.4 / 2.88 kWh          ⚡ +350W           │
│                                             │
│  🔋 Hyper 2000 #2        🟢 Online          │
│  ██████████████░░ 92%    🌡️ 26°C            │
│  2.6 / 2.88 kWh          ⚡ +200W           │
│                                             │
│  🔋 SolarFlow 2400       🟢 Online          │
│  ██████░░░░░░░░░░ 45%    🌡️ 22°C            │
│  2.6 / 5.76 kWh          ⚡ +800W (Laden)   │
│                                             │
│  Gesamt: 7.6 / 11.52 kWh (66%)             │
└─────────────────────────────────────────────┘
```

**Features:**
- Alle Geräte auf einen Blick
- Lade-/Entlade-Status mit Farben
- Temperatur-Warnung bei >40°C
- Klick auf Gerät → Details

---

## Card 3: Quick Control Card

**Design:**
```
┌─────────────────────────────────────────────┐
│     Zendure Schnellsteuerung                │
├─────────────────────────────────────────────┤
│                                             │
│  Betriebsmodus:                             │
│  ┌─────────┬─────────┬──────────┬─────────┐ │
│  │  Smart  │ Netzladen│ Nur Laden│ Aus    │ │
│  │   🟢    │         │          │        │ │
│  └─────────┴─────────┴──────────┴─────────┘ │
│                                             │
│  Netzladen Leistung:  [  800W  ]            │
│  Ziel-SoC:            [   90%  ]            │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  🔋 Alle kalibrieren                │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Kalibrierung: ✅ Aktiviert                 │
│  Nächste: 15. Dez 2025                      │
└─────────────────────────────────────────────┘
```

**Features:**
- Ein Klick Mode-Wechsel
- Wichtigste Einstellungen direkt
- Status-Übersicht
- Kompakt und übersichtlich

---

## Technische Implementation

### Datei-Struktur:
```
custom_components/zendure_ha/
├── lovelace/
│   ├── zendure-power-flow-card.js
│   ├── zendure-battery-overview-card.js
│   └── zendure-quick-control-card.js
└── www/
    └── zendure-cards-bundle.js (combined)
```

### Frontend Integration:
```python
# In __init__.py
async def async_setup_entry(hass, entry):
    # ...
    
    # Register custom cards
    hass.http.register_static_path(
        "/zendure_ha/zendure-cards.js",
        hass.config.path("custom_components/zendure_ha/www/zendure-cards-bundle.js"),
        True
    )
```

### Card Registration in Lovelace:
```yaml
# Automatisch in resources:
resources:
  - url: /zendure_ha/zendure-cards.js
    type: module
```

---

## Card Konfiguration

### Power Flow Card:
```yaml
type: custom:zendure-power-flow-card
entity: sensor.zendure_manager_power
entities:
  solar: sensor.zendure_manager_solar_input
  battery: sensor.zendure_manager_available_kwh
  home: sensor.zendure_manager_home_output
  grid: sensor.p1_meter
show_animation: true
color_scheme: auto  # auto, light, dark
```

### Battery Overview Card:
```yaml
type: custom:zendure-battery-overview-card
devices:
  - entity: sensor.hyper_2000_1_electric_level
    name: Hyper 2000 #1
  - entity: sensor.hyper_2000_2_electric_level
    name: Hyper 2000 #2
  - entity: sensor.solarflow_2400_electric_level
    name: SolarFlow 2400
show_temperature: true
show_power: true
compact: false
```

### Quick Control Card:
```yaml
type: custom:zendure-quick-control-card
entity: select.zendure_manager_operation
entities:
  grid_power: number.zendure_manager_grid_charge_power
  target_soc: number.zendure_manager_grid_charge_target_soc
  calibrate: button.zendure_manager_calibrate_all_devices
show_calibration_status: true
```

---

## Status

**Branch:** `feature/custom-lovelace-cards`  
**Basis:** `release/auto-calibration` (v1.5.1)  
**Implementierung:** In Arbeit...

---

_Verbessert die User Experience dramatisch!_
