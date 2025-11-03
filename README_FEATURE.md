# Feature: Property Validation

## Problem

Keine Validierung ob Properties **writable** sind.

**Aktuell:**
```python
# Schreibt blind jede Property
await httpPost("properties/write", {"properties": {name: value}})
```

**Probleme:**
- Read-only Properties können nicht geschrieben werden
- Fehler erst vom Gerät gemeldet
- Unklare Fehlermeldungen

---

## Lösung

**Property-Definitionen** pro Geräte-Typ mit Validierung.

```python
# Definiere writable properties pro Model
WRITABLE_PROPERTIES = {
    "SolarFlow800": ["acMode", "inputLimit", "outputLimit", ...],
    "Hyper2000": ["smartMode", "acMode", ...],
}

# Vor dem Schreiben prüfen
if property_name in WRITABLE_PROPERTIES[model]:
    await httpPost(...)
else:
    raise ValueError(f"{property_name} is read-only!")
```

---

## Vorteile

✅ **Klarere Fehler**
- "Property X ist read-only" statt "Command failed"

✅ **Verhindert ungültige Commands**
- Keine Requests die sowieso fehlschlagen

✅ **Dokumentation**
- Properties klar definiert
- Entwickler wissen was möglich ist

---

## Status

**Branch:** `feature/property-validation`
