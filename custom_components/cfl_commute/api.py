"""API client for CFL mobiliteit.lu."""

from dataclasses import dataclass
from typing import Optional
import aiohttp


@dataclass
class Station:
    """Represents a station/stop."""

    id: str
    name: str
    lon: float
    lat: float


@dataclass
class Departure:
    """Represents a train departure."""

    station_id: str
    scheduled_departure: str
    expected_departure: str
    platform: str
    line: str
    direction: str
    operator: str
    train_number: str
    is_cancelled: bool
    delay_minutes: int
    calling_points: list


class CFLCommuteClient:
    """Client for mobiliteit.lu API."""

    BASE_URL = "https://cdt.hafas.de/opendata/apiserver"

    RAIL_OPERATORS = {"CFL", "EC", "IC", "TER", "TGV", "RE", "RB"}

    def __init__(self, api_key: str):
        """Initialize the client."""
        self._api_key = api_key

    async def search_stations(self, query: str) -> list[Station]:
        """Search for stations by name."""
        url = f"{self.BASE_URL}/location.nearbystops"
        params = {
            "accessId": self._api_key,
            "originCoordLong": "6.09528",
            "originCoordLat": "49.77723",
            "maxNo": "5000",
            "r": "100000",
            "format": "json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        stations = []
        location_list = data.get("LocationList", {})
        stop_locations = location_list.get("StopLocation", [])

        if isinstance(stop_locations, dict):
            stop_locations = [stop_locations]

        for stop in stop_locations:
            if query.lower() in stop.get("name", "").lower():
                stations.append(
                    Station(
                        id=stop.get("id"),
                        name=stop.get("name"),
                        lon=float(stop.get("lon", 0)),
                        lat=float(stop.get("lat", 0)),
                    )
                )

        return stations

    async def get_departures(
        self, station_id: str, lang: str = "en", time_window: int = 60
    ) -> list[Departure]:
        """Get departures for a station."""
        url = f"{self.BASE_URL}/departureBoard"
        params = {
            "accessId": self._api_key,
            "id": station_id,
            "lang": lang,
            "format": "json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        departures = []
        departure_list = data.get("Departure", [])

        if isinstance(departure_list, dict):
            departure_list = [departure_list]

        for dep in departure_list:
            product = dep.get("product", {})
            operator = product.get("cat", "")

            if operator not in self.RAIL_OPERATORS:
                continue

            is_cancelled = dep.get("cancelled", False)
            delay = dep.get("delay")

            dep_time = dep.get("dep", "")
            scheduled_time = dep.get("depTime", "")

            calling_points = self._extract_calling_points(dep)

            departures.append(
                Departure(
                    station_id=station_id,
                    scheduled_departure=scheduled_time,
                    expected_departure=dep_time,
                    platform=dep.get("platform", "TBA"),
                    line=dep.get("line", ""),
                    direction=dep.get("direction", ""),
                    operator=operator,
                    train_number=dep.get("trainNumber", ""),
                    is_cancelled=is_cancelled,
                    delay_minutes=int(delay) if delay else 0,
                    calling_points=calling_points,
                )
            )

        return departures[:10]

    def _extract_calling_points(self, dep: dict) -> list[str]:
        """Extract calling points from departure data."""
        stops = dep.get("Stops", {}).get("Stop", [])
        if isinstance(stops, dict):
            stops = [stops]
        return [stop.get("name", "") for stop in stops if stop.get("name")]
