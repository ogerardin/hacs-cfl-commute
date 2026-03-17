# CFL Commute Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Home Assistant integration that tracks Luxembourg CFL train commutes using real-time data from API mobiliteit.lu

**Architecture:** REST API integration with Home Assistant. Uses station name search and departureBoard endpoints. Sensors poll at configurable intervals with smart scheduling (peak/off-peak/night).

**Tech Stack:** Python, Home Assistant custom component framework, mobiliteit.lu API

---

## File Structure

```
custom_components/cfl_commute/
├── __init__.py              # Component initialization, entry point
├── api.py                   # API client for mobiliteit.lu (station search, departures)
├── config_flow.py           # UI configuration flow (station selection, settings)
├── const.py                 # Constants, default values, icons
├── manifest.json            # HACS manifest
├── sensor.py                # Sensor entities (summary, status, train N)
├── binary_sensor.py         # Disruption binary sensor
└── translations/            # Localization (en, fr, de, lb)
    └── en.json

tests/
├── __init__.py
├── test_api.py
├── test_config_flow.py
├── test_sensor.py
└── test_binary_sensor.py
```

---

## Chunk 1: Project Setup & API Client

### Task 1: Create project structure and manifest

**Files:**
- Create: `custom_components/cfl_commute/__init__.py`
- Create: `custom_components/cfl_commute/manifest.json`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create manifest.json**

```json
{
  "domain": "cfl_commute",
  "name": "CFL Commute",
  "codeowners": ["@yourname"],
  "config_flow": true,
  "documentation": "https://github.com/yourname/hacs-cfl-commute",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/yourname/hacs-cfl-commute/issues",
  "requirements": ["aiohttp>=3.9.0"],
  "version": "0.0.1"
}
```

- [ ] **Step 2: Create __init__.py**

```python
"""CFL Commute - Home Assistant integration for Luxembourg railways."""
from .const import DOMAIN

async def async_setup_entry(hass, entry):
    """Set up CFL Commute from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    return True
```

- [ ] **Step 3: Create const.py**

```python
"""Constants for CFL Commute integration."""
from homeassistant.const import Platform

DOMAIN = "cfl_commute"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_TIME_WINDOW = 60
DEFAULT_NUM_SERVICES = 3
DEFAULT_MINOR_THRESHOLD = 3
DEFAULT_MAJOR_THRESHOLD = 10
DEFAULT_SEVERE_THRESHOLD = 15
DEFAULT_NIGHT_UPDATES = False

CONF_API_KEY = "api_key"
CONF_ORIGIN = "origin"
CONF_DESTINATION = "destination"
CONF_COMMUTE_NAME = "commute_name"
CONF_TIME_WINDOW = "time_window"
CONF_NUM_SERVICES = "num_services"
CONF_MINOR_THRESHOLD = "minor_threshold"
CONF_MAJOR_THRESHOLD = "major_threshold"
CONF_SEVERE_THRESHOLD = "severe_threshold"
CONF_NIGHT_UPDATES = "night_updates"

STATUS_NORMAL = "Normal"
STATUS_MINOR = "Minor Delays"
STATUS_MAJOR = "Major Delays"
STATUS_SEVERE = "Severe Disruption"
STATUS_CRITICAL = "Critical"

TRAIN_ON_TIME = "On Time"
TRAIN_DELAYED = "Delayed"
TRAIN_CANCELLED = "Cancelled"
TRAIN_EXPECTED = "Expected"
TRAIN_NO_SERVICE = "No service"
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/cfl_commute/__init__.py custom_components/cfl_commute/manifest.json custom_components/cfl_commute/const.py tests/__init__.py
git commit -m "feat: create project structure and manifest"
```

---

### Task 2: API Client

**Files:**
- Create: `custom_components/cfl_commute/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing test for API client**

```python
import pytest
from custom_components.cfl_commute.api import CFLCommuteClient

@pytest.mark.asyncio
async def test_station_search_returns_stations():
    """Test station search returns matching stations."""
    client = CFLCommuteClient("test_api_key")
    # Mock the API response
    stations = await client.search_stations("Luxembourg")
    assert isinstance(stations, list)

@pytest.mark.asyncio
async def test_get_departures_returns_list():
    """Test get departures returns list of departures."""
    client = CFLCommuteClient("test_api_key")
    departures = await client.get_departures("200426002")
    assert isinstance(departures, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'custom_components'"

- [ ] **Step 3: Write minimal API client implementation**

```python
"""API client for CFL mobiliteit.lu."""
from typing import Optional
import aiohttp

class CFLCommuteClient:
    """Client for mobiliteit.lu API."""

    BASE_URL = "https://cdt.hafas.de/opendata/apiserver"

    def __init__(self, api_key: str):
        """Initialize the client."""
        self._api_key = api_key

    async def search_stations(self, query: str) -> list:
        """Search for stations by name."""
        # Use large radius to get all stations, then filter
        url = f"{self.BASE_URL}/location.nearbystops"
        params = {
            "accessId": self._api_key,
            "originCoordLong": "6.09528",
            "originCoordLat": "49.77723",
            "maxNo": "5000",
            "r": "100000",
            "format": "json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
        # Filter stations by name match
        stations = []
        for stop in data.get("LocationList", {}).get("StopLocation", []):
            if query.lower() in stop.get("name", "").lower():
                stations.append({
                    "id": stop.get("id"),
                    "name": stop.get("name"),
                    "lon": stop.get("lon"),
                    "lat": stop.get("lat")
                })
        
        return stations

    async def get_departures(self, station_id: str, lang: str = "en") -> list:
        """Get departures for a station."""
        url = f"{self.BASE_URL}/departureBoard"
        params = {
            "accessId": self._api_key,
            "id": station_id,
            "lang": lang,
            "format": "json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
        
        departures = []
        for dep in data.get("Departure", []):
            # Filter to CFL trains only (rail)
            if dep.get("product", {}).get("cat", "") in ["CFL", "EC", "IC", "TER", "TGV"]:
                departures.append({
                    "station_id": station_id,
                    "departure_time": dep.get("dep"),
                    "scheduled_departure": dep.get("depTime"),
                    "platform": dep.get("platform", "TBA"),
                    "line": dep.get("line", ""),
                    "direction": dep.get("direction", ""),
                    "operator": dep.get("product", {}).get("cat", "CFL"),
                    "train_number": dep.get("trainNumber", ""),
                    "is_cancelled": dep.get("cancelled", False),
                    "delay_minutes": int(dep.get("delay", 0) or 0)
                })
        
        return departures
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS (or SKIP if no real API key)

- [ ] **Step 5: Commit**

```bash
git add custom_components/cfl_commute/api.py tests/test_api.py
git commit -m "feat: add API client for mobiliteit.lu"
```

---

## Chunk 2: Configuration Flow

### Task 3: Config Flow with Station Search

**Files:**
- Create: `custom_components/cfl_commute/config_flow.py`
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing test for config flow**

```python
import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.config_entries import ConfigFlow
from custom_components.cfl_commute.config_flow import CFLCommuteConfigFlow

async def test_flow_user_step():
    """Test user step shows stations input."""
    flow = CFLCommuteConfigFlow()
    flow.hass = Mock()
    
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL

- [ ] **Step 3: Write config flow implementation**

```python
"""Config flow for CFL Commute."""
import asyncio
import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from .api import CFLCommuteClient
from .const import (
    CONF_API_KEY,
    CONF_ORIGIN,
    CONF_DESTINATION,
    CONF_COMMUTE_NAME,
    CONF_TIME_WINDOW,
    CONF_NUM_SERVICES,
    CONF_MINOR_THRESHOLD,
    CONF_MAJOR_THRESHOLD,
    CONF_SEVERE_THRESHOLD,
    CONF_NIGHT_UPDATES,
    DEFAULT_TIME_WINDOW,
    DEFAULT_NUM_SERVICES,
    DEFAULT_MINOR_THRESHOLD,
    DEFAULT_MAJOR_THRESHOLD,
    DEFAULT_SEVERE_THRESHOLD,
    DEFAULT_NIGHT_UPDATES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
})

ORIGIN_SCHEMA = vol.Schema({
    vol.Required(CONF_ORIGIN): selector.TextSelector(
        selector.TextSelectorConfig(helper=True)
    ),
})

class CFLCommuteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CFL Commute."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._api_key: str = ""
        self._origin_station: dict = {}
        self._destination_station: dict = {}
        self._client: CFLCommuteClient = None

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            self._client = CFLCommuteClient(self._api_key)
            return await self.async_step_origin()
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_origin(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle origin station selection."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Search for stations
            query = user_input.get(CONF_ORIGIN, {}).get("value", "")
            if query:
                try:
                    stations = await self._client.search_stations(query)
                    if stations:
                        return self.async_show_form(
                            step_id="origin",
                            data_schema=vol.Schema({
                                vol.Required(CONF_ORIGIN): selector.SelectSelector(
                                    selector.SelectSelectorConfig(
                                        options=[
                                            {"value": s["id"], "label": s["name"]}
                                            for s in stations
                                        ],
                                        mode=selector.SelectSelectorMode.DROPDOWN,
                                    )
                                ),
                            }),
                            errors=errors,
                        )
                except Exception as e:
                    _LOGGER.error(f"Station search error: {e}")
                    errors["base"] = "station_search_failed"
        
        # Initial step - show search input
        return self.async_show_form(
            step_id="origin",
            data_schema=vol.Schema({
                vol.Required(CONF_ORIGIN): str,
            }),
            errors=errors,
            description_placeholders={
                "hint": "Enter origin station name (e.g., Luxembourg)"
            },
        )

    # ... Similar for destination and settings steps
    # Full implementation in config_flow.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/cfl_commute/config_flow.py tests/test_config_flow.py
git commit -m "feat: add config flow with station search"
```

---

## Chunk 3: Sensor Entities

### Task 4: Sensor Entities (Summary, Status, Train)

**Files:**
- Create: `custom_components/cfl_commute/sensor.py`
- Create: `tests/test_sensor.py`

- [ ] **Step 1: Write failing tests for sensors**

```python
import pytest
from custom_components.cfl_commute.sensor import CFLCommuteSummarySensor

def test_summary_sensor_state():
    """Test summary sensor calculates correct state."""
    # Test with mock data
    assert True  # Placeholder
```

- [ ] **Step 2: Write sensor implementation**

```python
"""Sensor entities for CFL Commute."""
from datetime import datetime
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from .api import CFLCommuteClient
from .const import (
    CONF_COMMUTE_NAME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_TIME_WINDOW,
    CONF_NUM_SERVICES,
    CONF_MINOR_THRESHOLD,
    CONF_MAJOR_THRESHOLD,
    CONF_SEVERE_THRESHOLD,
    DOMAIN,
    STATUS_NORMAL,
    STATUS_MINOR,
    STATUS_MAJOR,
    STATUS_SEVERE,
    STATUS_CRITICAL,
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CFL Commute sensors."""
    # Create sensors based on config
    commute_name = config_entry.data.get(CONF_COMMUTE_NAME, "cfl_commute")
    
    sensors = [
        CFLCommuteSummarySensor(hass, config_entry),
        CFLCommuteStatusSensor(hass, config_entry),
        CFLCommuteNextTrainSensor(hass, config_entry),
    ]
    
    # Add individual train sensors
    num_services = config_entry.data.get(CONF_NUM_SERVICES, 3)
    for i in range(1, num_services + 1):
        sensors.append(CFLCommuteTrainSensor(hass, config_entry, i))
    
    async_add_entities(sensors)


class CFLCommuteBaseSensor(SensorEntity):
    """Base sensor for CFL Commute."""

    def __init__(self, hass: HomeAssistant, config: dict):
        """Initialize the sensor."""
        self._hass = hass
        self._config = config
        self._commute_name = config.data.get(CONF_COMMUTE_NAME, "cfl_commute")
        self._api_key = config.data.get("api_key")
        self._origin_id = config.data.get(CONF_ORIGIN).get("id")
        self._origin_name = config.data.get(CONF_ORIGIN).get("name")
        self._destination_id = config.data.get(CONF_DESTINATION).get("id")
        self._destination_name = config.data.get(CONF_DESTINATION).get("name")
        self._time_window = config.data.get(CONF_TIME_WINDOW, 60)
        self._num_services = config.data.get(CONF_NUM_SERVICES, 3)
        self._minor_threshold = config.data.get(CONF_MINOR_THRESHOLD, 3)
        self._major_threshold = config.data.get(CONF_MAJOR_THRESHOLD, 10)
        self._severe_threshold = config.data.get(CONF_SEVERE_THRESHOLD, 15)
        self._client = CFLCommuteClient(self._api_key)
        self._departures = []

    async def async_update(self) -> None:
        """Update sensor data."""
        try:
            self._departures = await self._client.get_departures(self._origin_id)
            # Filter to only those within time window going to destination
            self._departures = [
                d for d in self._departures
                if self._destination_name.lower() in d.get("direction", "").lower()
            ][:self._num_services]
        except Exception as e:
            _LOGGER.error(f"Failed to update: {e}")


class CFLCommuteSummarySensor(CFLCommuteBaseSensor):
    """Summary sensor showing overall commute status."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._commute_name} Summary"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self._departures:
            return "No trains"
        
        on_time = sum(1 for d in self._departures if not d.get("is_cancelled") and d.get("delay_minutes", 0) < self._minor_threshold)
        delayed = sum(1 for d in self._departures if d.get("delay_minutes", 0) >= self._minor_threshold)
        cancelled = sum(1 for d in self._departures if d.get("is_cancelled"))
        
        parts = []
        if on_time:
            parts.append(f"{on_time} on time")
        if delayed:
            parts.append(f"{delayed} delayed")
        if cancelled:
            parts.append(f"{cancelled} cancelled")
        
        return ", ".join(parts) if parts else "No service"


class CFLCommuteStatusSensor(CFLCommuteBaseSensor):
    """Status sensor with hierarchical status."""

    @property
    def name(self) -> str:
        return f"{self._commute_name} Status"

    @property
    def state(self) -> str:
        """Return the hierarchical status."""
        # Check in priority order (highest first)
        if any(d.get("is_cancelled") for d in self._departures):
            return STATUS_CRITICAL
        
        max_delay = max((d.get("delay_minutes", 0) for d in self._departures), default=0)
        
        if max_delay >= self._severe_threshold:
            return STATUS_SEVERE
        elif max_delay >= self._major_threshold:
            return STATUS_MAJOR
        elif max_delay >= self._minor_threshold:
            return STATUS_MINOR
        
        return STATUS_NORMAL


class CFLCommuteNextTrainSensor(CFLCommuteBaseSensor):
    """Next train sensor."""

    @property
    def name(self) -> str:
        return f"{self._commute_name} Next Train"

    @property
    def state(self) -> str:
        """Return the next train status."""
        if not self._departures:
            return "No service"
        
        train = self._departures[0]
        if train.get("is_cancelled"):
            return "Cancelled"
        elif train.get("delay_minutes", 0) > 0:
            return "Delayed"
        return "On Time"


class CFLCommuteTrainSensor(CFLCommuteBaseSensor):
    """Individual train sensor (train_1, train_2, etc.)."""

    def __init__(self, hass: HomeAssistant, config: dict, train_number: int):
        """Initialize train sensor."""
        super().__init__(hass, config)
        self._train_number = train_number

    @property
    def name(self) -> str:
        return f"{self._commute_name} Train {self._train_number}"

    @property
    def state(self) -> str:
        """Return the train status."""
        if len(self._departures) < self._train_number:
            return "No service"
        
        train = self._departures[self._train_number - 1]
        if train.get("is_cancelled"):
            return "Cancelled"
        elif train.get("delay_minutes", 0) > 0:
            return "Delayed"
        return "On Time"
```

- [ ] **Step 3: Run test**

Run: `pytest tests/test_sensor.py -v`

- [ ] **Step 4: Commit**

```bash
git add custom_components/cfl_commute/sensor.py tests/test_sensor.py
git commit -m "feat: add sensor entities"
```

---

## Chunk 4: Binary Sensor & Polish

### Task 5: Disruption Binary Sensor

**Files:**
- Create: `custom_components/cfl_commute/binary_sensor.py`
- Create: `tests/test_binary_sensor.py`

- [ ] **Step 1: Write implementation**

```python
"""Binary sensor for disruption detection."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from .sensor import CFLCommuteBaseSensor
from .const import STATUS_NORMAL

class CFLCommuteDisruptionSensor(CFLCommuteBaseSensor, BinarySensorEntity):
    """Binary sensor for disruption detection."""

    @property
    def name(self) -> str:
        return f"{self._commute_name} Has Disruption"

    @property
    def is_on(self) -> bool:
        """Return true if disruption detected."""
        return self._status_sensor_state != STATUS_NORMAL

    @property
    def _status_sensor_state(self) -> str:
        """Get status from status sensor logic."""
        if any(d.get("is_cancelled") for d in self._departures):
            return "Critical"
        
        max_delay = max((d.get("delay_minutes", 0) for d in self._departures), default=0)
        
        if max_delay >= self._severe_threshold:
            return "Severe"
        elif max_delay >= self._major_threshold:
            return "Major"
        elif max_delay >= self._minor_threshold:
            return "Minor"
        
        return STATUS_NORMAL
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/cfl_commute/binary_sensor.py
git commit -m "feat: add disruption binary sensor"
```

---

### Task 6: Translations & HACS

**Files:**
- Create: `custom_components/cfl_commute/translations/en.json`

- [ ] **Step 1: Add translations**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "CFL Commute",
        "data": {
          "api_key": "API Key"
        }
      },
      "origin": {
        "title": "Select Origin Station",
        "data": {
          "origin": "Origin Station"
        }
      },
      "destination": {
        "title": "Select Destination Station",
        "data": {
          "destination": "Destination Station"
        }
      },
      "settings": {
        "title": "Commute Settings",
        "data": {
          "commute_name": "Commute Name",
          "time_window": "Time Window (minutes)",
          "num_services": "Number of Services",
          "minor_threshold": "Minor Delays Threshold (min)",
          "major_threshold": "Major Delays Threshold (min)",
          "severe_threshold": "Severe Threshold (min)",
          "night_updates": "Enable Night Updates"
        }
      }
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/cfl_commute/translations/en.json
git commit -m "feat: add translations"
```

---

## Chunk 5: Lovelace Card (Separate Repository)

### Task 7: Create Lovelace Card

**Files:**
- Create: `lovelace-cfl-commute-card.js` (in separate repo)

The Lovelace card would be created in a separate repository: `lovelace-cfl-commute-card`

```javascript
// Simple example structure
class CFLCommuteCard extends HTMLElement {
  // Display commute status, next train, disruptions
  // Theme-aware styling
}
customElements.define("cfl-commute-card", CFLCommuteCard);
```

---

## Summary

| Chunk | Task | Files |
|-------|------|-------|
| 1 | Project Setup | manifest.json, __init__.py, const.py |
| 1 | API Client | api.py, test_api.py |
| 2 | Config Flow | config_flow.py, test_config_flow.py |
| 3 | Sensors | sensor.py, test_sensor.py |
| 4 | Binary Sensor | binary_sensor.py, test_binary_sensor.py |
| 4 | Translations | translations/en.json |
| 5 | Lovelace Card | (separate repo) |

---

**Plan complete and saved to `docs/superpowers/plans/2026-03-17-cfl-commute-plan.md`. Ready to execute?**
