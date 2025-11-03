# Feature: Besseres Error Handling

## Problem

Fehlerbehandlung ist aktuell zu generisch.

**Aktueller Code:**
```python
except Exception as e:
    _LOGGER.error(f"HttpPost error {self.name} {e}!")
```

**Probleme:**
- Alle Fehler werden gleich behandelt
- Keine Unterscheidung zwischen Netzwerk-, Timeout-, oder Geräte-Fehlern
- Keine automatische Wiederherstellung
- Schwierige Diagnose für Nutzer

---

## Lösung

**Spezifische Exception-Typen** mit angepassten Reaktionen.

```python
try:
    response = await self.session.post(url, json=command)
except aiohttp.ClientConnectorError as e:
    _LOGGER.error(f"Cannot connect to {self.name}: {e}")
    self.mark_offline()
except asyncio.TimeoutError:
    _LOGGER.warning(f"Timeout for {self.name}, will retry")
    self.schedule_retry()
except json.JSONDecodeError as e:
    _LOGGER.error(f"Invalid response from {self.name}: {e}")
except aiohttp.ClientError as e:
    _LOGGER.error(f"HTTP error for {self.name}: {e}")
```

---

## Vorteile

✅ **Präzise Diagnose**
- Nutzer weiß genau was schief ging
- Bessere Fehlermeldungen im Log

✅ **Intelligente Recovery**
- Timeout: Retry automatisch
- Connection Error: Offline markieren
- JSON Error: Request überspringen

✅ **Bessere Notifications**
- Spezifische Warnungen an Nutzer
- "Gerät XY offline" vs. "Unbekannter Fehler"

✅ **Einfacheres Debugging**
- Entwickler sehen sofort Problem-Typ
- Schnellere Lösung möglich

---

## Status

**Branch:** `feature/better-error-handling`  
**Basis:** `release/auto-calibration` (v1.5.1)
