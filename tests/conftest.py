"""Shared test fixtures."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def aiohttp_session_cleanup():
    """Auto-use fixture to properly close aiohttp sessions in tests.

    In Python 3.12+, aiohttp's TCPConnector creates a background thread
    for cleanup. This fixture ensures proper cleanup after each test.
    """
    yield
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, lambda: None)
    except RuntimeError:
        pass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.data = {
        "api_key": "test_key",
        "origin": {"id": "200426002", "name": "Luxembourg"},
        "destination": {"id": "200426001", "name": "Esch-sur-Alzette"},
        "commute_name": "Test Commute",
        "time_window": 60,
        "num_trains": 3,
        "minor_threshold": 3,
        "major_threshold": 10,
        "severe_threshold": 15,
        "night_updates": False,
    }
    return entry


@pytest.fixture
def mock_client():
    """Mock API client."""
    client = AsyncMock()
    client.get_departures = AsyncMock(return_value=[])
    client.search_stations = AsyncMock(return_value=[])
    return client


@pytest.fixture
def sample_departures():
    """Sample departure data for testing."""
    return [
        {
            "station_id": "200426002",
            "scheduled_departure": "08:00",
            "expected_departure": "08:00",
            "platform": "1",
            "line": "1",
            "direction": "Esch-sur-Alzette",
            "operator": "CFL",
            "train_number": "1234",
            "is_cancelled": False,
            "delay_minutes": 0,
            "calling_points": ["Luxembourg", "Bettembourg", "Esch-sur-Alzette"],
        },
        {
            "station_id": "200426002",
            "scheduled_departure": "08:30",
            "expected_departure": "08:35",
            "platform": "2",
            "line": "1",
            "direction": "Esch-sur-Alzette",
            "operator": "CFL",
            "train_number": "1236",
            "is_cancelled": False,
            "delay_minutes": 5,
            "calling_points": ["Luxembourg", "Bettembourg", "Esch-sur-Alzette"],
        },
    ]


@pytest.fixture
def cancelled_departure():
    """Sample cancelled departure."""
    return {
        "station_id": "200426002",
        "scheduled_departure": "08:00",
        "expected_departure": "08:00",
        "platform": "1",
        "line": "1",
        "direction": "Esch-sur-Alzette",
        "operator": "CFL",
        "train_number": "1234",
        "is_cancelled": True,
        "delay_minutes": 0,
        "calling_points": [],
    }
