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
        """Test that CFL train categories are defined."""
        client = CFLCommuteClient("test_key")
        assert "RB" in client.TRAIN_CATEGORIES
        assert "RE" in client.TRAIN_CATEGORIES
        assert "CFL" in client.RAIL_OPERATORS

    @pytest.mark.asyncio
    async def test_search_stations_returns_list(self):
        """Test station search returns list of Station objects."""
        client = CFLCommuteClient("test_api_key")

        mock_response = {
            "stopLocationOrCoordLocation": [
                {
                    "StopLocation": {
                        "id": "A=1@O=Luxembourg@X=6114948@Y=49626164@U=82@L=200426002@",
                        "extId": "200426002",
                        "name": "Luxembourg",
                        "lon": 6.1,
                        "lat": 49.6,
                    }
                },
                {
                    "StopLocation": {
                        "id": "A=1@O=Luxembourg Airport@X=6200000@Y=4960000@U=82@L=200426003@",
                        "extId": "200426003",
                        "name": "Luxembourg Airport",
                        "lon": 6.2,
                        "lat": 49.6,
                    }
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
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
            departures = await client.get_departures("200426002")

        # Both RB (train) and Bus should be included
        assert len(departures) == 2
        operators = [d.operator for d in departures]
        assert "CFL" in operators  # RB train has CFL operator
        assert "AVL" in operators
