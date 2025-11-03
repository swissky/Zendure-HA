# Feature: HTTP Timeouts

## Problem

Die HTTP-Kommunikation mit Zendure-Geräten hat aktuell **keine Timeouts** konfiguriert.

**Was passiert:**
- Wenn ein Gerät nicht antwortet, wartet Home Assistant **unbegrenzt**
- Die Integration "friert ein" und blockiert
- Nutzer sehen keine Updates mehr
- Manuelle Neustarts nötig

**Betroffener Code:**
```python
# device.py - ZendureZenSdk
response = await self.session.get(url, headers=CONST_HEADER)
# ⚠️ Kein Timeout!
```

---

## Lösung

HTTP-Requests mit **konfigurierbaren Timeouts** versehen.

**Wie es funktioniert:**
```python
import aiohttp

# Timeout-Konfiguration
timeout = aiohttp.ClientTimeout(
    total=5,      # Gesamte Request: max 5 Sekunden
    connect=2     # Verbindungsaufbau: max 2 Sekunden
)

# Bei jedem Request
response = await self.session.get(url, timeout=timeout, headers=CONST_HEADER)
```

**Bei Timeout:**
- Request wird abgebrochen
- Fehler geloggt
- Gerät wird als offline markiert
- Nächster Update-Zyklus versucht es erneut

---

## Vorteile

✅ **Keine eingefrorene Integration mehr**
- Home Assistant bleibt responsiv auch bei Netzwerk-Problemen

✅ **Schnelleres Offline-Erkennung**
- Geräte werden nach 5 Sekunden als offline markiert
- Statt minutenlang zu warten

✅ **Bessere User Experience**
- UI bleibt immer bedienbar
- Klare Fehlermeldungen

✅ **Robustheit**
- Automatische Recovery beim nächsten Update
- Kein manueller Eingriff nötig

---

## Anwendungsfall

**Szenario: Gerät hat WLAN-Probleme**

**Vorher:**
```
15:00 - Gerät verliert WLAN
15:01 - HTTP Request hängt...
15:02 - Noch am Warten...
15:05 - Home Assistant UI reagiert nicht mehr
       → Nutzer muss HA neu starten
```

**Nachher:**
```
15:00 - Gerät verliert WLAN
15:01 - HTTP Request startet
15:01:05 - Timeout nach 5 Sekunden
15:01:05 - Gerät als "offline" markiert
15:02 - Nächster Versuch
       → HA läuft normal weiter
```

---

## Konfigurierbarkeit

**Standard-Werte:**
- `total`: 5 Sekunden (gesamt)
- `connect`: 2 Sekunden (Verbindung)

**Optional erweiterbar:**
```python
# In const.py
class HttpDefaults:
    TIMEOUT_TOTAL = 5
    TIMEOUT_CONNECT = 2
    TIMEOUT_READ = 3
```

---

## Kompatibilität

**Betrifft nur:**
- ZenSDK-Geräte (SF800, SF800 Pro, SF2400 AC)
- Geräte die HTTP API nutzen

**Betrifft NICHT:**
- Legacy-Geräte (nur MQTT)
- Cloud-Verbindung

---

## Status

**Branch:** `feature/http-timeouts`  
**Basis:** `release/auto-calibration` (v1.5.1)  
**Implementierung:** Offen  
**Testing:** Ausstehend

---

## Nächste Schritte

1. Timeouts in `httpGet()` und `httpPost()` hinzufügen
2. Error Handling für `asyncio.TimeoutError` verbessern
3. Logging für Timeout-Events
4. Testen mit Device-Disconnect-Szenarien
5. Release als v1.6.0

---

_Siehe auch: [Zendure zenSDK](https://github.com/Zendure/zenSDK)_

