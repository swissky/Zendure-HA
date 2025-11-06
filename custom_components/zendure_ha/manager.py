"""Coordinator for Zendure integration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import traceback
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from math import sqrt
from pathlib import Path
from typing import Any

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.auth.providers import homeassistant as auth_ha
from homeassistant.components import bluetooth, persistent_notification
from homeassistant.components.number import NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.loader import async_get_integration

from .api import Api
from .button import ZendureButton
from .const import (
    CalibrationDefaults,
    CONF_CALIB_ENABLED,
    CONF_CALIB_INTERVAL_DAYS,
    CONF_CALIB_MODE,
    CONF_CALIB_PRICE_SENSOR,
    CONF_CALIB_PRICE_THRESHOLD,
    CONF_CALIB_SOC_MAX,
    CONF_CALIB_SOC_MIN,
    CONF_CALIB_TIME_END,
    CONF_CALIB_TIME_START,
    CONF_GRID_CHARGE_POWER,
    CONF_P1METER,
    CONF_TARGET_EXPORT,
    DOMAIN,
    DeviceState,
    GridChargingDefaults,
    SmartMatchingDefaults,
    SmartMode,
)
from .device import DeviceSettings, ZendureDevice, ZendureLegacy
from .entity import EntityDevice
from .fusegroup import FuseGroup
from .number import ZendureNumber, ZendureRestoreNumber
from .select import ZendureRestoreSelect, ZendureSelect
from .sensor import ZendureSensor
from .switch import ZendureSwitch

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type ZendureConfigEntry = ConfigEntry[ZendureManager]


class ZendureManager(DataUpdateCoordinator[None], EntityDevice):
    """Class to regular update devices."""

    devices: list[ZendureDevice] = []
    fuseGroups: list[FuseGroup] = []
    simulation: bool = False

    def __init__(self, hass: HomeAssistant, entry: ZendureConfigEntry) -> None:
        """Initialize Zendure Manager."""
        super().__init__(hass, _LOGGER, name="Zendure Manager", update_interval=SCAN_INTERVAL, config_entry=entry)
        EntityDevice.__init__(self, hass, "manager", "Zendure Manager", "Zendure Manager")
        self.api = Api()
        self.operation = 0
        self.zero_next = datetime.min
        self.zero_fast = datetime.min
        self.check_reset = datetime.min
        self.power_history: deque[int] = deque(maxlen=25)
        self.p1_history: deque[int] = deque([25, -25], maxlen=8)
        self.pwr_total = 0
        self.pwr_avg = 0
        self.pwr_count = 0
        self.pwr_update = 0
        # Track mode changes to prevent oscillation
        self.last_mode: str = "idle"  # "idle", "charging", "discharging"
        self.last_mode_change: datetime = datetime.min
        self.p1meterEvent: Callable[[], None] | None = None
        self.p1_unit_logged: bool = False  # Track if we've logged the P1 meter unit
        self.update_count = 0

    async def loadDevices(self) -> None:
        if self.config_entry is None or (data := await Api.Connect(self.hass, dict(self.config_entry.data), True)) is None:
            return
        if (mqtt := data.get("mqtt")) is None:
            return

        # get version number from integration
        integration = await async_get_integration(self.hass, DOMAIN)
        if integration is None:
            _LOGGER.error("Integration not found for domain: %s", DOMAIN)
            return
        self.attr_device_info["sw_version"] = integration.manifest.get("version", "unknown")

        self.operationmode = (ZendureRestoreSelect(self, "Operation", {0: "off", 1: "manual", 2: "smart", 3: "smart_discharging", 4: "smart_charging", 5: "grid_charging"}, self.update_operation),)
        self.manualpower = ZendureRestoreNumber(self, "manual_power", None, None, "W", "power", 10000, -10000, NumberMode.BOX, True)
        
        # Grid Charging Power - TOTAL limit for all devices (not per device!)
        saved_grid_power = self.config_entry.data.get(CONF_GRID_CHARGE_POWER, GridChargingDefaults.POWER)
        async def save_grid_power(_entity: Any, value: Any) -> None:
            data = self.config_entry.data | {CONF_GRID_CHARGE_POWER: int(value)}
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        self.gridChargepower = ZendureNumber(self, "grid_charge_power", save_grid_power, None, "W", "power", 10000, 100, NumberMode.BOX, 1, True)
        self.gridChargepower._attr_native_value = float(saved_grid_power)
        self.gridChargepower._attr_icon = "mdi:battery-charging"
        self.gridChargepower._attr_entity_category = EntityCategory.CONFIG
        
        self.availableKwh = ZendureSensor(self, "available_kwh", None, "kWh", "energy", None, 1)
        self.power = ZendureSensor(self, "power", None, "W", "power", None, 0)
        
        # DEBUG SENSOR - Shows last P1 value and timestamp
        self.debugP1Sensor = ZendureSensor(self, "debug_p1_last", None, None, None, None)
        self.debugP1Sensor._attr_icon = "mdi:chart-line"
        
        # DEBUG SENSOR - Shows Grid Charging status
        self.debugGridCharging = ZendureSensor(self, "debug_grid_charging", None, None, None, None)
        self.debugGridCharging._attr_icon = "mdi:battery-charging"
        
        # Aggregate sensors (automatically sum all devices)
        self.totalSolarPower = ZendureSensor(self, "total_solar_power", None, "W", "power", "measurement", 0)
        self.totalSolarPower._attr_icon = "mdi:solar-panel"
        
        self.totalBatteryCapacity = ZendureSensor(self, "total_battery_capacity", None, "kWh", "energy", "measurement", 1)
        self.totalBatteryCapacity._attr_icon = "mdi:battery-outline"
        
        self.totalBatteryAvailable = ZendureSensor(self, "total_battery_available", None, "kWh", "energy", "measurement", 1)
        self.totalBatteryAvailable._attr_icon = "mdi:battery"
        
        self.totalBatterySoc = ZendureSensor(self, "total_battery_soc", None, "%", "battery", "measurement", 0)
        self.totalBatterySoc._attr_icon = "mdi:battery-50"
        
        self.totalHomeOutput = ZendureSensor(self, "total_home_output", None, "W", "power", "measurement", 0)
        self.totalHomeOutput._attr_icon = "mdi:home"
        
        self.totalGridInput = ZendureSensor(self, "total_grid_input", None, "W", "power", "measurement", 0)
        self.totalGridInput._attr_icon = "mdi:transmission-tower"
        
        # ═══════════════════════════════════════════════════════════
        # CALIBRATION - ALL settings in Manager Device!
        # ═══════════════════════════════════════════════════════════
        
        # Helper function to create save callback for config_entry
        def make_save_callback(config_key: str):
            async def save_to_config(_entity: Any, value: Any) -> None:
                # Convert to proper type (float for prices, int for others)
                if config_key == CONF_CALIB_PRICE_THRESHOLD:
                    typed_value = float(value)
                else:
                    typed_value = int(value)
                data = self.config_entry.data | {config_key: typed_value}
                self.hass.config_entries.async_update_entry(self.config_entry, data=data)
                # Update status display
                self._update_calibration_status()
            return save_to_config
        
        # Read initial values from config
        saved_enabled = self.config_entry.data.get(CONF_CALIB_ENABLED, CalibrationDefaults.ENABLED)
        saved_mode = self.config_entry.data.get(CONF_CALIB_MODE, CalibrationDefaults.MODE)
        saved_interval = self.config_entry.data.get(CONF_CALIB_INTERVAL_DAYS, CalibrationDefaults.INTERVAL_DAYS)
        saved_time_start = self.config_entry.data.get(CONF_CALIB_TIME_START, CalibrationDefaults.TIME_START)
        saved_time_end = self.config_entry.data.get(CONF_CALIB_TIME_END, CalibrationDefaults.TIME_END)
        saved_soc_min = self.config_entry.data.get(CONF_CALIB_SOC_MIN, CalibrationDefaults.SOC_MIN)
        saved_soc_max = self.config_entry.data.get(CONF_CALIB_SOC_MAX, CalibrationDefaults.SOC_MAX)
        saved_price_threshold = self.config_entry.data.get(CONF_CALIB_PRICE_THRESHOLD, CalibrationDefaults.PRICE_THRESHOLD)
        saved_price_sensor = self.config_entry.data.get(CONF_CALIB_PRICE_SENSOR, "")
        
        # Switch: Enable/Disable
        async def save_enabled(_entity: Any, value: Any) -> None:
            data = self.config_entry.data | {CONF_CALIB_ENABLED: bool(value)}
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            self._update_calibration_status()
        self.calib01_enabled = ZendureSwitch(self, "calib01_enabled", save_enabled, None, None, saved_enabled)
        self.calib01_enabled._attr_entity_category = EntityCategory.CONFIG
        
        # Select: Mode (all_together / individual) - using ZendureSelect instead of Restore
        mode_options = ["all_together", "individual"]
        mode_dict = {i: opt for i, opt in enumerate(mode_options)}
        mode_current = 0 if saved_mode == "all_together" else 1
        
        async def save_mode(_entity: Any, value: Any) -> None:
            # value is the key (0 or 1)
            mode_str = mode_dict[value]
            data = self.config_entry.data | {CONF_CALIB_MODE: mode_str}
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        
        self.calib02_mode = ZendureSelect(self, "calib02_mode", mode_dict, save_mode, mode_current)
        self.calib02_mode._attr_entity_category = EntityCategory.CONFIG
        
        # Number: Interval (days)
        self.calib03_interval = ZendureNumber(
            self, "calib03_interval", make_save_callback(CONF_CALIB_INTERVAL_DAYS),
            None, "Tage", None,
            CalibrationDefaults.MAX_INTERVAL_DAYS, CalibrationDefaults.MIN_INTERVAL_DAYS,
            NumberMode.BOX, 1, True
        )
        self.calib03_interval._attr_native_value = float(saved_interval)
        self.calib03_interval._attr_entity_category = EntityCategory.CONFIG
        
        # Number: Time Start (hour)
        self.calib04_time_start = ZendureNumber(
            self, "calib04_time_start", make_save_callback(CONF_CALIB_TIME_START),
            None, "Uhr", None,
            23, 0, NumberMode.BOX, 1, True
        )
        self.calib04_time_start._attr_native_value = float(saved_time_start)
        self.calib04_time_start._attr_entity_category = EntityCategory.CONFIG
        
        # Number: Time End (hour)
        self.calib05_time_end = ZendureNumber(
            self, "calib05_time_end", make_save_callback(CONF_CALIB_TIME_END),
            None, "Uhr", None,
            23, 0, NumberMode.BOX, 1, True
        )
        self.calib05_time_end._attr_native_value = float(saved_time_end)
        self.calib05_time_end._attr_entity_category = EntityCategory.CONFIG
        
        # Number: SoC Min (%)
        self.calib06_soc_min = ZendureNumber(
            self, "calib06_soc_min", make_save_callback(CONF_CALIB_SOC_MIN),
            None, "%", None,
            100, 0, NumberMode.BOX, 1, True
        )
        self.calib06_soc_min._attr_native_value = float(saved_soc_min)
        self.calib06_soc_min._attr_icon = "mdi:battery-low"
        self.calib06_soc_min._attr_entity_category = EntityCategory.CONFIG
        
        # Number: SoC Max (%)
        self.calib07_soc_max = ZendureNumber(
            self, "calib07_soc_max", make_save_callback(CONF_CALIB_SOC_MAX),
            None, "%", None,
            100, 0, NumberMode.BOX, 1, True
        )
        self.calib07_soc_max._attr_native_value = float(saved_soc_max)
        self.calib07_soc_max._attr_icon = "mdi:battery-high"
        self.calib07_soc_max._attr_entity_category = EntityCategory.CONFIG
        
        # Number: Price Threshold (ct/kWh, optional - 0 = deaktiviert)
        self.calib08_price_max = ZendureNumber(
            self, "calib08_price_max", make_save_callback(CONF_CALIB_PRICE_THRESHOLD),
            None, "ct/kWh", None,
            CalibrationDefaults.MAX_PRICE, 0,  # Min ist 0 (= deaktiviert)
            NumberMode.BOX, 1, True
        )
        self.calib08_price_max._attr_native_value = float(saved_price_threshold)  # MUST be float!
        self.calib08_price_max._attr_entity_category = EntityCategory.CONFIG
        
        # Select: Price Sensor (optional) - using ZendureSelect for proper functionality
        sensor_list = ["Kein Sensor (nur Zeitfenster)"]
        state = self.hass.states.async_all()
        for entity in state:
            if entity.domain == "sensor" and entity.attributes.get("unit_of_measurement", "").startswith(("€", "CHF", "$", "ct")):
                sensor_list.append(entity.entity_id)
        
        sensor_dict = {i: v for i, v in enumerate(sensor_list)}
        sensor_current = 0
        if saved_price_sensor and saved_price_sensor in sensor_list:
            sensor_current = sensor_list.index(saved_price_sensor)
        
        async def save_price_sensor(_entity: Any, value: Any) -> None:
            # value is the index key
            sensor_id = "" if value == 0 else sensor_list[value]
            data = self.config_entry.data | {CONF_CALIB_PRICE_SENSOR: sensor_id}
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        
        self.calib09_price_sensor = ZendureSelect(self, "calib09_price_sensor", sensor_dict, save_price_sensor, sensor_current)
        self.calib09_price_sensor._attr_entity_category = EntityCategory.CONFIG
        
        # Read-only status displays
        self.calibrationStatus = ZendureSensor(self, "calibration_status", None, None, None, None)
        self.nextCalibrationAll = ZendureSensor(self, "next_calibration_all", None, None, "timestamp", None)
        self.calibrateAllButton = ZendureButton(self, "calibrate_all_devices", self.button_calibrate_all)
        
        # Initialize with default values (will be updated when devices are loaded)
        next_date = datetime.now() + timedelta(days=saved_interval)
        self.calibrationStatus.update_value("Aktiviert" if saved_enabled else "Deaktiviert")
        self.nextCalibrationAll.update_value(next_date.isoformat())

        # load devices
        for dev in data["deviceList"]:
            try:
                if (deviceId := dev["deviceKey"]) is None or (prodModel := dev["productModel"]) is None:
                    continue
                _LOGGER.info(f"Adding device: {deviceId} {prodModel} => {dev}")

                init = Api.createdevice.get(prodModel.lower(), None)
                if init is None:
                    _LOGGER.info(f"Device {prodModel} is not supported!")
                    continue

                # create the device and mqtt server
                device = init(self.hass, deviceId, prodModel, dev)
                Api.devices[deviceId] = device

                if Api.localServer is not None and Api.localServer != "":
                    try:
                        psw = hashlib.md5(deviceId.encode()).hexdigest().upper()[8:24]  # noqa: S324
                        provider: auth_ha.HassAuthProvider = auth_ha.async_get_provider(self.hass)
                        credentials = await provider.async_get_or_create_credentials({"username": deviceId.lower()})
                        user = await self.hass.auth.async_get_user_by_credentials(credentials)
                        if user is None:
                            user = await self.hass.auth.async_create_user(deviceId, group_ids=[GROUP_ID_USER], local_only=False)
                            await provider.async_add_auth(deviceId.lower(), psw)
                            await self.hass.auth.async_link_user(user, credentials)
                        else:
                            await provider.async_change_password(deviceId.lower(), psw)

                        _LOGGER.info(f"Created MQTT user: {deviceId} with password: {psw}")

                    except Exception as err:
                        _LOGGER.error(err)

            except Exception as e:
                _LOGGER.error(f"Unable to create device {e}!")
                _LOGGER.error(traceback.format_exc())

        self.devices = list(Api.devices.values())
        _LOGGER.info(f"Loaded {len(self.devices)} devices")

        # initialize the api & p1 meter
        await EntityDevice.add_entities()
        self.api.Init(self.config_entry.data, mqtt)
        self.update_p1meter(self.config_entry.data.get(CONF_P1METER, "sensor.power_actual"))
        await asyncio.sleep(1)  # allow other tasks to run
        self.update_fusegroups()
        Api.mqttLogging = True
        
        # Update calibration status now that devices are loaded
        self._update_calibration_status()

    def update_fusegroups(self) -> None:
        _LOGGER.info("Update fusegroups")

        # updateFuseGroup callback
        def updateFuseGroup(_entity: ZendureRestoreSelect, _value: Any) -> None:
            self.update_fusegroups()

        fuseGroups: dict[str, FuseGroup] = {}
        for device in self.devices:
            try:
                if device.fuseGroup.onchanged is None:
                    device.fuseGroup.onchanged = updateFuseGroup

                fg: FuseGroup | None = None
                match device.fuseGroup.state:
                    case "owncircuit" | "group3600":
                        fg = FuseGroup(device.name, 3600, -3600)
                    case "group800":
                        fg = FuseGroup(device.name, 800, -1200)
                    case "group1200":
                        fg = FuseGroup(device.name, 1200, -1200)
                    case "group2000":
                        fg = FuseGroup(device.name, 2000, -2000)
                    case "group2400":
                        fg = FuseGroup(device.name, 2400, -2400)
                    case _:
                        _LOGGER.debug("Device %s has unsupported fuseGroup state: %s", device.name, device.fuseGroup.state)
                        continue

                if fg is not None:
                    fg.devices.append(device)
                    fuseGroups[device.deviceId] = fg
            except AttributeError as err:
                _LOGGER.error("Device %s missing fuseGroup attribute: %s", device.name, err)
            except Exception as err:
                _LOGGER.error("Unable to create fusegroup for device %s (%s): %s", device.name, device.deviceId, err, exc_info=True)

        # Update the fusegroups and select optins for each device
        for device in self.devices:
            try:
                fusegroups: dict[Any, str] = {
                    0: "unused",
                    1: "owncircuit",
                    2: "group800",
                    3: "group1200",
                    4: "group2000",
                    5: "group2400",
                    6: "group3600",
                }
                for deviceId, fg in fuseGroups.items():
                    if deviceId != device.deviceId:
                        fusegroups[deviceId] = f"Part of {fg.name} fusegroup"
                device.fuseGroup.setDict(fusegroups)
            except AttributeError as err:
                _LOGGER.error("Device %s missing fuseGroup attribute: %s", device.name, err)
            except Exception as err:
                _LOGGER.error("Unable to update fusegroup options for device %s (%s): %s", device.name, device.deviceId, err, exc_info=True)

        # Add devices to fusegroups
        for device in self.devices:
            if fg := fuseGroups.get(device.fuseGroup.value):
                device.fuseGrp = fg
                fg.devices.append(device)
            device.setStatus()

        # check if we can split fuse groups
        self.fuseGroups.clear()
        for fg in fuseGroups.values():
            if len(fg.devices) > 1 and fg.maxpower >= sum(d.limitDischarge for d in fg.devices) and fg.minpower <= sum(d.limitCharge for d in fg.devices):
                for d in fg.devices:
                    self.fuseGroups.append(FuseGroup(d.name, d.limitDischarge, d.limitCharge, [d]))
            else:
                for d in fg.devices:
                    d.fuseGrp = fg
                self.fuseGroups.append(fg)

    async def button_calibrate_all(self, _button: Any) -> None:
        """Manually trigger calibration for all devices."""
        from homeassistant.components import persistent_notification
        
        _LOGGER.info("Manual calibration triggered for all devices")
        
        calibrated = 0
        failed = 0
        offline = 0
        
        for device in self.devices:
            if not device.online:
                offline += 1
                continue
            
            success = await device.start_calibration(manual=True)
            if success:
                calibrated += 1
            else:
                failed += 1
        
        # Show summary notification
        message = f"Calibration started for {calibrated} device(s)"
        if failed > 0:
            message += f", {failed} failed"
        if offline > 0:
            message += f", {offline} offline"
        
        persistent_notification.async_create(
            self.hass,
            message,
            "Zendure Calibration",
            "zendure_calibration_all",
        )
        
        _LOGGER.info("Calibration summary: %d started, %d failed, %d offline", calibrated, failed, offline)

    def _update_aggregate_sensors(self) -> None:
        """Update aggregate sensors by summing all devices."""
        if not hasattr(self, 'devices') or not self.devices:
            return
        
        total_solar = 0
        total_capacity = 0
        total_available = 0
        total_home_output = 0
        total_grid_input = 0
        
        for device in self.devices:
            # Sum solar input (nur positive Werte)
            if hasattr(device, 'solarInput'):
                solar = device.solarInput.asInt
                if solar > 0:
                    total_solar += solar
            
            # Sum battery capacity (kWh)
            if hasattr(device, 'kWh'):
                total_capacity += device.kWh
            
            # Sum available energy (kWh currently in batteries)
            if hasattr(device, 'availableKwh'):
                total_available += device.availableKwh.asNumber
            
            # Sum home output (NETTO: output - input)
            # For Smart Matching, we need NETTO power, not raw output
            # If device outputs 2000W but draws 500W from grid, netto = 1500W
            if hasattr(device, 'homeOutput') and hasattr(device, 'homeInput'):
                # Netto = Output - Input (positive = discharging, negative = charging)
                netto = device.homeOutput.asInt - device.homeInput.asInt
                total_home_output += netto
            elif hasattr(device, 'homeOutput'):
                # Fallback if homeInput not available
                total_home_output += device.homeOutput.asInt
            
            # Sum grid input
            if hasattr(device, 'homeInput'):
                total_grid_input += device.homeInput.asInt
        
        # Calculate total SoC (%)
        total_soc = (total_available / total_capacity * 100) if total_capacity > 0 else 0
        
        # Update sensors
        self.totalSolarPower.update_value(total_solar)
        self.totalBatteryCapacity.update_value(total_capacity)
        self.totalBatteryAvailable.update_value(total_available)
        self.totalBatterySoc.update_value(total_soc)
        self.totalHomeOutput.update_value(total_home_output)
        self.totalGridInput.update_value(total_grid_input)
        
        # FORCE visible aggregate logs
        agg_msg = f"Aggregates: Solar={total_solar}W, Available={total_available:.1f}/{total_capacity:.1f}kWh ({total_soc:.0f}%), Home={total_home_output}W, Grid={total_grid_input}W"
        _LOGGER.info(agg_msg)
        print(f"[ZENDURE] {agg_msg}")

    def _update_calibration_status(self) -> None:
        """Update the calibration status display sensors."""
        saved_enabled = self.config_entry.data.get(CONF_CALIB_ENABLED, CalibrationDefaults.ENABLED)
        saved_interval = self.config_entry.data.get(CONF_CALIB_INTERVAL_DAYS, CalibrationDefaults.INTERVAL_DAYS)
        
        # Update status text
        status_text = "Aktiviert" if saved_enabled else "Deaktiviert"
        self.calibrationStatus.update_value(status_text)
        _LOGGER.debug(f"Calibration status updated: {status_text}")
        
        # Calculate next calibration date
        if saved_enabled:
            # Find oldest last_calibration date (only if devices are loaded)
            oldest_date = datetime.min
            if hasattr(self, 'devices') and self.devices:
                for device in self.devices:
                    if hasattr(device, 'last_calibration') and device.last_calibration != datetime.min:
                        if oldest_date == datetime.min or device.last_calibration < oldest_date:
                            oldest_date = device.last_calibration
            
            if oldest_date != datetime.min:
                next_date = oldest_date + timedelta(days=saved_interval)
                _LOGGER.debug(f"Next calibration based on last: {next_date.isoformat()}")
            else:
                next_date = datetime.now() + timedelta(days=saved_interval)
                _LOGGER.debug(f"Next calibration based on now: {next_date.isoformat()}")
            
            self.nextCalibrationAll.update_value(next_date.isoformat())
        else:
            _LOGGER.debug("Calibration disabled, clearing next calibration date")
            self.nextCalibrationAll.update_value("")

    async def update_operation(self, entity: ZendureSelect, _operation: Any) -> None:
        operation = int(entity.value)
        _LOGGER.info(f"Update operation: {operation} from: {self.operation}")
        
        old_operation = self.operation
        self.operation = operation
        self.power_history.clear()
        
        # When switching FROM grid_charging to another mode, turn off all devices first
        if old_operation == SmartMode.GRID_CHARGING and operation != SmartMode.GRID_CHARGING:
            _LOGGER.info("Switching from Grid Charging to another mode - turning off all devices")
            for d in self.devices:
                await d.power_off()
            
            # Force immediate P1 update to activate new mode
            if self.p1meterEvent is not None and operation == SmartMode.MATCHING:
                _LOGGER.info("Forcing immediate P1 update to activate Smart Matching")
                p1_sensor = self.hass.states.get(self.config_entry.data.get(CONF_P1METER, "sensor.power_actual"))
                if p1_sensor and p1_sensor.state not in ("unknown", "unavailable"):
                    try:
                        p1_value = int(float(p1_sensor.state))
                        await self.powerChanged(p1_value, True)
                    except (ValueError, TypeError):
                        pass
        
        if self.p1meterEvent is not None:
            if operation != SmartMode.NONE and (len(self.devices) == 0 or all(not d.online for d in self.devices)):
                _LOGGER.warning("No devices online, not possible to start the operation")
                persistent_notification.async_create(self.hass, "No devices online, not possible to start the operation", "Zendure", "zendure_ha")
                return

            match self.operation:
                case SmartMode.NONE:
                    if len(self.devices) > 0:
                        for d in self.devices:
                            await d.power_off()

    async def check_auto_calibration(self, device: ZendureDevice) -> None:
        """Check if automatic calibration should be triggered for a device.
        
        Checks all configured conditions:
        - Auto-calibration enabled
        - Interval since last calibration
        - Current electricity price
        - Time window
        - Battery SoC level
        """
        from .const import (
            CONF_CALIB_ENABLED,
            CONF_CALIB_INTERVAL_DAYS,
            CONF_CALIB_PRICE_SENSOR,
            CONF_CALIB_PRICE_THRESHOLD,
            CONF_CALIB_SOC_MAX,
            CONF_CALIB_SOC_MIN,
            CONF_CALIB_TIME_END,
            CONF_CALIB_TIME_START,
            CalibrationDefaults,
        )
        
        # Check if auto-calibration is enabled (from config!)
        enabled = self.config_entry.data.get(CONF_CALIB_ENABLED, CalibrationDefaults.ENABLED)
        if not enabled:
            _LOGGER.debug(f"Auto-calibration DISABLED for {device.name}")
            return
        
        # Check if device is already calibrating
        if device.calibration_in_progress or device.socStatus.asInt == 1:
            _LOGGER.info(f"Auto-calibration SKIPPED for {device.name}: Already calibrating")
            return
        
        # Check interval - only calibrate if enough time has passed (from config!)
        interval_days = self.config_entry.data.get(CONF_CALIB_INTERVAL_DAYS, CalibrationDefaults.INTERVAL_DAYS)
        if device.last_calibration != datetime.min:
            days_since_last = (datetime.now() - device.last_calibration).days
            if days_since_last < interval_days:
                _LOGGER.info(
                    f"Auto-calibration SKIPPED for {device.name}: Not due yet ({days_since_last}/{interval_days} days)",
                )
                return
        else:
            _LOGGER.info(f"Auto-calibration CHECK for {device.name}: Never calibrated before")
        
        # Check time window (read from config!)
        current_hour = datetime.now().hour
        time_start = self.config_entry.data.get(CONF_CALIB_TIME_START, CalibrationDefaults.TIME_START)
        time_end = self.config_entry.data.get(CONF_CALIB_TIME_END, CalibrationDefaults.TIME_END)
        
        if time_start <= time_end:
            # Normal range (e.g. 2-6)
            in_time_window = time_start <= current_hour < time_end
        else:
            # Overnight range (e.g. 22-6)
            in_time_window = current_hour >= time_start or current_hour < time_end
        
        if not in_time_window:
            _LOGGER.info(
                f"Auto-calibration SKIPPED for {device.name}: Outside time window (current: {current_hour}h, window: {time_start}-{time_end}h)"
            )
            return
        else:
            _LOGGER.info(f"Auto-calibration CHECK for {device.name}: In time window ✅ ({time_start}-{time_end}h)")
        
        # Check battery SoC level (read from config!)
        soc = device.electricLevel.asInt
        soc_min = self.config_entry.data.get(CONF_CALIB_SOC_MIN, CalibrationDefaults.SOC_MIN)
        soc_max = self.config_entry.data.get(CONF_CALIB_SOC_MAX, CalibrationDefaults.SOC_MAX)
        
        if not (soc <= soc_min or soc >= soc_max):
            _LOGGER.info(
                f"Auto-calibration SKIPPED for {device.name}: SoC {soc}% not in range (<{soc_min}% or >{soc_max}%)"
            )
            return
        else:
            _LOGGER.info(f"Auto-calibration CHECK for {device.name}: SoC {soc}% OK ✅ (<{soc_min}% or >{soc_max}%)")
        
        # Check electricity price (read from config!)
        price_sensor = self.config_entry.data.get(CONF_CALIB_PRICE_SENSOR, "")
        if price_sensor and price_sensor != "":
            try:
                price_state = self.hass.states.get(price_sensor)
                if price_state and price_state.state not in ("unavailable", "unknown"):
                    current_price = float(price_state.state)
                    price_threshold = self.config_entry.data.get(CONF_CALIB_PRICE_THRESHOLD, CalibrationDefaults.PRICE_THRESHOLD)
                    
                    if current_price > price_threshold:
                        _LOGGER.debug(
                            "Calibration for %s: Price %.2f ct/kWh exceeds threshold %.2f ct/kWh",
                            device.name,
                            current_price,
                            price_threshold,
                        )
                        return
                    
                    _LOGGER.info(
                        "Calibration for %s: Price %.2f ct/kWh is below threshold %.2f ct/kWh - triggering!",
                        device.name,
                        current_price,
                        price_threshold,
                    )
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Failed to read electricity price from %s: %s", price_sensor, err)
                # Continue anyway if price sensor fails
        
        # All conditions met - trigger calibration!
        days_text = "never" if device.last_calibration == datetime.min else f"{(datetime.now() - device.last_calibration).days} days ago"
        
        _LOGGER.info(f"═══ AUTO-CALIBRATION TRIGGERED ═══")
        _LOGGER.info(f"Device: {device.name}")
        _LOGGER.info(f"  SoC: {soc}%")
        _LOGGER.info(f"  Hour: {current_hour}h (window: {time_start}-{time_end}h)")
        _LOGGER.info(f"  Last calibration: {days_text}")
        _LOGGER.info(f"  Starting calibration now...")
        
        success = await device.start_calibration(manual=False)
        
        if success:
            _LOGGER.info(f"Auto-calibration STARTED for {device.name} ✅")
        else:
            _LOGGER.error(f"Auto-calibration FAILED for {device.name} ❌")

    async def _async_update_data(self) -> None:
        _LOGGER.debug("Updating Zendure data")
        await EntityDevice.add_entities()
        
        # Update aggregate sensors (sum all devices)
        self._update_aggregate_sensors()

        def isBleDevice(device: ZendureDevice, si: bluetooth.BluetoothServiceInfoBleak) -> bool:
            for d in si.manufacturer_data.values():
                try:
                    if d is None or len(d) <= 1:
                        continue
                    sn = d.decode("utf8")[:-1]
                    if device.snNumber.endswith(sn):
                        _LOGGER.info(f"Found Zendure Bluetooth device: {si}")
                        device.attr_device_info["connections"] = {("bluetooth", str(si.address))}
                        return True
                except Exception:  # noqa: S112
                    continue
            return False

        for device in self.devices:
            if isinstance(device, ZendureLegacy) and device.bleMac is None:
                for si in bluetooth.async_discovered_service_info(self.hass, False):
                    if isBleDevice(device, si):
                        break

            _LOGGER.debug(f"Update device: {device.name} ({device.deviceId})")
            await device.dataRefresh(self.update_count)
            device.setStatus()
            
            # Check if auto-calibration should be triggered
            await self.check_auto_calibration(device)
        
        self.update_count += 1

        # Manually update the timer
        if self.hass and self.hass.loop.is_running():
            self._schedule_refresh()

    def update_p1meter(self, p1meter: str | None) -> None:
        """Update the P1 meter sensor."""
        _LOGGER.info(f"Updating P1 meter to: {p1meter}")  # Changed to INFO!
        
        # Cancel old event tracker
        if self.p1meterEvent:
            self.p1meterEvent()
            self.p1meterEvent = None
        
        # Cancel old polling
        if hasattr(self, 'p1_polling_cancel') and self.p1_polling_cancel:
            self.p1_polling_cancel()
            self.p1_polling_cancel = None
        
        if p1meter:
            # Try event-based first (efficient)
            try:
                self.p1meterEvent = async_track_state_change_event(self.hass, [p1meter], self._p1_changed)
                _LOGGER.info(f"P1 meter event tracker registered for {p1meter}")
            except Exception as e:
                _LOGGER.error(f"Failed to register P1 event tracker: {e}")
            
            # FALLBACK: Polling every 10 seconds (always works!)
            from homeassistant.helpers.event import async_track_time_interval
            
            async def _p1_poll(_now):
                """Poll P1 sensor value every 10 seconds."""
                state = self.hass.states.get(p1meter)
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        # Simulate state change event
                        from homeassistant.core import Event, EventStateChangedData
                        event_data = EventStateChangedData(
                            entity_id=p1meter,
                            old_state=None,
                            new_state=state
                        )
                        fake_event = Event(
                            "state_changed",
                            event_data,
                        )
                        await self._p1_changed(fake_event)
                    except Exception as e:
                        _LOGGER.error(f"P1 polling error: {e}")
            
            self.p1_polling_cancel = async_track_time_interval(
                self.hass,
                _p1_poll,
                timedelta(seconds=10)
            )
            _LOGGER.info(f"P1 meter polling started (every 10s) for {p1meter}")
        else:
            _LOGGER.warning("No P1 meter configured!")

    def writeSimulation(self, time: datetime, p1: int) -> None:
        if Path("simulation.csv").exists() is False:
            with Path("simulation.csv").open("w") as f:
                f.write(
                    "Time;P1;Operation;Battery;Solar;Home;--;"
                    + ";".join(
                        [
                            f"bat;Prod;Home;{
                                json.dumps(
                                    DeviceSettings(
                                        d.name,
                                        d.fuseGrp.name,
                                        d.limitCharge,
                                        d.limitDischarge,
                                        d.maxSolar,
                                        d.kWh,
                                        d.socSet.asNumber,
                                        d.minSoc.asNumber,
                                    ),
                                    default=vars,
                                )
                            }"
                            for d in self.devices
                        ]
                    )
                    + "\n"
                )

        with Path("simulation.csv").open("a") as f:
            data = ""
            tbattery = 0
            tsolar = 0
            thome = 0

            for d in self.devices:
                tbattery += (pwr_battery := d.batteryOutput.asInt - d.batteryInput.asInt)
                tsolar += (pwr_solar := d.solarInput.asInt)
                thome += (pwr_home := d.homeOutput.asInt - d.homeInput.asInt)
                data += f";{pwr_battery};{pwr_solar};{pwr_home};{d.electricLevel.asInt}"

            f.write(f"{time};{p1};{self.operation};{tbattery};{tsolar};{thome};" + data + "\n")

    @callback
    async def _p1_changed(self, event: Event[EventStateChangedData]) -> None:
        # update new entities
        await EntityDevice.add_entities()

        # exit if there is nothing to do
        if not self.hass.is_running or (new_state := event.data["new_state"]) is None:
            return

        try:  # convert the state to a float
            p1_raw = float(new_state.state)
        except ValueError:
            return

        # Get unit of measurement and convert to Watts if necessary
        unit = new_state.attributes.get("unit_of_measurement", "W")
        
        # Log the unit once for debugging
        if not self.p1_unit_logged:
            _LOGGER.info("P1 meter unit detected: %s (sensor: %s)", unit, new_state.entity_id)
            self.p1_unit_logged = True
        
        # Convert to Watts based on unit
        if unit in ("kW", "kilowatt", "kilowatts"):
            p1 = int(p1_raw * 1000)  # Convert kW to W
            _LOGGER.debug("Converted P1 from %.3f kW to %d W", p1_raw, p1)
        elif unit in ("W", "watt", "watts", ""):
            p1 = int(p1_raw)  # Already in Watts
        else:
            _LOGGER.warning("Unknown P1 meter unit '%s', assuming Watts. Please check your P1 sensor configuration.", unit)
            p1 = int(p1_raw)

        # Get time & update simulation
        time = datetime.now()
        if ZendureManager.simulation:
            self.writeSimulation(time, p1)

        # Check for emergency response (very large changes >2kW)
        # This bypasses all delays for immediate response
        p1_change = abs(p1 - (self.p1_history[-1] if self.p1_history else p1))
        is_emergency = p1_change > SmartMode.VERY_LARGE_CHANGE_THRESHOLD
        
        # Check for large change (>1kW) - use faster response
        is_large_change = p1_change > SmartMode.LARGE_CHANGE_THRESHOLD
        
        # Check for fast delay (skip if emergency)
        if not is_emergency and time < self.zero_fast:
            self.p1_history.append(p1)
            return

        # calculate the standard deviation
        if len(self.p1_history) > 1:
            avg = int(sum(self.p1_history) / len(self.p1_history))
            stddev = SmartMode.Threshold * max(SmartMode.MAX_STDDEV_THRESHOLD, sqrt(sum([pow(i - avg, 2) for i in self.p1_history]) / len(self.p1_history)))
            if isFast := abs(p1 - avg) > stddev or abs(p1 - self.p1_history[0]) > stddev:
                self.p1_history.clear()
        else:
            isFast = False
        self.p1_history.append(p1)

        # Determine update urgency
        # Emergency: >2kW change -> immediate response (0.3s)
        # Large: >1kW change -> fast response (1.0s)
        # Normal: standard deviation -> fast response (1.0s)
        # Otherwise: normal response (4.0s)
        if is_emergency:
            update_interval = SmartMode.TIMEEMERGENCY
            isFast = True
            _LOGGER.warning(f"P1 EMERGENCY: {p1_change}W change detected (P1={p1}W) - immediate response!")
        elif is_large_change or isFast:
            update_interval = SmartMode.TIMEFAST
            isFast = True
            _LOGGER.info(f"P1 LARGE CHANGE: {p1_change}W change detected (P1={p1}W) - fast response")
        else:
            update_interval = SmartMode.TIMEZERO
            isFast = False

        # check minimal time between updates
        if is_emergency or is_large_change or isFast or time > self.zero_next:
            try:
                self.zero_next = time + timedelta(seconds=SmartMode.TIMEZERO)
                self.zero_fast = time + timedelta(seconds=update_interval)
                await self.powerChanged(p1, isFast)
            except Exception as err:
                _LOGGER.error(err)
                _LOGGER.error(traceback.format_exc())

    async def powerChanged(self, p1: int, isFast: bool) -> None:
        # get the current power
        availEnergy = 0
        pwr_bypass = 0
        pwr_home = 0
        pwr_produced = 0

        devices: list[ZendureDevice] = []
        for d in self.devices:
            if await d.power_get():
                availEnergy += d.availableKwh.asNumber
                pwr_bypass += -d.pwr_home if d.state == DeviceState.SOCFULL else 0
                pwr_home += d.pwr_home
                pwr_produced += d.pwr_produced
                devices.append(d)
        
        # Update aggregate sensors BEFORE calculating setpoint
        # This ensures totalHomeOutput has the latest values
        self._update_aggregate_sensors()

        # SPECIAL CASE: Grid Charging Mode ignores P1 meter completely!
        if self.operation == SmartMode.GRID_CHARGING:
            # Use grid_charge_power as TOTAL limit for all devices
            total_grid_power = self.config_entry.data.get(CONF_GRID_CHARGE_POWER, GridChargingDefaults.POWER)
            
            # Update sensors
            self.power.update_value(pwr_home + pwr_produced)
            self.availableKwh.update_value(availEnergy)
            
            # Distribute total power across non-full ONLINE devices
            # Include all devices that are not FULL, even if they have no solar (like SolarFlow 2400 without panels)
            non_full_devices = [d for d in devices if d.state != DeviceState.SOCFULL and d.online]
            
            # Update DEBUG sensors (also for Grid Charging)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.debugP1Sensor.update_value(f"P1={p1}W (Grid Charging Mode) @ {timestamp}")
            
            if non_full_devices:
                # Distribute evenly (simple approach)
                power_per_device = total_grid_power // len(non_full_devices)
                
                # Update DEBUG sensor
                self.debugGridCharging.update_value(f"{total_grid_power}W → {len(non_full_devices)} Geräte ({power_per_device}W each) @ {timestamp}")
                
                _LOGGER.info(f"═══ GRID CHARGING MODE ═══")
                _LOGGER.info(f"Total Power: {total_grid_power}W | Non-full devices: {len(non_full_devices)} | Per device: {power_per_device}W")
                _LOGGER.info(f"Ignoring P1 meter (currently: {p1}W)")
                
                # Iterate over non_full_devices (not all devices!)
                for device in non_full_devices:
                    _LOGGER.info(f"  → {device.name}: Charging with {power_per_device}W (SoC: {device.electricLevel.asInt}%, Online: {device.online})")
                    # Force=True to skip delta check (devices might already charge from panels or have no solar)
                    # All devices now support force parameter
                    await device.power_charge(-power_per_device, force=True)
                
                # Turn off FULL or OFFLINE devices
                for device in devices:
                    if device not in non_full_devices:
                        if device.state == DeviceState.SOCFULL:
                            _LOGGER.info(f"  → {device.name}: FULL (SoC: {device.electricLevel.asInt}%) - skipping")
                        elif not device.online:
                            _LOGGER.info(f"  → {device.name}: OFFLINE - skipping")
                        await device.power_off()
            else:
                _LOGGER.info(f"═══ GRID CHARGING MODE ═══")
                _LOGGER.info(f"All {len(devices)} devices are FULL or OFFLINE - stopping grid charging")
                self.debugGridCharging.update_value(f"Keine Geräte verfügbar (alle voll/offline) @ {timestamp}")
                for device in devices:
                    await device.power_off()
            
            return  # DONE - don't process P1 meter!
        
        # Get the setpoint (only for non-grid-charging modes)
        # Use totalHomeOutput sensor value (NETTO output: output - input from all devices)
        # This is updated in _update_aggregate_sensors() which calculates NETTO power
        # 
        # P1 SENSOR INTERPRETATION (user-defined, e.g. sensor.gplugd_z_pi):
        # - Positive P1 = Import from grid (need to discharge more to compensate)
        # - Negative P1 = Export to grid (need to discharge less or charge)
        # 
        # Setpoint calculation with target export:
        # pwr_setpoint = total NETTO discharge needed to achieve target export (default: 50W)
        # If totalHomeOutput = 1465W (netto output) and p1 = 263W (import),
        # then setpoint = 1465 + 263 - 50 = 1678W (to achieve 50W export, not 0W)
        # 
        # IMPORTANT: totalHomeOutput is now NETTO (output - input), not raw output!
        total_home_output = int(self.totalHomeOutput.asNumber) if hasattr(self, 'totalHomeOutput') else pwr_home
        target_export = self.config_entry.data.get(CONF_TARGET_EXPORT, SmartMatchingDefaults.TARGET_EXPORT)
        pwr_setpoint = total_home_output + p1 - target_export  # Subtract target export to achieve small export instead of 0
        if issurplus := self.operation == SmartMode.MATCHING and pwr_setpoint > 0 and abs(pwr_bypass) > pwr_setpoint:
            pwr_setpoint += pwr_bypass
        elif pwr_setpoint < 0 and pwr_setpoint < pwr_produced + pwr_bypass:
            pwr_setpoint += pwr_produced
        
        # For Smart Matching: setpoint is the TOTAL discharge needed
        # But we need to calculate ADDITIONAL discharge needed
        # If devices already discharge pwr_home, we need (setpoint - pwr_home) more
        # But actually, setpoint already includes pwr_home, so we just need setpoint total
        # The issue is: powerDischarge receives setpoint but devices might already be discharging
        # So we need to ensure powerDischarge sets the TOTAL, not ADDITIONAL

        # Update the power entities
        self.power.update_value(pwr_home + pwr_produced)
        self.availableKwh.update_value(availEnergy)
        self.pwr_update += 1
        self.pwr_total = 0
        self.pwr_count = 0
        self.pwr_avg = 0

        # reset history on fast change and discharging
        if len(self.power_history) > 1:
            avg = int(sum(self.power_history) / len(self.power_history))
            if avg > 0 and pwr_setpoint < 0:
                self.power_history.clear()
            else:
                stddev = SmartMode.ThresholdAvg * max(SmartMode.MAX_STDDEV_THRESHOLD_AVG, sqrt(sum([pow(i - avg, 2) for i in self.power_history]) / len(self.power_history)))
                if abs(pwr_setpoint - avg) > stddev or abs(pwr_setpoint - self.power_history[0]) > stddev:
                    self.power_history.clear()

        self.power_history.append(pwr_setpoint)
        p1_average = sum(self.power_history) // len(self.power_history)

        # Determine target mode to detect mode changes
        current_mode = "idle"
        if pwr_setpoint > SmartMode.IGNORE_DELTA:
            current_mode = "discharging"
        elif pwr_setpoint < -SmartMode.IGNORE_DELTA:
            current_mode = "charging"

        # Hysteresis: prevent rapid mode switching
        time = datetime.now()  # Get current time for hysteresis check
        time_since_last_change = (time - self.last_mode_change).total_seconds()
        if current_mode != self.last_mode and time_since_last_change < SmartMode.MIN_SWITCH_INTERVAL:
            _LOGGER.info(
                "Preventing mode switch from %s to %s (only %d seconds since last change, minimum is %d)",
                self.last_mode,
                current_mode,
                int(time_since_last_change),
                SmartMode.MIN_SWITCH_INTERVAL,
            )
            # Stay in current mode - don't update devices
            return

        # Track mode changes
        if current_mode != self.last_mode:
            _LOGGER.info("Mode changed from %s to %s", self.last_mode, current_mode)
            self.last_mode = current_mode
            self.last_mode_change = time

        # Update DEBUG sensor to show P1 activity
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debugP1Sensor.update_value(f"P1={p1}W setpoint={pwr_setpoint}W @ {timestamp}")
        
        # Calculate what we need: setpoint is TOTAL discharge needed
        # If devices already discharge total_home_output, we need (setpoint - total_home_output) more
        # But actually, setpoint already accounts for this, so we just need to reach setpoint total
        additional_needed = pwr_setpoint - total_home_output if pwr_setpoint > total_home_output else 0
        
        # Update power distribution.
        _LOGGER.info(f"P1 ======> p1:{p1}W isFast:{isFast}, setpoint:{pwr_setpoint}W, current_total:{total_home_output}W, additional_needed:{additional_needed}W, produced:{pwr_produced}W")
        print(f"[ZENDURE] P1={p1}W setpoint={pwr_setpoint}W current={total_home_output}W additional={additional_needed}W")
        match self.operation:
            case SmartMode.MATCHING:
                if pwr_setpoint >= 0:
                    await self.powerDischarge(devices, p1_average, pwr_setpoint)
                elif pwr_setpoint <= 0 and p1_average > 0:
                    await self.powerDischarge(devices, 0, 0)
                elif pwr_setpoint <= 0:
                    await self.powerCharge(devices, p1_average, pwr_setpoint, issurplus)

            case SmartMode.MATCHING_DISCHARGE:
                await self.powerDischarge(devices, p1_average, max(0, pwr_setpoint))

            case SmartMode.MATCHING_CHARGE:
                if pwr_setpoint > -SmartMode.STARTWATT and pwr_setpoint < -pwr_produced:
                    await self.powerDischarge(devices, p1_average, pwr_setpoint)
                else:
                    await self.powerCharge(devices, p1_average, min(0, pwr_setpoint), issurplus)

            case SmartMode.MANUAL:
                if (setpoint := int(self.manualpower.asNumber)) > 0:
                    await self.powerDischarge(devices, setpoint, setpoint)
                else:
                    await self.powerCharge(devices, setpoint, setpoint, True)

    async def powerCharge(self, devices: list[ZendureDevice], average: int, setpoint: int, issurplus: bool) -> None:
        def sortCharge(d: ZendureDevice) -> int:
            if d.state == DeviceState.SOCFULL:
                return 0
            d.pwr_load = d.limitCharge // 4
            if (d.homeOutput.asInt > 0 or d.batteryInput.asInt > 0) and d.state != DeviceState.SOCFULL:
                self.pwr_count += 1
                self.pwr_total += d.fuseGrp.chargePower(d, self.pwr_update)
            return d.electricLevel.asInt - (5 if d.batteryInput.asInt > SmartMode.STARTWATT else 0)

        devices.sort(key=sortCharge, reverse=False)
        _LOGGER.info(f"powerCharge => setpoint {setpoint} cnt {self.pwr_count}")

        # distribute the power over the devices
        isFirst = True
        setpoint = max(setpoint, self.pwr_total)
        for d in devices:
            if d.state == DeviceState.SOCFULL:
                await d.power_discharge(0)
            else:
                if (d.homeOutput.asInt > 0 or d.batteryInput.asInt > 0) and setpoint < 0:
                    if self.pwr_count > 1 and setpoint < d.pwr_load and self.pwr_total < 0:
                        pct = min(1, max(0.125, setpoint / self.pwr_total))
                        pct = pct if pct < 0.25 or pct > 0.8 else min(0.9, pct + min(0.2, self.pwr_count * 0.075))
                        pwr = max(int(pct * d.maxPower), setpoint)
                        self.pwr_count -= 1
                        self.pwr_total -= d.maxPower
                    else:
                        pwr = setpoint

                    if issurplus:
                        pwr = await d.power_discharge(pwr) if pwr > 0 else -d.homeOutput.asInt + await d.power_charge(pwr)
                    elif d.pwr_produced == 0:
                        pwr = await d.power_charge(pwr)
                    elif d.pwr_produced < pwr:
                        pwr = d.pwr_produced + await d.power_discharge(pwr - d.pwr_produced)
                    else:
                        pwr = d.pwr_produced + await d.power_charge(pwr - d.pwr_produced)

                    setpoint = min(0, setpoint - pwr)

                elif average < d.pwr_load or isFirst:
                    await d.power_discharge(SmartMode.STARTWATT) if d.pwr_produced < -SmartMode.STARTWATT else await d.power_charge(-SmartMode.STARTWATT)
                else:
                    await d.power_discharge(0 if issurplus else -d.pwr_produced)
                average -= d.pwr_load
                isFirst = False

        # Distribution done, remaining power should be zero
        if setpoint != 0:
            _LOGGER.info(f"powerDistribution => left {setpoint}W")

    async def powerDischarge(self, devices: list[ZendureDevice], average: int, setpoint: int) -> None:
        def sortDischarge(d: ZendureDevice) -> int:
            if d.state == DeviceState.SOCEMPTY:
                return 101
            d.pwr_load = d.limitDischarge // 4
            # Count ALL online devices that can discharge (not just those currently discharging)
            if d.online and d.state != DeviceState.SOCEMPTY and d.state != DeviceState.SOCFULL:
                self.pwr_count += 1
                # Use limitDischarge as available capacity (not just current output)
                self.pwr_total += d.limitDischarge
            return d.electricLevel.asInt + (5 if d.homeOutput.asInt > SmartMode.STARTWATT else 0)

        devices.sort(key=sortDischarge, reverse=True)
        
        # Calculate current total discharge BEFORE distribution
        current_total_discharge = sum(d.homeOutput.asInt for d in devices if d.homeOutput.asInt > 0)
        
        # For large setpoints (>1kW), prioritize maximum discharge for faster response
        # This helps when Wärmepumpe/Backofen suddenly starts
        is_large_setpoint = setpoint > SmartMode.LARGE_CHANGE_THRESHOLD
        
        _LOGGER.info(f"powerDischarge => setpoint {setpoint}W, current total: {current_total_discharge}W, available {self.pwr_total}W, devices {self.pwr_count}, large_setpoint={is_large_setpoint}")

        # distribute the power over the devices
        isFirst = True
        remaining_setpoint = setpoint  # Track remaining setpoint
        
        for d in devices:
            if d.state == DeviceState.SOCEMPTY:
                await d.power_discharge(-d.pwr_produced)
            elif d.online and d.state != DeviceState.SOCFULL and remaining_setpoint > 0:
                # For large setpoints, prioritize maximum discharge per device for faster response
                if is_large_setpoint and self.pwr_count > 1:
                    # Give each device its maximum capacity first, then distribute remainder
                    # This ensures all devices ramp up quickly
                    if remaining_setpoint > d.limitDischarge:
                        # Still need more - give this device its max
                        pwr = d.limitDischarge
                    else:
                        # Remaining setpoint is less than this device's capacity
                        pwr = remaining_setpoint
                    self.pwr_count -= 1
                    self.pwr_total -= d.limitDischarge
                elif self.pwr_count > 1 and self.pwr_total > 0:
                    # Normal proportional distribution
                    pct = d.limitDischarge / self.pwr_total if self.pwr_total > 0 else 1.0 / self.pwr_count
                    pwr = min(int(remaining_setpoint * pct), d.limitDischarge, remaining_setpoint)
                    self.pwr_count -= 1
                    self.pwr_total -= d.limitDischarge
                else:
                    # Single device or last device - give it all remaining power
                    pwr = min(remaining_setpoint, d.limitDischarge)

                if pwr > 0:
                    # pwr is the TOTAL discharge we want from this device
                    current_discharge = d.homeOutput.asInt if d.homeOutput.asInt > 0 else 0
                    _LOGGER.info(f"  → {d.name}: Setting discharge to {pwr}W (currently: {current_discharge}W, limit: {d.limitDischarge}W, SoC: {d.electricLevel.asInt}%)")
                    actual_pwr = await d.power_discharge(pwr)
                    # Reduce remaining_setpoint by what we actually got (not just additional)
                    # This ensures we track total discharge correctly
                    remaining_setpoint = max(0, remaining_setpoint - actual_pwr)
                    _LOGGER.info(f"  → {d.name}: Actually discharging {actual_pwr}W (remaining setpoint: {remaining_setpoint}W)")
                else:
                    # If pwr <= 0, turn off this device
                    await d.power_discharge(0)
            elif average > d.pwr_load or isFirst:
                await d.power_discharge(SmartMode.STARTWATT)
            else:
                await d.power_discharge(0)
            average -= d.pwr_load
            isFirst = False

        # Distribution done, remaining power should be zero
        if remaining_setpoint != 0:
            _LOGGER.warning(f"powerDistribution => left {remaining_setpoint}W (devices may be at limit or offline)")
