# Feature: RPC Methods für MQTT Setup

## Problem

MQTT-Konfiguration erfordert aktuell **Bluetooth (BLE)** Verbindung.

**Was passiert:**
- Nutzer muss physisch nah am Gerät sein
- BLE-Verbindung oft instabil
- Komplizierter Setup-Prozess
- Funktioniert nicht bei allen Geräten

**Aktueller Code:**
```python
# Via BLE MQTT konfigurieren
async def bleMqtt(self, mqtt):
    async with BleakClient(device) as client:
        await self.bleCommand(client, {
            "iotUrl": mqtt.host,
            "password": wifi_psw,
            # ...
        })
```

---

## Lösung

**HTTP RPC Methods** nutzen wie in zenSDK spezifiziert.

**Wie es funktioniert:**
```python
# 1. MQTT Status abfragen
GET /rpc?method=HA.Mqtt.GetStatus

Response:
{
  "connected": true,
  "server": "192.168.1.100",
  "port": 1883
}

# 2. MQTT konfigurieren
POST /rpc
{
  "sn": "WOB1NHMAMXXXXX3",
  "method": "HA.Mqtt.SetConfig",
  "params": {
    "config": {
      "enable": true,
      "server": "192.168.1.100",
      "port": 1883,
      "protocol": "mqtt",
      "username": "zendure",
      "password": "password"
    }
  }
}
```

---

## Vorteile

✅ **Kein Bluetooth mehr nötig**
- Setup über WLAN
- Funktioniert von überall im Netz

✅ **Zuverlässiger**
- HTTP stabiler als BLE
- Weniger Verbindungsfehler

✅ **Einfacher Setup-Flow**
- Direkt in Config Flow integrierbar
- Keine BLE-Scan nötig

✅ **Status-Monitoring**
- MQTT-Verbindung prüfbar
- Diagnostics in UI

---

## Anwendungsfall

**Vorher (BLE-basiert):**
```
1. Gerät in BLE-Reichweite bringen
2. BLE-Scan starten
3. Verbindung aufbauen (oft fehlschlagend)
4. MQTT-Daten übertragen
5. Hoffen dass es funktioniert hat
```

**Nachher (HTTP-basiert):**
```
1. Config Flow öffnen
2. MQTT Server-Daten eingeben
3. "Speichern" klicken
4. FERTIG - sofort aktiv!
```

---

## Config Flow Integration

**Erweiterter Setup:**
```python
async def async_step_mqtt_config(self, user_input):
    """Configure MQTT via HTTP RPC."""
    
    # MQTT Daten vom Nutzer
    mqtt_config = {
        "server": user_input["mqtt_server"],
        "port": user_input["mqtt_port"],
        "username": user_input["mqtt_user"],
        "password": user_input["mqtt_password"]
    }
    
    # An Gerät senden via HTTP
    for device in devices:
        await device.configure_mqtt_http(mqtt_config)
    
    # Status prüfen
    status = await device.get_mqtt_status()
    if status["connected"]:
        # Erfolg!
```

---

## Status

**Branch:** `feature/rpc-mqtt-setup`  
**Basis:** `release/auto-calibration` (v1.5.1)  
**Implementierung:** Offen

---

_Referenz: [zenSDK - RPC Methods](https://github.com/Zendure/zenSDK)_
