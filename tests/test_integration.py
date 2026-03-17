"""Integration tests for CFL Commute API."""

import os
import pytest
from custom_components.cfl_commute.api import CFLCommuteClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("CFL_API_KEY"), reason="CFL_API_KEY environment variable not set"
)


class TestRealAPI:
    """Real API integration tests."""

    @pytest.fixture
    def client(self):
        """Create client with real API key."""
        return CFLCommuteClient(os.environ["CFL_API_KEY"])

    @pytest.mark.asyncio
    async def test_search_stations_returns_results(self, client):
        """Test station search returns real results."""
        stations = await client.search_stations("Luxembourg")

        assert isinstance(stations, list)
        assert len(stations) > 0
        assert any("Luxembourg" in s.name for s in stations)

    @pytest.mark.asyncio
    async def test_search_luxembourg_central(self, client):
        """Test finding Luxembourg station."""
        stations = await client.search_stations("Luxembourg")

        ids = [s.id for s in stations]
        # Check that we found at least one Luxembourg station
        assert len(ids) > 0

    @pytest.mark.asyncio
    async def test_get_departures_returns_data(self, client):
        """Test departures endpoint returns data."""
        departures = await client.get_departures("200426002")

        assert isinstance(departures, list)

    @pytest.mark.asyncio
    async def test_departures_have_required_fields(self, client):
        """Test departure data structure."""
        departures = await client.get_departures("200405060")

        if departures:
            dep = departures[0]
            assert dep.scheduled_departure
            assert dep.platform
            assert (
                dep.operator in client.TRAIN_CATEGORIES
                or dep.operator in client.RAIL_OPERATORS
                or dep.operator in client.BUS_OPERATORS
            )

    @pytest.mark.asyncio
    async def test_rail_operators_only(self, client):
        """Test that only valid transport operators are returned."""
        departures = await client.get_departures("200405060")

        for dep in departures:
            assert (
                dep.operator in client.TRAIN_CATEGORIES
                or dep.operator in client.RAIL_OPERATORS
                or dep.operator in client.BUS_OPERATORS
            )

    @pytest.mark.asyncio
    async def test_station_coords_valid(self, client):
        """Test station coordinates are valid."""
        stations = await client.search_stations("Luxembourg")

        for station in stations:
            assert -180 <= station.lon <= 180
            assert -90 <= station.lat <= 90
