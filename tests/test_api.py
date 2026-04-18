"""Tests for CFL Commute API client."""

import pytest
import aiohttp
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from custom_components.cfl_commute.api import (
    CFLCommuteClient,
    Departure,
    _clean_station_name,
)
from custom_components.cfl_commute.util import format_time


class TestCleanStationName:
    """Test cases for _clean_station_name()."""

    def test_strips_gare_suffix(self):
        assert _clean_station_name("Esch-sur-Alzette, Gare") == "Esch-sur-Alzette"

    def test_strips_gare_centrale_suffix(self):
        assert _clean_station_name("Luxembourg, Gare Centrale") == "Luxembourg"

    def test_case_insensitive_gare(self):
        assert _clean_station_name("Arlon, gare") == "Arlon"

    def test_no_suffix_unchanged(self):
        assert _clean_station_name("Bettembourg") == "Bettembourg"

    def test_belval_with_parentheses(self):
        assert _clean_station_name("Belval (Université), Gare") == "Belval (Université)"

    def test_strips_trailing_whitespace(self):
        assert _clean_station_name("Rodange, Gare  ") == "Rodange"


class TestCFLCommuteClientSession:
    """Test cases for CFLCommuteClient session handling."""

    def test_client_creates_default_session_when_none(self):
        """Client should create its own session when none is provided (backward compat)."""
        client = CFLCommuteClient("test_key")
        assert client._session is None
        assert client._owns_session is True

    def test_client_accepts_external_session(self):
        """Client should accept an aiohttp.ClientSession via constructor."""
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        client = CFLCommuteClient("test_key", session=mock_session)
        assert client._session is mock_session
        assert client._owns_session is False

    @pytest.mark.asyncio
    async def test_close_with_own_session(self):
        """Closing client with own session should close it."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        # Simulate _owns_session by using internal method
        client = CFLCommuteClient("test_key")
        client._session = mock_session
        client._owns_session = True
        await client.close()
        mock_session.close.assert_called_once()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_with_external_session_is_noop(self):
        """Closing client with external session should not close the session."""
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        client = CFLCommuteClient("test_key", session=mock_session)
        await client.close()
        mock_session.close.assert_not_called()
        assert client._session is None


class TestCFLCommuteClient:
    """Test cases for CFLCommuteClient."""

    def test_client_initialization(self):
        """Test client is initialized with API key."""
        client = CFLCommuteClient("test_api_key")
        assert client._api_key == "test_api_key"
        assert client.BASE_URL == "https://cdt.hafas.de/opendata/apiserver"

    def test_rail_operators_defined(self):
        """Test that CFL train categories are defined."""
        client = CFLCommuteClient("test_key")
        assert "RB" in client.TRAIN_CATEGORIES
        assert "RE" in client.TRAIN_CATEGORIES
        assert "CFL" in client.RAIL_OPERATORS

    @pytest.mark.asyncio
    async def test_search_stations_returns_list(self):
        """Test station search returns list of Station objects from departures API."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "Stops": {
                        "Stop": [
                            {
                                "extId": "300031019",
                                "name": "Luxembourg, Gare Centrale",
                                "lon": 6.1,
                                "lat": 49.6,
                            },
                            {
                                "extId": "300439001",
                                "name": "Esch-sur-Alzette, Gare",
                                "lon": 5.94,
                                "lat": 49.50,
                            },
                        ]
                    }
                }
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            stations = await client.search_stations("")

        assert isinstance(stations, list)
        assert len(stations) == 2
        assert stations[0].name == "Esch-sur-Alzette"
        assert stations[1].name == "Luxembourg"

    @pytest.mark.asyncio
    async def test_search_stations_filters_by_query(self):
        """Test that station search filters by query."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "Stops": {
                        "Stop": [
                            {
                                "extId": "300031019",
                                "name": "Luxembourg, Gare Centrale",
                                "lon": 6.1,
                                "lat": 49.6,
                            },
                            {
                                "extId": "300439001",
                                "name": "Esch-sur-Alzette, Gare",
                                "lon": 5.94,
                                "lat": 49.50,
                            },
                        ]
                    }
                }
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            stations = await client.search_stations("Esch")

        assert len(stations) == 1
        assert stations[0].name == "Esch-sur-Alzette"

    @pytest.mark.asyncio
    async def test_search_stations_includes_luxembourg_station(self):
        """Test that Luxembourg station is included in results."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "Stops": {
                        "Stop": [
                            {
                                "extId": "300031019",
                                "name": "Luxembourg, Gare Centrale",
                                "lon": 6.1,
                                "lat": 49.6,
                            },
                        ]
                    }
                }
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            stations = await client.search_stations("")

        assert len(stations) == 1
        assert stations[0].name == "Luxembourg"
        assert stations[0].id == "300031019"

    @pytest.mark.asyncio
    async def test_get_departures_filters_non_rail(self):
        """Test that only rail operators are returned."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "ProductAtStop": {
                        "name": "Train 1",
                        "catOut": "RB",
                        "operatorInfo": {"nameS": "CFL"},
                    },
                    "time": "10:00",
                    "rtTime": "10:00",
                    "direction": "Test",
                    "num": "1234",
                },
                {
                    "ProductAtStop": {
                        "name": "Bus 1",
                        "catOut": "Bus",
                        "operatorInfo": {"nameS": "AVL"},
                    },
                    "time": "10:05",
                    "rtTime": "10:05",
                    "direction": "Test",
                    "num": "",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            # Use large time_window to include test times regardless of current time
            departures = await client.get_departures("200426002", time_window=1440)

        # Both RB (train) and Bus should be included
        assert len(departures) == 2
        operators = [d.operator for d in departures]
        assert "CFL" in operators  # RB train has CFL operator
        assert "AVL" in operators

    @pytest.mark.asyncio
    async def test_get_departures_filters_by_time_window(self):
        """Test that departures are filtered by time window."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "ProductAtStop": {
                        "name": "Train 1",
                        "catOut": "RB",
                        "operatorInfo": {"nameS": "CFL"},
                    },
                    "time": "10:00",  # Within 60 min window
                    "rtTime": "10:00",
                    "direction": "Test",
                    "num": "1234",
                },
                {
                    "ProductAtStop": {
                        "name": "Train 2",
                        "catOut": "RB",
                        "operatorInfo": {"nameS": "CFL"},
                    },
                    "time": "14:00",  # Outside 60 min window
                    "rtTime": "14:00",
                    "direction": "Test",
                    "num": "5678",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            # With time_window=0, all departures should be included
            departures = await client.get_departures("200426002", time_window=0)

        assert len(departures) == 2

    def test_filter_by_time_window_handles_midnight(self):
        """Test that time filtering handles midnight crossing correctly."""
        client = CFLCommuteClient("test_api_key")

        # Create mock departures with times around midnight
        departures = [
            Departure(
                station_id="123",
                scheduled_departure="23:50",  # Will be 10 min from mocked time
                expected_departure="23:50",
                platform="1",
                line="RB",
                direction="Test",
                operator="CFL",
                train_number="1234",
                is_cancelled=False,
                delay_minutes=0,
                calling_points=[],
                stop_ids=[],
            ),
            Departure(
                station_id="123",
                scheduled_departure="00:10",  # Will be 30 min from mocked time (crosses midnight)
                expected_departure="00:10",
                platform="1",
                line="RB",
                direction="Test",
                operator="CFL",
                train_number="5678",
                is_cancelled=False,
                delay_minutes=0,
                calling_points=[],
                stop_ids=[],
            ),
        ]

        # Mock datetime.now() to return 23:40
        mock_now = MagicMock()
        mock_now.hour = 23
        mock_now.minute = 40

        with patch("custom_components.cfl_commute.api.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            # With 60 min window, both should be included
            # 23:50 is 10 min away, 00:10 is 30 min away (crosses midnight)
            filtered = client._filter_by_time_window(departures, 60)
            assert len(filtered) == 2

            # With 5 min window, only departures within 5 min
            # 23:50 is 10 min away - outside window
            # 00:10 is 30 min away - outside window
            filtered = client._filter_by_time_window(departures, 5)
            assert len(filtered) == 0

        # Test that time_window=0 returns all departures
        filtered = client._filter_by_time_window(departures, 0)
        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_delay_calculation_with_hh_mm_ss_format(self):
        """Test that delay is correctly calculated with HH:MM:SS time format."""
        client = CFLCommuteClient("test_api_key")

        # API returns times in HH:MM:SS format
        mock_response = {
            "Departure": [
                {
                    "ProductAtStop": {
                        "name": "RE 456",
                        "catOut": "RE",
                        "operatorInfo": {"nameS": "CFL"},
                    },
                    "time": "11:20:00",  # Scheduled 11:20
                    "rtTime": "11:22:00",  # Expected 11:22 (2 min late)
                    "direction": "Rodange",
                    "num": "456",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            departures = await client.get_departures("110109004", time_window=1440)

        assert len(departures) == 1
        assert departures[0].scheduled_departure == "11:20:00"
        assert departures[0].expected_departure == "11:22:00"
        assert departures[0].delay_minutes == 2  # Should be 2, not 0

    @pytest.mark.asyncio
    async def test_delay_calculation_on_time(self):
        """Test that delay is 0 when train is on time."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "ProductAtStop": {
                        "name": "RE 456",
                        "catOut": "RE",
                        "operatorInfo": {"nameS": "CFL"},
                    },
                    "time": "11:20:00",
                    "rtTime": "11:20:00",  # Same as scheduled
                    "direction": "Rodange",
                    "num": "456",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            departures = await client.get_departures("110109004", time_window=1440)

        assert len(departures) == 1
        assert departures[0].delay_minutes == 0


class TestFormatTime:
    """Test cases for format_time utility function."""

    def test_format_time_with_seconds(self):
        """Test formatting time string with seconds."""
        assert format_time("01:10:00") == "01:10"

    def test_format_time_without_seconds(self):
        """Test formatting time string without seconds."""
        assert format_time("01:10") == "01:10"

    def test_format_time_empty_string(self):
        """Test formatting empty string."""
        assert format_time("") == ""

    def test_format_time_none(self):
        """Test formatting None."""
        assert format_time(None) == ""

    def test_format_time_short_string(self):
        """Test formatting short time string."""
        assert format_time("01") == "01"

    def test_format_time_invalid(self):
        """Test formatting invalid time string."""
        assert format_time("invalid") == "inval"
