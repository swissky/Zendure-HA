"""Module for the Hyper2000 device integration in Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.zendure_ha.device import ZendureLegacy
from custom_components.zendure_ha.sensor import ZendureRestoreSensor, ZendureSensor

_LOGGER = logging.getLogger(__name__)


class Hyper2000(ZendureLegacy):
    def __init__(self, hass: HomeAssistant, deviceId: str, prodName: str, definition: Any) -> None:
        """Initialise Hyper2000."""
        super().__init__(hass, deviceId, definition["deviceName"], prodName, definition)
        self.limitDischarge = 1200
        self.limitCharge = -1200
        self.maxSolar = -1600
        self.offGrid = ZendureSensor(self, "gridOffPower", None, "W", "power", "measurement")
        self.aggrOffGrid = ZendureRestoreSensor(self, "aggrGridOffPowerTotal", None, "kWh", "energy", "total_increasing", 2)

    @property
    def pwr_offgrid(self) -> int:
        """Get the offgrid power."""
        return self.offGrid.asInt

    async def power_charge(self, power: int, force: bool = False) -> int:
        """Set charge power.
        
        Args:
            power: Power to charge (negative value)
            force: Skip delta check (for grid charging)
        """
        if not force and abs(power - self.pwr_home) <= 1:
            _LOGGER.info(f"Power charge {self.name} => no action [power {power}, delta too small]")
            self.deviceAction.update_value("Standby (kein Delta)")
            return power

        _LOGGER.info(f"Power charge {self.name} => {power} (Setting acMode=1, inputLimit={abs(power)}, force={force})")
        
        # Update debug sensors
        self.deviceAction.update_value(f"Laden vom Netz")
        self.lastPowerCommand.update_value(power)
        
        # Hyper 2000 needs DIRECT property setting for reliable grid charging
        # Set acMode=1 (AC Input) and inputLimit directly
        self.mqttPublish(
            self.topic_write,
            {
                "properties": {
                    "acMode": 1,  # AC-Eingangsmodus
                    "inputLimit": abs(power),  # Positive value
                    "smartMode": 1  # Enable smart mode
                }
            }
        )
        
        return power

    async def power_discharge(self, power: int) -> int:
        """Set discharge power."""
        if abs(power - self.pwr_home) <= 1:
            _LOGGER.info(f"Power discharge {self.name} => no action [power {power}]")
            self.deviceAction.update_value("Standby (kein Delta)")
            return power

        _LOGGER.info(f"Power discharge {self.name} => {power} (Setting acMode=2, outputLimit={power})")
        
        # Update debug sensors
        if power > 0:
            self.deviceAction.update_value(f"Entladen ans Haus")
            self.lastPowerCommand.update_value(power)
        else:
            self.deviceAction.update_value("Standby")
            self.lastPowerCommand.update_value(0)
        
        # Set acMode=2 (AC Output) and outputLimit directly
        self.mqttPublish(
            self.topic_write,
            {
                "properties": {
                    "acMode": 2,  # AC-Ausgangsmodus
                    "outputLimit": power,  # Discharge power
                    "smartMode": 1 if power > 0 else 0  # Enable only if power > 0
                }
            }
        )
        
        return power

    async def power_off(self) -> None:
        """Set the power off."""
        _LOGGER.info(f"Power off {self.name} (Setting smartMode=0, limits=0)")
        
        # Update debug sensors
        self.deviceAction.update_value("Aus")
        self.lastPowerCommand.update_value(0)
        
        # Turn off both input and output
        self.mqttPublish(
            self.topic_write,
            {
                "properties": {
                    "smartMode": 0,
                    "acMode": 2,  # Default to output mode
                    "inputLimit": 0,
                    "outputLimit": 0
                }
            }
        )
