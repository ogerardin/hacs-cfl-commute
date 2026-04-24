"""API client for CFL mobiliteit.lu."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
import aiohttp

LUXEMBOURG_TZ = ZoneInfo("Europe/Luxembourg")


def _get_luxembourg_now() -> datetime:
    """Get current time in Luxembourg timezone."""
    return datetime.now(LUXEMBOURG_TZ)


_LOGGER = logging.getLogger(__name__)

RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_PER_HOUR = 100
RATE_LIMIT_WARNING_THRESHOLD = 0.8


class CFLAPIError(Exception):
    """Exception raised for CFL API errors."""

    pass


class RateLimitExceeded(CFLAPIError):
    """Exception raised when rate limit is exceeded."""

    pass


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


def _normalize_platform(platform):
    """Normalize platform value to a string.

    The HAFAS API can return platform as either a string ("3")
    or an object ({"text": "3", "pos": "N"}).
    """
    if isinstance(platform, dict):
        return str(
            platform.get("text", platform.get("name", platform.get("number", "")))
        )
    if platform and platform != "n/a":
        return str(platform)
    return ""


def _clean_station_name(name: str) -> str:
    """Remove redundant ', Gare' suffixes from station names.

    The CFL API appends ', Gare' or ', Gare Centrale' to station names,
    which is redundant since all entries are train stations.
    """
    return re.sub(r",\s*Gare\b.*$", "", name, flags=re.IGNORECASE).strip()


class CFLCommuteClient:
    """Client for mobiliteit.lu API."""

    BASE_URL = "https://cdt.hafas.de/opendata/apiserver"

    # Train categories (not operators) - these are used for filtering
    TRAIN_CATEGORIES = {"RB", "RE", "IC", "TER", "TGV", "EC", "Train"}
    # Actual railway operators
    RAIL_OPERATORS = {"CFL"}
    # Include bus operators for stations that only have bus data
    BUS_OPERATORS = {"AVL", "RGTR", "TICE", "Bus"}

    # Luxembourg hub station ID - used to discover all train stations
    LUXEMBOURG_HUB_STATION_ID = "200405060"

    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None):
        """Initialize the client.

        Args:
            api_key: CFL mobiliteit.lu API key.
            session: Optional aiohttp session. If None, one will be created on first request.
                     Pass HA's managed session via async_get_clientsession(hass) for proper lifecycle.
        """
        self._api_key = api_key
        self._session = session
        self._owns_session = session is None
        self._rate_limit_calls_minute: list[float] = []
        self._rate_limit_calls_hour: list[float] = []
        self._cached_stations_: list[Station] | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    def _cleanup_rate_limit_calls(self) -> None:
        """Remove expired entries from rate limit tracking."""
        now = time.time()
        self._rate_limit_calls_minute = [
            t for t in self._rate_limit_calls_minute if now - t < 60
        ]
        self._rate_limit_calls_hour = [
            t for t in self._rate_limit_calls_hour if now - t < 3600
        ]

    def _check_rate_limit(self) -> None:
        """Check if we're approaching rate limits and log warning."""
        self._cleanup_rate_limit_calls()

        minute_count = len(self._rate_limit_calls_minute)
        hour_count = len(self._rate_limit_calls_hour)

        minute_pct = minute_count / RATE_LIMIT_PER_MINUTE
        hour_pct = hour_count / RATE_LIMIT_PER_HOUR

        if minute_pct >= RATE_LIMIT_WARNING_THRESHOLD:
            _LOGGER.warning(
                "Approaching per-minute rate limit: %d/%d (%.0f%%)",
                minute_count,
                RATE_LIMIT_PER_MINUTE,
                minute_pct * 100,
            )
        if hour_pct >= RATE_LIMIT_WARNING_THRESHOLD:
            _LOGGER.warning(
                "Approaching per-hour rate limit: %d/%d (%.0f%%)",
                hour_count,
                RATE_LIMIT_PER_HOUR,
                hour_pct * 100,
            )

        if minute_count >= RATE_LIMIT_PER_MINUTE:
            raise RateLimitExceeded(
                f"Per-minute rate limit reached ({RATE_LIMIT_PER_MINUTE} calls)"
            )
        if hour_count >= RATE_LIMIT_PER_HOUR:
            raise RateLimitExceeded(
                f"Per-hour rate limit reached ({RATE_LIMIT_PER_HOUR} calls)"
            )

    def _record_api_call(self) -> None:
        """Record an API call for rate limit tracking."""
        now = time.time()
        self._rate_limit_calls_minute.append(now)
        self._rate_limit_calls_hour.append(now)

    async def close(self) -> None:
        """Close the aiohttp session if we own it.

        Only closes sessions we created. External sessions (e.g. from
        async_get_clientsession) are managed by Home Assistant.
        """
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            await asyncio.sleep(0.25)
        self._session = None

    async def _request(self, url: str, params: dict[str, str] | None = None) -> dict:
        """Make an API request."""
        self._check_rate_limit()

        session = await self._get_session()
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                try:
                    return await response.json()
                except (ValueError, aiohttp.ContentTypeError) as e:
                    _LOGGER.error(
                        "Invalid JSON response from API: %s. Response text: %s",
                        e,
                        await response.text()[:500],
                    )
                    raise CFLAPIError(f"Invalid JSON response: {e}") from e
        finally:
            self._record_api_call()

    async def search_stations(self, query: str) -> list[Station]:
        """Search for stations by querying departures from Luxembourg hub.

        This approach discovers all stations that have train service by querying
        departures from Luxembourg and extracting all calling points. This ensures
        we include the main Luxembourg station which the location.nearbystops
        endpoint doesn't return.
        """
        if self._cached_stations_ is None:
            await self._fetch_all_train_stations()

        if not query:
            return self._cached_stations_

        query_lower = query.lower()
        return [s for s in self._cached_stations_ if query_lower in s.name.lower()]

    async def _fetch_all_train_stations(self) -> None:
        """Fetch all train stations from departures API.

        Queries departures from Luxembourg hub station and extracts all unique stations
        from the journey calling points.
        """
        import datetime

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = "08:00"

        url = f"{self.BASE_URL}/departureBoard"
        params = {
            "accessId": self._api_key,
            "id": self.LUXEMBOURG_HUB_STATION_ID,
            "lang": "en",
            "format": "json",
            "passlist": "1",
            "duration": "120",
            "date": date_str,
            "time": time_str,
        }

        data = await self._request(url, params)

        stations_map: dict[str, Station] = {}

        departures = data.get("Departure", [])
        if isinstance(departures, dict):
            departures = [departures]

        for dep in departures:
            stops = dep.get("Stops", {}).get("Stop", [])
            if isinstance(stops, dict):
                stops = [stops]

            for stop in stops:
                ext_id = stop.get("extId", "")
                if not ext_id:
                    continue

                name = stop.get("name", "")
                if not name:
                    continue

                if ext_id not in stations_map:
                    lat = float(stop.get("lat", 0))
                    lon = float(stop.get("lon", 0))
                    stations_map[ext_id] = Station(
                        id=ext_id,
                        name=_clean_station_name(name),
                        lon=lon,
                        lat=lat,
                    )

        self._cached_stations_ = sorted(
            stations_map.values(),
            key=lambda s: s.name,
        )
        _LOGGER.debug(
            "Fetched %d train stations from departures API",
            len(self._cached_stations_),
        )

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
            "duration": str(
                time_window if time_window > 0 else 1200
            ),  # Request departures within time_window minutes (0 = all departures = 20h max)
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
                    delay_delta = (actual_time_parsed - sched_time).total_seconds() / 60
                    if delay_delta < -720:
                        delay_delta += 1440
                    elif delay_delta > 720:
                        delay_delta -= 1440
                    delay_minutes = int(delay_delta)
                except ValueError:
                    delay_minutes = 0

            # Check if cancelled
            is_cancelled = dep.get("JourneyStatus") == "C" or not dep.get(
                "reachable", True
            )

            # Get direction
            direction = _clean_station_name(dep.get("direction", ""))

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
                    stop_names.append(_clean_station_name(stop_name))

            departures.append(
                Departure(
                    station_id=station_id,
                    scheduled_departure=scheduled_time,
                    expected_departure=actual_time,
                    platform=_normalize_platform(dep.get("platform")),
                    line=product_name.split()[-1] if product_name else "",
                    direction=direction,
                    operator=operator,
                    train_number=product_name,
                    is_cancelled=is_cancelled,
                    delay_minutes=delay_minutes,
                    calling_points=stop_names,
                    stop_ids=stop_ids,
                    journey_ref="",
                )
            )

        return self._filter_by_time_window(departures, time_window)

    def _filter_by_time_window(
        self, departures: list[Departure], time_window: int
    ) -> list[Departure]:
        """Filter departures by time window (minutes from now).

        Handles midnight crossing (e.g., current 23:50, departure 00:10 = +20 min).
        Note: API returns times in Luxembourg local time (CET/CEST).
        """
        if time_window <= 0:
            return departures

        now = _get_luxembourg_now()
        now_minutes = now.hour * 60 + now.minute

        _LOGGER.debug(
            "Filtering by time window: now=%s (%d min), window=%d min",
            now.strftime("%H:%M"),
            now_minutes,
            time_window,
        )

        filtered = []
        for dep in departures:
            try:
                dep_time = datetime.strptime(dep.scheduled_departure, "%H:%M")
                dep_minutes = dep_time.hour * 60 + dep_time.minute

                diff = dep_minutes - now_minutes
                if diff < -60:
                    diff += 1440

                if 0 <= diff <= time_window:
                    filtered.append(dep)
                    _LOGGER.debug(
                        "Train %s at %s is within window (+%d min)",
                        dep.train_number,
                        dep.scheduled_departure,
                        diff,
                    )
                else:
                    _LOGGER.debug(
                        "Train %s at %s filtered out (diff=%d, window=%d)",
                        dep.train_number,
                        dep.scheduled_departure,
                        diff,
                        time_window,
                    )
            except (ValueError, TypeError):
                filtered.append(dep)

        _LOGGER.debug(
            "Time window filter: %d/%d departures included",
            len(filtered),
            len(departures),
        )
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
                        "name": _clean_station_name(stop.get("name", "")),
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
        return [
            _clean_station_name(stop.get("name", ""))
            for stop in stops
            if stop.get("name")
        ]
