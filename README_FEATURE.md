# Feature: Multi-Protocol Failover

## Problem

Verbindung ist entweder **Cloud** ODER **Lokal** - kein automatisches Failover.

**Aktuell:**
- Nutzer wählt "Cloud" oder "zenSDK"
- Bei lokalem Fehler: Gerät offline
- Kein automatischer Wechsel zu Cloud

---

## Lösung

**Automatisches Failover** zwischen Protokollen.

```
Versuch 1: Lokal (HTTP) → Schnell
Wenn fehlschlägt: Cloud (MQTT) → Fallback
```

---

## Vorteile

✅ **Höhere Verfügbarkeit**
- Funktioniert auch bei lokalen Problemen

✅ **Automatische Recovery**
- Kein manueller Eingriff

✅ **Best of Both**
- Lokal wenn möglich (schnell)
- Cloud als Backup (zuverlässig)

---

## Status

**Branch:** `feature/multi-protocol-failover`
