# Zendure Custom Cards - Verwendung

Die Integration enthält 3 Custom Lovelace Cards für bessere Visualisierung.

---

## Installation

Die Cards werden **automatisch** registriert beim Setup der Integration.

**Manuelle Registrierung (falls nötig):**

```yaml
# In configuration.yaml oder ui-lovelace.yaml
lovelace:
  mode: yaml
  resources:
    - url: /zendure_ha/zendure-power-flow-card.js
      type: module
    - url: /zendure_ha/zendure-battery-overview-card.js
      type: module
    - url: /zendure_ha/zendure-quick-control-card.js
      type: module
```

---

## Card 1: Power Flow Card

Visualisiert den Energie-Fluss zwischen Solar, Batterie, Haus und Netz.

### Konfiguration:

```yaml
type: custom:zendure-power-flow-card
entity: sensor.zendure_manager_power
entities:
  solar: sensor.zendure_manager_solar_input_power
  battery: sensor.zendure_manager_available_kwh
  battery_soc: sensor.zendure_manager_electric_level
  home: sensor.zendure_manager_home_output_power
  grid: sensor.p1_meter
  operation: select.zendure_manager_operation
```

### Features:
- ✅ Animierte Energie-Flüsse
- ✅ Farbcodierung (Laden/Entladen)
- ✅ Aktueller Operation Mode
- ✅ Auto-Update

---

## Card 2: Battery Overview Card

Zeigt alle Batterien mit SoC, Temperatur und aktueller Leistung.

### Konfiguration:

```yaml
type: custom:zendure-battery-overview-card
devices:
  - entity: sensor.hyper_2000_1_electric_level
    name: Hyper 2000 #1
  - entity: sensor.hyper_2000_2_electric_level
    name: Hyper 2000 #2
  - entity: sensor.hyper_2000_3_electric_level
    name: Hyper 2000 #3
  - entity: sensor.sf800_pro_electric_level
    name: SF800 Pro
  - entity: sensor.solarflow_2400_electric_level
    name: SolarFlow 2400 AC
```

### Features:
- ✅ Alle Geräte auf einen Blick
- ✅ Fortschrittsbalken mit Farben
- ✅ Temperatur-Anzeige (Warnung bei >40°C)
- ✅ Lade-/Entlade-Leistung
- ✅ Online-Status
- ✅ Gesamt-Statistik

---

## Card 3: Quick Control Card

Schneller Zugriff auf Operation Modi und wichtige Einstellungen.

### Konfiguration:

```yaml
type: custom:zendure-quick-control-card
entity: select.zendure_manager_operation
entities:
  grid_power: number.zendure_manager_grid_charge_power
  target_soc: number.zendure_manager_grid_charge_target_soc
  calibrate: button.zendure_manager_calibrate_all_devices
  calibration_status: sensor.zendure_manager_calibration_status
  next_calibration: sensor.zendure_manager_next_calibration_all
show_calibration_status: true
```

### Features:
- ✅ 4 Mode-Buttons (ein Klick Wechsel)
- ✅ Direkte Eingabe für Netzladen-Leistung
- ✅ Direkte Eingabe für Ziel-SoC
- ✅ Kalibrierungs-Button
- ✅ Kalibrierungs-Status

---

## Komplettes Dashboard Beispiel

```yaml
title: Zendure
views:
  - title: Übersicht
    cards:
      # Schnellsteuerung oben
      - type: custom:zendure-quick-control-card
        entity: select.zendure_manager_operation
        entities:
          grid_power: number.zendure_manager_grid_charge_power
          target_soc: number.zendure_manager_grid_charge_target_soc
          calibrate: button.zendure_manager_calibrate_all_devices
          calibration_status: sensor.zendure_manager_calibration_status
          next_calibration: sensor.zendure_manager_next_calibration_all

      # Energie-Fluss
      - type: custom:zendure-power-flow-card
        entity: sensor.zendure_manager_power
        entities:
          solar: sensor.zendure_manager_solar_input_power
          battery: sensor.zendure_manager_available_kwh
          battery_soc: sensor.zendure_manager_electric_level
          home: sensor.zendure_manager_home_output_power
          grid: sensor.p1_meter
          operation: select.zendure_manager_operation

      # Batterien Übersicht
      - type: custom:zendure-battery-overview-card
        devices:
          - entity: sensor.hyper_2000_1_electric_level
            name: Hyper 2000 #1
          - entity: sensor.hyper_2000_2_electric_level
            name: Hyper 2000 #2
          - entity: sensor.solarflow_2400_electric_level
            name: SolarFlow 2400
```

---

## Anpassung

### Farben ändern:

Die Cards nutzen HA Theme-Variablen. Anpassung über Theme:

```yaml
# In themes.yaml
my_theme:
  primary-color: "#03a9f4"  # Card-Akzent
  card-background-color: "#1e1e1e"
  # etc.
```

### Compact Mode:

Für kleinere Bildschirme oder Tablets:

```yaml
type: custom:zendure-battery-overview-card
devices: [...]
compact: true  # Kleinere Darstellung
```

---

## Troubleshooting

### Cards erscheinen nicht:

1. **Cache leeren:**
   - Browser: Strg+Shift+R (Hard Reload)
   - HA: Einstellungen → System → Erweitert → Frontend Cache löschen

2. **Logs prüfen:**
   ```bash
   ha core logs | grep -i "lovelace\|zendure.*card"
   ```

3. **Manuell registrieren:**
   ```yaml
   lovelace:
     resources:
       - url: /zendure_ha/zendure-power-flow-card.js
         type: module
   ```

### Fehler in Browser Console:

- F12 öffnen → Console Tab
- Fehlermeldungen zeigen Problem

---

## Vorteile

✅ **Bessere Übersicht**
- Alle wichtigen Infos auf einen Blick
- Visuell statt nur Zahlen

✅ **Schnellere Bedienung**
- Ein Klick für Mode-Wechsel
- Keine Entity-Suche mehr

✅ **Professioneller Look**
- Moderne UI
- Animationen
- Responsive Design

✅ **Einfache Konfiguration**
- YAML statt komplizierter Conditional Cards
- Copy-Paste Beispiele

---

_Für v1.6.0 geplant_

