"""API client for CFL mobiliteit.lu."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import aiohttp

_LOGGER = logging.getLogger(__name__)


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
    stop_ids: list
    journey_ref: str = ""


class CFLCommuteClient:
    """Client for mobiliteit.lu API."""

    BASE_URL = "https://cdt.hafas.de/opendata/apiserver"

    # Train categories (not operators) - these are used for filtering
    TRAIN_CATEGORIES = {"RB", "RE", "IC", "TER", "TGV", "EC", "Train"}
    # Actual railway operators
    RAIL_OPERATORS = {"CFL"}
    # Include bus operators for stations that only have bus data
    BUS_OPERATORS = {"AVL", "RGTR", "TICE", "Bus"}

    def __init__(self, api_key: str):
        """Initialize the client."""
        self._api_key = api_key

    async def _request(self, url: str, params: dict[str, str] | None = None) -> dict:
        """Make an API request."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()

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

        data = await self._request(url, params)

        stations = []
        # Handle different response formats
        location_data = data.get("stopLocationOrCoordLocation", [])

        if isinstance(location_data, dict):
            location_data = [location_data]

        for loc in location_data:
            stop = loc.get("StopLocation")
            if not stop:
                continue

            # Extract station name
            name = stop.get("name", "")
            if query.lower() not in name.lower():
                continue

            # Extract ID - could be in 'id' or 'extId'
            station_id = stop.get("id", stop.get("extId", ""))

            # Parse numeric ID from complex format like "A=1@O=Name@X=...@L=160102002@"
            if "L=" in station_id:
                parts = station_id.split("@")
                for part in parts:
                    if part.startswith("L="):
                        station_id = part[2:]
                        break

            stations.append(
                Station(
                    id=station_id,
                    name=name,
                    lon=float(stop.get("lon", 0)),
                    lat=float(stop.get("lat", 0)),
                )
            )

        return stations

    async def get_departures(
        self,
        station_id: str,
        lang: str = "en",
        time_window: int = 60,
        date: str | None = None,
        time: str | None = None,
    ) -> list[Departure]:
        """Get departures for a station, filtered by time window."""
        url = f"{self.BASE_URL}/departureBoard"
        params = {
            "accessId": self._api_key,
            "id": station_id,
            "lang": lang,
            "format": "json",
            "passlist": "1",  # Include all stops for this journey
        }

        # Add date/time parameters if provided (format: YYYY-MM-DD, HH:MM)
        if date:
            params["date"] = date
        if time:
            params["time"] = time

        data = await self._request(url, params)

        departures = []
        departure_list = data.get("Departure", [])

        if isinstance(departure_list, dict):
            departure_list = [departure_list]

        for dep in departure_list:
            # Handle different response formats
            product = dep.get("ProductAtStop", {})
            product_name = product.get("name", "")

            # Get operator info
            operator_info = product.get("operatorInfo", {})
            operator_name = operator_info.get("nameS", operator_info.get("name", ""))

            # Check if it's a valid transport type (train category or bus)
            cat_out = product.get("catOut", "")
            if (
                cat_out not in self.TRAIN_CATEGORIES
                and cat_out not in self.BUS_OPERATORS
            ):
                continue

            # Determine operator (use category if no operator info)
            if operator_name:
                operator = operator_name
            else:
                operator = cat_out  # Fallback to category like "RB"

            # Parse times
            scheduled_time = dep.get("time", "")
            actual_time = dep.get("rtTime", scheduled_time)

            # Calculate delay in minutes
            delay_minutes = 0
            if scheduled_time and actual_time:
                try:
                    sched_time = datetime.strptime(scheduled_time, "%H:%M:%S")
                    actual_time_parsed = datetime.strptime(actual_time, "%H:%M:%S")
                    delay_minutes = int(
                        (actual_time_parsed - sched_time).total_seconds() / 60
                    )
                except ValueError:
                    delay_minutes = 0

            # Check if cancelled
            is_cancelled = dep.get("JourneyStatus") == "C" or not dep.get(
                "reachable", True
            )

            # Get direction
            direction = dep.get("direction", "")

            # Get all stops for this journey (when passlist=1 is used)
            stops = dep.get("Stops", {}).get("Stop", [])
            if isinstance(stops, dict):
                stops = [stops]

            # Extract stop IDs from the journey
            stop_ids = []
            stop_names = []
            for stop in stops:
                stop_id = stop.get("extId", "")
                stop_name = stop.get("name", "")
                if stop_id:
                    stop_ids.append(stop_id)
                if stop_name:
                    stop_names.append(stop_name)

            departures.append(
                Departure(
                    station_id=station_id,
                    scheduled_departure=scheduled_time,
                    expected_departure=actual_time,
                    platform=dep.get("platform", "TBA"),
                    line=product_name.split()[-1] if product_name else "",
                    direction=direction,
                    operator=operator,
                    train_number=dep.get("num", ""),
                    is_cancelled=is_cancelled,
                    delay_minutes=delay_minutes,
                    calling_points=stop_names,
                    stop_ids=stop_ids,
                    journey_ref="",
                )
            )

        # Filter by time window and return
        departures = self._filter_by_time_window(departures, time_window)
        return departures[:10]

    def _filter_by_time_window(
        self, departures: list[Departure], time_window: int
    ) -> list[Departure]:
        """Filter departures by time window (minutes from now).

        Handles midnight crossing (e.g., current 23:50, departure 00:10 = +20 min).
        """
        if time_window <= 0:
            return departures

        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute

        filtered = []
        for dep in departures:
            try:
                dep_time = datetime.strptime(dep.scheduled_departure, "%H:%M")
                dep_minutes = dep_time.hour * 60 + dep_time.minute

                # Calculate minutes from now, handling midnight crossing
                diff = dep_minutes - now_minutes
                if diff < -60:  # Past midnight (e.g., 23:50 -> 00:10 = +20 min)
                    diff += 1440  # Add 24 hours in minutes

                if 0 <= diff <= time_window:
                    filtered.append(dep)
            except (ValueError, TypeError):
                # Keep departures where time parsing fails
                filtered.append(dep)

        return filtered

    async def get_journey_details(self, journey_ref: str) -> list[dict]:
        """Get journey details to find calling points.

        Args:
            journey_ref: Journey reference from departure (e.g., "1|1735|16|82|17032026")

        Returns:
            List of stop dictionaries with id, name, and arrival time
        """
        url = f"{self.BASE_URL}/journeyDetail"
        params = {
            "accessId": self._api_key,
            "ref": journey_ref,
            "format": "json",
        }

        try:
            data = await self._request(url, params)
            stops = data.get("JourneyDetail", {}).get("Stops", {}).get("Stop", [])

            if isinstance(stops, dict):
                stops = [stops]

            calling_points = []
            for stop in stops:
                stop_id = stop.get("extId", "")
                # Parse numeric ID from complex format
                if not stop_id:
                    stop_id_full = stop.get("id", "")
                    if "L=" in stop_id_full:
                        parts = stop_id_full.split("@")
                        for part in parts:
                            if part.startswith("L="):
                                stop_id = part[2:]
                                break

                calling_points.append(
                    {
                        "id": stop_id,
                        "name": stop.get("name", ""),
                        "arr_time": stop.get("arrTime", stop.get("depTime", "")),
                    }
                )

            return calling_points
        except Exception as e:
            _LOGGER.error(f"Failed to fetch journey details: {e}")
            return []

    def _extract_calling_points(self, dep: dict) -> list[str]:
        """Extract calling points from departure data."""
        stops = dep.get("Stops", {}).get("Stop", [])
        if isinstance(stops, dict):
            stops = [stops]
        return [stop.get("name", "") for stop in stops if stop.get("name")]
