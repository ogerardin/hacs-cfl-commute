# CFL Commute - Home Assistant Integration Design

**Date:** 2026-03-17  
**Status:** Draft  
**Project:** Adapt my-rail-commute (UK) to Luxembourg CFL railways

---

## 1. Overview

### Purpose
A Home Assistant integration that tracks regular train commutes in Luxembourg using real-time CFL data from the official API mobiliteit.lu (ATP). Users monitor upcoming services, receive disruption alerts, and automate commuting routines.

### Source Project
[my-rail-commute](https://github.com/adamf83/my-rail-commute) - UK National Rail integration for Home Assistant

---

## 2. API Specification

### Primary API: API mobiliteit.lu (ATP)

| Attribute | Details |
|-----------|---------|
| **Provider** | Administration des transports publics (ATP) |
| **Base URL** | `https://cdt.hafas.de/opendata/apiserver/` |
| **License** | Creative Commons Attribution 4.0 |
| **Coverage** | CFL trains + all Luxembourg public transport |

#### Endpoints

**Station Search**
```
GET /location.nearbystops?accessId=<API_KEY>&originCoordLong=<lon>&originCoordLat=<lat>&maxNo=<count>&r=<radius>&format=json
```
- Returns stations/stops near coordinates
- Use large radius (100km) and maxNo=5000 to get all stations

**Real-time Departures**
```
GET /departureBoard?accessId=<API_KEY>&id=<STATION_ID>&lang=<en|fr>&format=json
```
- Returns real-time departures for a specific station

#### Obtaining API Key

1. Send email to `opendata-api@atp.etat.lu`
2. Request access to the "API mobiliteit.lu" (ATP)
3. Receive free API key
4. Include key in Home Assistant configuration

---

## 3. Functionality Specification

### Core Features

1. **Real-time Train Tracking**
   - Monitor upcoming services between any two CFL stations
   - Display departure times, platforms, delays, cancellations

2. **Smart Update Intervals**
   - Peak hours (06:00-10:00, 16:00-20:00): Every 2 minutes
   - Off-peak: Every 5 minutes
   - Night (23:00-05:00): Every 15 minutes (configurable)

3. **Disruption Detection**
   - Binary sensor alerts on cancellations or significant delays
   - Configurable delay thresholds

4. **Rich Sensor Data**
   - Platforms, delays, calling points, operators
   - Comprehensive attributes for automation

5. **Multi-Route Support**
   - Configure multiple commutes (morning/evening)

6. **UI Configuration**
   - Config flow interface in Home Assistant
   - Station name search with autocomplete

7. **HACS Compatible**
   - Install via Home Assistant Community Store

8. **Custom Lovelace Card**
   - Beautiful dashboard card for displaying train info
   - Separate repository: `lovelace-cfl-commute-card`

### User Configuration Options

| Option | Default | Range |
|--------|---------|-------|
| API Key | (required) | string |
| Origin Station | (required) | station name search |
| Destination Station | (required) | station name search |
| Commute Name | "Origin → Destination" | string |
| Time Window | 60 minutes | 15-120 |
| Number of Services | 3 | 1-10 |
| Minor Delays Threshold | 3 minutes | 1-60 |
| Major Delays Threshold | 10 minutes | 1-60 |
| Severe Disruption Threshold | 15 minutes | 1-60 |
| Enable Night-Time Updates | false | boolean |

---

## 4. Sensor Specification

### 4.1 Commute Summary Sensor
- **Entity ID**: `sensor.{commute_name}_summary`
- **State**: Summary string (e.g., "3 trains on time", "2 trains delayed")
- **Attributes**:
  - `origin`, `destination` - Station names
  - `origin_id`, `destination_id` - Station IDs
  - `on_time_count`, `delayed_count`, `cancelled_count`
  - `all_trains` - Array of all tracked trains

### 4.2 Commute Status Sensor
- **Entity ID**: `sensor.{commute_name}_status`
- **State**: Hierarchical status
  - `Normal` - All trains on time
  - `Minor Delays` - ≥ minor threshold
  - `Major Delays` - ≥ major threshold
  - `Severe Disruption` - ≥ severe threshold
  - `Critical` - Cancelled (highest priority)
- **Icon**: Dynamic based on status

### 4.3 Next Train Sensor
- **Entity ID**: `sensor.{commute_name}_next_train`
- **State**: "On Time", "Delayed", "Cancelled", "Expected", "No service"
- **Attributes**:
  - `departure_time`, `scheduled_departure`, `expected_departure`
  - `platform`, `platform_changed`, `previous_platform`
  - `operator` (CFL, THELLY, TRAM, etc.)
  - `delay_minutes`, `is_cancelled`
  - `calling_points` - List of stops
  - `delay_reason`, `cancellation_reason`

### 4.4 Individual Train Sensors
- **Entity IDs**: `sensor.{commute_name}_train_1`, `sensor.{commute_name}_train_2`, etc.
- **Count**: 1-10 based on configuration
- Same attributes as Next Train, with `train_number` attribute

### 4.5 Disruption Binary Sensor
- **Entity ID**: `binary_sensor.{commute_name}_has_disruption`
- **State**: "on" when disruption, "off" when normal
- **Attributes**:
  - `current_status`, `cancelled_count`, `delayed_count`
  - `max_delay_minutes`, `disruption_reasons`

---

## 5. Architecture

### Component Structure

```
custom_components/cfl_commute/
├── __init__.py
├── api.py              # API client for mobiliteit.lu
├── config_flow.py      # UI configuration
├── const.py            # Constants, thresholds
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entity
├── station_search.py    # Station name search
└── translations/        # Localization
```

### Data Flow

```
User Config → Config Flow → Station Search (API) → Store Config
                                    ↓
                           Scheduled Update (CoordinatedUpdate)
                                    ↓
                           API Client (departureBoard)
                                    ↓
                           Parse Response → Update Sensors
```

### Key Classes

| Class | Responsibility |
|-------|---------------|
| `CFLCommuteClient` | API communication, station search, departure fetching |
| `CFLCommuteConfigFlow` | UI configuration flow |
| `CFLCommuteSummarySensor` | Aggregate summary of all trains |
| `CFLCommuteStatusSensor` | Hierarchical status determination |
| `CFLCommuteTrainSensor` | Individual train data |
| `CFLCommuteDisruptionBinarySensor` | Disruption detection |

---

## 6. Station Selection

### Approach: Station Name Search

1. User types station name in search field
2. Integration calls `location.nearbystops` with large radius
3. Results filtered by name match (case-insensitive)
4. User selects from filtered results
5. Station ID stored in config for API calls
6. Station name stored for display purposes

### Station ID Format
- Numeric IDs from API (e.g., `200426002` = Luxembourg Central)
- Stored alongside name for UI display

---

## 7. Lovelace Card Specification

### Repository
`lovelace-cfl-commute-card` (separate from integration)

### Features
- Display commute status with icon
- Show next train details (time, platform, delay)
- List upcoming trains
- Highlight disruptions
- Theme-aware styling

### Installation
- HACS (Frontend category)
- Manual: Copy to `www/community/lovelace-cfl-commute-card/`

---

## 8. Differences from UK Version

| Aspect | UK (my-rail-commute) | Luxembourg (cfl_commute) |
|--------|----------------------|--------------------------|
| API | National Rail Darwin | API mobiliteit.lu (ATP) |
| Station Codes | 3-letter CRS | Numeric IDs |
| Operators | UK train companies | CFL, THELLY, TRAM |
| API Key | Required (Rail Data Marketplace) | Required (ATP) |
| Coverage | UK only | Luxembourg + connected networks |

---

## 9. Testing Requirements

### Unit Tests
- API client (station search, departure parsing)
- Sensor state calculation
- Delay threshold logic

### Integration Tests
- Config flow (happy path + error cases)
- Station search results
- Sensor updates

### Manual Testing
- Real API calls with valid key
- Edge cases (no trains, cancellations)

---

## 10. Implementation Priority

1. **Phase 1**: Core integration
   - API client
   - Config flow
   - Basic sensors
   - Station search

2. **Phase 2**: Enhancement
   - Status sensor logic
   - Binary disruption sensor
   - Update intervals

3. **Phase 3**: Polish
   - Lovelace card
   - HACS packaging
   - Documentation
