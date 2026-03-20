"""Constants for CFL Commute integration."""

from homeassistant.const import Platform

DOMAIN = "cfl_commute"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_TIME_WINDOW = 60
DEFAULT_NUM_TRAINS = 3
DEFAULT_MINOR_THRESHOLD = 3
DEFAULT_MAJOR_THRESHOLD = 10
DEFAULT_SEVERE_THRESHOLD = 15
DEFAULT_NIGHT_UPDATES = False

CONF_API_KEY = "api_key"
CONF_ORIGIN = "origin"
CONF_DESTINATION = "destination"
CONF_COMMUTE_NAME = "commute_name"
CONF_TIME_WINDOW = "time_window"
CONF_NUM_TRAINS = "num_trains"
CONF_MINOR_THRESHOLD = "minor_threshold"
CONF_MAJOR_THRESHOLD = "major_threshold"
CONF_SEVERE_THRESHOLD = "severe_threshold"
CONF_NIGHT_UPDATES = "night_updates"
CONF_ADD_RETURN_JOURNEY = "add_return_journey"

STATUS_NORMAL = "Normal"
STATUS_MINOR = "Minor Delays"
STATUS_MAJOR = "Major Delays"
STATUS_SEVERE = "Severe Disruption"
STATUS_CRITICAL = "Critical"

TRAIN_ON_TIME = "On Time"
TRAIN_DELAYED = "Delayed"
TRAIN_CANCELLED = "Cancelled"
TRAIN_EXPECTED = "Expected"
TRAIN_NO_TRAIN = "No trains"

UPDATE_INTERVAL_PEAK = 120
UPDATE_INTERVAL_OFFPEAK = 300
UPDATE_INTERVAL_NIGHT = 900

# Smart interval configuration
PEAK_HOURS = [(6, 10), (16, 20)]  # 6-10am, 4-8pm
NIGHT_HOURS = (23, 5)  # 11pm-5am
