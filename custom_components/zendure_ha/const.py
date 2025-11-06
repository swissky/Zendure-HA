"""Constants for Zendure."""

from datetime import timedelta
from enum import Enum

DOMAIN = "zendure_ha"

CONF_APPTOKEN = "token"
CONF_P1METER = "p1meter"
CONF_PRICE = "price"
CONF_MQTTLOG = "mqttlog"
CONF_MQTTLOCAL = "mqttlocal"
CONF_MQTTSERVER = "mqttserver"
CONF_SIM = "simulation"
CONF_MQTTPORT = "mqttport"
CONF_MQTTUSER = "mqttuser"
CONF_MQTTPSW = "mqttpsw"
CONF_WIFISSID = "wifissid"
CONF_WIFIPSW = "wifipsw"
CONF_GRID_CHARGE_POWER = "grid_charge_power"
CONF_TARGET_EXPORT = "target_export"  # Target export power for Smart Matching (W)

# Calibration configuration
CONF_CALIB_ENABLED = "calib_enabled"
CONF_CALIB_MODE = "calib_mode"  # "all_together" or "individual"
CONF_CALIB_PRICE_SENSOR = "calib_price_sensor"
CONF_CALIB_PRICE_THRESHOLD = "calib_price_threshold"
CONF_CALIB_INTERVAL_DAYS = "calib_interval_days"
CONF_CALIB_TIME_START = "calib_time_start"
CONF_CALIB_TIME_END = "calib_time_end"
CONF_CALIB_SOC_MIN = "calib_soc_min"
CONF_CALIB_SOC_MAX = "calib_soc_max"

CONF_HAKEY = "C*dafwArEOXK"


class AcMode:
    INPUT = 1
    OUTPUT = 2


class DeviceState(Enum):
    OFFLINE = 0
    SOCEMPTY = 1
    SOCFULL = 2
    INACTIVE = 3
    STARTING = 4
    ACTIVE = 5


class ManagerState(Enum):
    IDLE = 0
    CHARGING = 1
    DISCHARGING = 2
    WAITING = 3


class SmartMode:
    NONE = 0
    MANUAL = 1
    MATCHING = 2
    MATCHING_DISCHARGE = 3
    MATCHING_CHARGE = 4
    GRID_CHARGING = 5  # New: Charge from grid (for off-peak hours)
    FAST_UPDATE = 100
    MIN_POWER = 50
    START_POWER = 100
    
    # Timing constants (in seconds)
    TIMEFAST = 2.2  # Fast update interval after significant change
    TIMEZERO = 4  # Normal update interval
    TIMEIDLE = 10  # Idle time
    TIMERESET = 150  # Reset time
    MIN_SWITCH_INTERVAL = 30  # Minimum seconds between mode changes to prevent oscillation
    
    # Standard deviation thresholds for detecting significant changes
    Threshold = 3.5  # Multiplier for P1 meter stddev calculation
    ThresholdAvg = 3.5  # Multiplier for power average stddev calculation
    MAX_STDDEV_THRESHOLD = 15  # Minimum stddev value for P1 changes (watts)
    MAX_STDDEV_THRESHOLD_AVG = 20  # Minimum stddev value for power average (watts)
    
    P1_MIN_UPDATE = timedelta(milliseconds=400)
    
    # Power delta thresholds to prevent rapid switching
    IGNORE_DELTA = 10  # Minimum power change (W) to trigger device update (was 3)
    POWER_TOLERANCE = 5  # Device-level power tolerance (W) before updating (was 1)
    
    ZENSDK = 2
    CONNECTED = 10
    SOCMIN_OPTIMAL = 22
    SOCFULL = 1
    SOCEMPTY = 2
    KWHSTEP = 0.5
    STARTWATT = 40
    PEAKWATT = 500


class CalibrationDefaults:
    """Default values for battery calibration automation."""
    
    # Default settings
    ENABLED = False  # Auto-calibration disabled by default
    MODE = "all_together"  # Calibrate all devices together
    INTERVAL_DAYS = 30  # Calibrate once per month
    PRICE_THRESHOLD = 15.0  # cents/kWh - only calibrate when price below this
    TIME_START = 2  # Start time: 02:00 (night tariff)
    TIME_END = 6  # End time: 06:00 (before sunrise)
    SOC_MIN = 15  # Only calibrate if battery below 15% (deep cycle)
    SOC_MAX = 85  # Or above 85% (full cycle)
    
    # Minimum/Maximum configurable values
    MIN_INTERVAL_DAYS = 7  # At least weekly
    MAX_INTERVAL_DAYS = 365  # At most yearly
    MIN_PRICE = 0.0  # Minimum price threshold
    MAX_PRICE = 50.0  # Maximum price threshold (cents/kWh)


class GridChargingDefaults:
    """Default values for grid charging mode."""
    POWER = 800  # Default charging power from grid (W)


class SmartMatchingDefaults:
    """Default values for Smart Matching mode."""
    TARGET_EXPORT = 50  # Default target export power (W) - aim for 50W export instead of 0W
