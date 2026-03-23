# AGENTS.md - Agentic Coding Guidelines

This file provides guidelines for agents working in this repository.

---

## 1. Build / Lint / Test Commands

### Testing

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install pytest pytest-asyncio aiohttp homeassistant voluptuous

# Run all tests (unit + integration)
pytest tests/ -v

# Run unit tests only (skip integration tests)
pytest tests/ -v -m "not integration"

# Run a single test file
pytest tests/test_api.py -v

# Run a single test
pytest tests/test_api.py::TestCFLCommuteClient::test_client_initialization -v

# Run integration tests (requires API key)
CFL_API_KEY=your_key pytest tests/test_integration.py -v

# Run tests with coverage
pytest tests/ --cov=custom_components/cfl_commute --cov-report=term-missing
```

### Code Quality

```bash
# Install development dependencies
pip install ruff black mypy

# Run ruff linter
ruff check custom_components/ tests/

# Auto-fix linting issues
ruff check --fix custom_components/ tests/

# Run black formatter
black custom_components/ tests/

# Type checking with mypy
mypy custom_components/ --ignore-missing-imports
```

---

## 2. Code Style Guidelines

### General Principles

- **Follow Home Assistant conventions**: This is a Home Assistant custom component
- **Use type hints**: All functions should have type annotations
- **Keep it simple**: YAGNI - don't add features until needed
- **Write tests**: All new code should have tests
- **Small files**: Each file should have one clear responsibility

### Import Conventions

```python
# Standard library first
from dataclasses import dataclass
from typing import Optional
import asyncio

# Third-party libraries
import aiohttp
import voluptuous as vol

# Home Assistant imports
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

# Local imports (relative)
from .const import DOMAIN, CONF_API_KEY
from .api import CFLCommuteClient
```

### Formatting

- **Line length**: 100 characters max
- **Indentation**: 4 spaces (no tabs)
- **Blank lines**: 
  - 2 blank lines between top-level definitions
  - 1 blank line between methods in a class
- **Trailing commas**: Use when breaking across lines

### Type Annotations

```python
# Use specific types, not generic "Any"
def search_stations(self, query: str) -> list[Station]:
    ...

# Use Optional for nullable parameters
async def _request(self, url: str, params: dict = None) -> Optional[dict]:
    ...

# Use dataclasses for structured data
@dataclass
class Station:
    id: str
    name: str
    lon: float
    lat: float
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `api.py`, `config_flow.py` |
| Classes | PascalCase | `CFLCommuteClient`, `CFLCommuteSensor` |
| Functions | snake_case | `async_setup_entry`, `search_stations` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_TIME_WINDOW`, `BASE_URL` |
| Private methods | snake_case with leading underscore | `_request`, `_extract_calling_points` |
| Config keys | snake_case | `CONF_API_KEY`, `CONF_COMMUTE_NAME` |
| Entity IDs | snake_case | `sensor.cfl_commute_summary` |

### Docstrings

```python
class CFLCommuteClient:
    """Client for mobiliteit.lu API."""

    def __init__(self, api_key: str):
        """Initialize the client."""
        self._api_key = api_key
```

### Error Handling

```python
# Use logging for errors, not print
import logging

_LOGGER = logging.getLogger(__name__)

# Log errors with context
try:
    departures = await self._client.get_departures(station_id)
except aiohttp.ClientError as e:
    _LOGGER.error(f"Failed to fetch departures: {e}")
    return []

# Use specific exceptions, not bare except
except ValueError as e:
    _LOGGER.warning(f"Invalid data format: {e}")
```

---

## 3. Project Structure

```
custom_components/cfl_commute/
├── __init__.py           # Component setup/teardown
├── api.py               # API client (external calls)
├── config_flow.py       # UI configuration flow
├── const.py             # Constants, defaults
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
└── translations/        # Localization
    └── en.json

tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_api.py          # API client tests
├── test_sensor.py       # Sensor logic tests
├── test_config_flow.py  # Config flow tests
├── test_integration.py  # Real API tests
```

---

## 4. Testing Guidelines

### Unit Tests

- Use `pytest` with `pytest-asyncio` for async tests
- Mock external dependencies (API calls, HA internals)
- Test one thing per test function
- Use descriptive test names: `test_<what>_<expected_behavior>`

```python
@pytest.mark.asyncio
async def test_search_stations_returns_list(self):
    """Test station search returns list of Station objects."""
    client = CFLCommuteClient("test_api_key")
    # ... test code
```

### Integration Tests

- Mark with `@pytest.mark.integration`
- Skip if no API key: use `pytest.mark.skipif`
- Test against real API when possible

```python
pytestmark = pytest.mark.skipif(
    not os.environ.get("CFL_API_KEY"),
    reason="CFL_API_KEY environment variable not set"
)
```

---

## 5. Home Assistant Specific

### Entity Naming

- Sensors: `sensor.{commute_name}_{type}` 
  - `sensor.morning_commute_summary`
  - `sensor.morning_commute_status`
  - `sensor.morning_commute_train_1`
- Binary sensors: `binary_sensor.{commute_name}_has_disruption`

### Config Flow

- Use `config_entries.ConfigFlow` base class
- Use `SchemaFlowFormStep` for multi-step flows
- Validate user input with voluptuous schemas
- Store API key in config data (not options)

### Sensors

- Inherit from `SensorEntity` or `BinarySensorEntity`
- Implement `async_update` for data fetching
- Use `extra_state_attributes` for rich data
- Set `unique_id` for proper entity registry

---

## 6. API Reference

### mobiliteit.lu API

- **Base URL**: `https://cdt.hafas.de/opendata/apiserver`
- **Station search**: `/location.nearbystops`
- **Departures**: `/departureBoard`
- **Station ID format**: 9-digit numbers (e.g., `200405060` for Luxembourg Gare Centrale)
- **Train categories**: RB, RE, IC, TER, TGV, EC
- **Operator**: CFL (Chemins de Fer Luxembourgeois)

---

## 7. Git Conventions

- **Commits**: Use imperative mood ("Add feature" not "Added feature")
- **Branch naming**: `feature/description` or `fix/description`
- **Commit messages**: First line < 72 chars, body for details

```bash
# Good commit messages
git commit -m "feat: add station search to config flow"
git commit -m "fix: handle empty departures list"
git commit -m "test: add integration tests for real API"
```

### Releases

To make a release:

1. **Update version** in `custom_components/cfl_commute/manifest.json`
2. **Zip the integration**:
   ```bash
   cd custom_components && zip -r ../cfl_commute.zip cfl_commute && cd ..
   ```
3. **Create git tag** with the same version:
   ```bash
   git tag -a 1.3.2 -m "Release 1.3.2"
   git push origin main --tags
   ```
4. **Create GitHub release**:
   ```bash
   gh release create 1.3.2 --title "Release 1.3.2" --notes "Changes in this release..."
   ```
5. **Upload the zip asset**:
   ```bash
   gh release upload 1.3.2 cfl_commute.zip
   ```
