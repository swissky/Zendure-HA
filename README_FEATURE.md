# Feature: Connection Health Monitoring

## Problem

Nutzer sehen nicht **wie gut** die Verbindung zu Geräten ist.

**Aktuell:**
- Nur "online" oder "offline"
- Keine Information über Verbindungsqualität
- Langsame Verbindungen fallen nicht auf
- Probleme werden erst spät erkannt

---

## Lösung

**Connection Health Sensor** für jedes Gerät.

```python
sensor.device_connection_health:
  States:
    - "excellent" (< 100ms Antwortzeit)
    - "good" (100-500ms)
    - "fair" (500-2000ms)
    - "poor" (2000-5000ms)
    - "offline" (Timeout/Fehler)
```

**Wie es gemessen wird:**
```python
start = time.time()
await self.httpGet("properties/report")
latency = (time.time() - start) * 1000  # ms

if latency < 100:
    health = "excellent"
elif latency < 500:
    health = "good"
# ...
```

---

## Vorteile

✅ **Proaktive Fehlererkennung**
- Probleme sichtbar bevor Gerät offline geht
- "poor" → Nutzer kann reagieren

✅ **Netzwerk-Diagnose**
- Sieht ob WLAN zu schwach ist
- Kann Gerät näher an Router platzieren

✅ **Automatisierbar**
- Benachrichtigung bei schlechter Verbindung
- Automatisches Fallback zu Cloud-Modus

✅ **Historische Daten**
- Verbindungsqualität über Zeit
- Erkennt Muster und Probleme

---

## Anwendungsfall

**Automation basierend auf Health:**
```yaml
# Warnung bei schlechter Verbindung
- trigger:
    platform: state
    entity_id: sensor.hyper_2000_connection_health
    to: "poor"
  action:
    service: notify.mobile_app
    data:
      message: "Hyper 2000 hat schlechte WLAN-Verbindung!"

# Automatisches Fallback
- trigger:
    platform: state
    entity_id: sensor.hyper_2000_connection_health
    to: "offline"
  action:
    # Wechsel zu Cloud-Modus
    service: select.select_option
    data:
      entity_id: select.hyper_2000_connection
      option: "cloud"
```

---

## Status

**Branch:** `feature/connection-health`  
**Basis:** `release/auto-calibration` (v1.5.1)
