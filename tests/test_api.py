"""Tests for CFL Commute API client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from custom_components.cfl_commute.api import CFLCommuteClient, Station, Departure


class TestCFLCommuteClient:
    """Test cases for CFLCommuteClient."""

    def test_client_initialization(self):
        """Test client is initialized with API key."""
        client = CFLCommuteClient("test_api_key")
        assert client._api_key == "test_api_key"
        assert client.BASE_URL == "https://cdt.hafas.de/opendata/apiserver"

    def test_rail_operators_defined(self):
        """Test that CFL is in rail operators."""
        client = CFLCommuteClient("test_key")
        assert "CFL" in client.RAIL_OPERATORS

    @pytest.mark.asyncio
    async def test_search_stations_returns_list(self):
        """Test station search returns list of Station objects."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "LocationList": {
                "StopLocation": [
                    {
                        "id": "200426002",
                        "name": "Luxembourg",
                        "lon": "6.1",
                        "lat": "49.6",
                    },
                    {
                        "id": "200426003",
                        "name": "Luxembourg Airport",
                        "lon": "6.2",
                        "lat": "49.6",
                    },
                ]
            }
        }

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            stations = await client.search_stations("Luxembourg")

        assert isinstance(stations, list)
        assert len(stations) == 2

    @pytest.mark.asyncio
    async def test_get_departures_filters_non_rail(self):
        """Test that only rail operators are returned."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "Departure": [
                {
                    "product": {"cat": "CFL"},
                    "dep": "10:00",
                    "depTime": "10:00",
                    "platform": "1",
                    "line": "1",
                    "direction": "Test",
                    "trainNumber": "1234",
                    "cancelled": False,
                    "delay": 0,
                },
                {
                    "product": {"cat": "BUS"},
                    "dep": "10:05",
                    "depTime": "10:05",
                    "platform": "TBA",
                    "line": "Bus1",
                    "direction": "Test",
                    "trainNumber": "",
                    "cancelled": False,
                    "delay": 0,
                },
            ]
        }

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            departures = await client.get_departures("200426002")

        assert len(departures) == 1
        assert departures[0].operator == "CFL"
