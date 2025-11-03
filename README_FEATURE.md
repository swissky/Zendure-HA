# Feature: mDNS Device Discovery

## Problem

Geräte müssen aktuell **manuell** ins Netzwerk integriert werden.

**Was passiert:**
- Integration kennt Geräte nur über Cloud-API
- IP-Adressen werden "geraten" (`zendure-model-sn.local`)
- Funktioniert nicht immer (DNS-Probleme)
- Nutzer können nicht sehen welche Geräte lokal verfügbar sind

**Aktueller Ansatz:**
```python
# IP wird konstruiert basierend auf Modell + Serial
self.ipAddress = f"zendure-{model}-{snNumber}.local"

# Problem: .local DNS nicht überall verfügbar!
# Problem: Keine Discovery von neuen Geräten!
```

---

## Lösung

**mDNS Service Discovery** nutzen wie in zenSDK spezifiziert.

**Wie es funktioniert:**
```python
# Zendure-Geräte broadcasten automatisch:
Service: _zendure._tcp.local
Name: Zendure-SolarFlow800-WOB1NHMAMXXXXX3
IP: 192.168.1.123
Port: 80

# Home Assistant kann das automatisch erkennen:
from zeroconf import ServiceBrowser, Zeroconf

class ZendureDiscovery:
    def on_service_found(self, name, ip, port):
        # Automatisch Gerät hinzufügen!
```

**zenSDK Service Format:**
- **Service-Name:** `Zendure-<Model>-<Last12MAC>`
- **Service-Type:** `_zendure._tcp.local.`
- **Broadcast:** Automatisch beim Netzwerk-Connect

---

## Vorteile

✅ **Automatische Geräte-Erkennung**
- Nutzer muss nichts manuell konfigurieren
- Neue Geräte erscheinen automatisch in HA

✅ **Zuverlässige IP-Adressen**
- Direkt vom Gerät gemeldet
- Keine DNS-Auflösung nötig
- Funktioniert auch bei Netzwerk-Änderungen

✅ **Bessere User Experience**
- Setup wird **dramatisch** einfacher
- Kein technisches Wissen nötig
- "Plug & Play" Erlebnis

✅ **Discovery UI in Home Assistant**
- Geräte erscheinen als "Entdeckt" in UI
- Ein Klick zum Hinzufügen
- Wie bei anderen Integrationen (Philips Hue, etc.)

---

## Anwendungsfall

**Szenario: Neues Gerät hinzufügen**

**Vorher:**
```
1. Gerät einschalten
2. In Zendure App einrichten
3. Cloud-API Token holen
4. In HA Integration eintragen
5. Hoffen dass .local DNS funktioniert
6. Bei Problemen: IP manuell rausfinden
```

**Nachher:**
```
1. Gerät einschalten
2. In HA: Benachrichtigung "Neues Zendure-Gerät gefunden!"
3. Klick auf "Konfigurieren"
4. FERTIG!
```

---

## Technische Details

### mDNS Libraries für Home Assistant:

**Option 1: zeroconf (bereits in HA)**
```python
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

class ZendureMDNSDiscovery:
    def __init__(self, hass):
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(
            self.zeroconf,
            "_zendure._tcp.local.",
            handlers=[self._on_service_change]
        )
    
    def _on_service_change(self, zeroconf, service_type, name, state_change):
        if state_change == ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            # Extract: IP, Model, Serial Number
            # Trigger HA Discovery Flow
```

**Option 2: HA's eigenes mDNS (homeassistant.components.zeroconf)**
```python
from homeassistant.components import zeroconf

async def async_setup(hass, config):
    await zeroconf.async_get_async_instance(hass)
    # Register mDNS browser
```

### Service-Name Parsing:
```
Name: "Zendure-SolarFlow800-WOB1NHMAMXXXXX3"
→ Model: "SolarFlow800"
→ Serial: "WOB1NHMAMXXXXX3" (letzten 12 Zeichen der MAC)
```

---

## Integration in Config Flow

**Erweiterte Discovery:**
```python
class ZendureConfigFlow(ConfigFlow):
    async def async_step_zeroconf(self, discovery_info):
        """Handle mDNS discovered device."""
        # Automatisch Gerät vorschlagen
        # Nutzer bestätigt nur noch
        
    async def async_step_user(self, user_input):
        """Manuelle Eingabe als Fallback."""
        # Wie bisher für Cloud-only Setup
```

---

## Kompatibilität

**Unterstützte Geräte (zenSDK):**
- ✅ SolarFlow 800
- ✅ SolarFlow 800 Pro
- ✅ SolarFlow 2400 AC
- ✅ SmartMeter 3CT

**Legacy-Geräte:**
- Hyper 2000, Hub1200, Hub2000: Kein mDNS (nutzen weiter Cloud)
- Funktionieren wie bisher

---

## Voraussetzungen

**Home Assistant:**
- `zeroconf` Integration (bereits eingebaut)
- Geräte im selben Netzwerk

**Zendure-Geräte:**
- Aktuelle Firmware (mDNS Support)
- Im WLAN verbunden

**Netzwerk:**
- mDNS/Bonjour nicht blockiert
- Multicast erlaubt

---

## Testplan

1. **Discovery Test:**
   - Gerät einschalten → Erscheint in HA Benachrichtigungen
   
2. **Multi-Device Test:**
   - Mehrere Geräte → Alle werden erkannt
   
3. **Network Change Test:**
   - IP ändert sich → Discovery aktualisiert automatisch

4. **Fallback Test:**
   - mDNS blockiert → Nutzer kann manuell konfigurieren

---

## Status

**Branch:** `feature/mdns-discovery`  
**Basis:** `release/auto-calibration` (v1.5.1)  
**Implementierung:** Offen  
**Testing:** Ausstehend

---

_Referenz: [Zendure zenSDK](https://github.com/Zendure/zenSDK) - mDNS Discovery_
