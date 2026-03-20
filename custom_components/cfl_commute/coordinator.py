"""Data update coordinator for CFL Commute integration."""

import asyncio
import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CFLCommuteClient, Departure
from .const import (
    CONF_MAJOR_THRESHOLD,
    CONF_MINOR_THRESHOLD,
    CONF_NIGHT_UPDATES,
    CONF_SEVERE_THRESHOLD,
    CONF_TIME_WINDOW,
    DEFAULT_MAJOR_THRESHOLD,
    DEFAULT_MINOR_THRESHOLD,
    DEFAULT_SEVERE_THRESHOLD,
    DOMAIN,
    UPDATE_INTERVAL_PEAK,
    UPDATE_INTERVAL_OFFPEAK,
    UPDATE_INTERVAL_NIGHT,
    PEAK_HOURS,
    NIGHT_HOURS,
)

_LOGGER = logging.getLogger(__name__)


class CFLCommuteDataUpdateCoordinator(DataUpdateCoordinator[list[Departure]]):
    """Coordinator to manage CFL API data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: CFLCommuteClient,
        origin_id: str,
        origin_name: str,
        destination_id: str,
        destination_name: str,
        config: dict,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.origin_id = origin_id
        self.origin_name = origin_name
        self.destination_id = destination_id
        self.destination_name = destination_name
        self.config = config
        self.time_window = config.get(CONF_TIME_WINDOW, 60)
        self.night_updates_enabled = config.get(CONF_NIGHT_UPDATES, False)
        self._update_lock = asyncio.Lock()

        minor_threshold = config.get(CONF_MINOR_THRESHOLD, DEFAULT_MINOR_THRESHOLD)
        major_threshold = config.get(CONF_MAJOR_THRESHOLD, DEFAULT_MAJOR_THRESHOLD)
        severe_threshold = config.get(CONF_SEVERE_THRESHOLD, DEFAULT_SEVERE_THRESHOLD)

        if not (minor_threshold <= major_threshold <= severe_threshold):
            _LOGGER.warning(
                "Invalid threshold hierarchy: minor=%d, major=%d, severe=%d. "
                "Resetting to defaults.",
                minor_threshold,
                major_threshold,
                severe_threshold,
            )
            minor_threshold = DEFAULT_MINOR_THRESHOLD
            major_threshold = DEFAULT_MAJOR_THRESHOLD
            severe_threshold = DEFAULT_SEVERE_THRESHOLD

        self.minor_threshold = minor_threshold
        self.major_threshold = major_threshold
        self.severe_threshold = severe_threshold

        update_interval = self._get_update_interval()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{origin_id}_{destination_id}",
            update_interval=update_interval,
        )

    def _get_update_interval(self) -> timedelta:
        """Get update interval based on current time."""
        now = dt_util.now()
        current_hour = now.hour

        # Check if in night time
        night_start, night_end = NIGHT_HOURS
        if night_start <= current_hour or current_hour < night_end:
            if not self.night_updates_enabled:
                _LOGGER.debug("Night updates disabled, using 60min interval")
                return timedelta(minutes=60)
            return timedelta(seconds=UPDATE_INTERVAL_NIGHT)

        # Check if in peak hours
        for peak_start, peak_end in PEAK_HOURS:
            if peak_start <= current_hour < peak_end:
                return timedelta(seconds=UPDATE_INTERVAL_PEAK)

        # Off-peak hours
        return timedelta(seconds=UPDATE_INTERVAL_OFFPEAK)

    def _filter_departed_trains(
        self, departures: list[Departure], now: datetime
    ) -> list[Departure]:
        """Filter out departed trains from the list.

        Keeps trains that:
        - Have not departed yet (scheduled time > current time)
        - Are cancelled (cancelled trains should remain visible)
        - Have not exceeded the grace period (2 minutes)

        Args:
            departures: List of departures to filter
            now: Current datetime

        Returns:
            Filtered list of departures
        """
        if not departures:
            return departures

        grace_period_seconds = 120
        filtered = []

        for dep in departures:
            if dep.is_cancelled:
                filtered.append(dep)
                continue

            if "expected_departure" in dep.__dict__ and dep.expected_departure:
                try:
                    dep_time = datetime.strptime(dep.expected_departure, "%H:%M:%S")
                    dep_datetime = now.replace(
                        hour=dep_time.hour,
                        minute=dep_time.minute,
                        second=dep_time.second,
                    )
                    if dep_datetime <= now + timedelta(seconds=grace_period_seconds):
                        filtered.append(dep)
                except ValueError:
                    filtered.append(dep)
            elif dep.scheduled_departure:
                try:
                    dep_time = datetime.strptime(dep.scheduled_departure, "%H:%M:%S")
                    dep_datetime = now.replace(
                        hour=dep_time.hour,
                        minute=dep_time.minute,
                        second=dep_time.second,
                    )
                    if dep_datetime <= now + timedelta(seconds=grace_period_seconds):
                        filtered.append(dep)
                except ValueError:
                    filtered.append(dep)
            else:
                filtered.append(dep)

        return filtered

    async def _async_update_data(self) -> list[Departure]:
        """Fetch data from CFL API."""
        try:
            now = dt_util.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")

            _LOGGER.debug(
                "Fetching departures from %s to %s at %s %s",
                self.origin_name,
                self.destination_name,
                date_str,
                time_str,
            )

            # Fetch departures with passlist to get all stops
            departures = await self.api.get_departures(
                self.origin_id,
                time_window=self.time_window,
                date=date_str,
                time=time_str,
            )

            _LOGGER.debug("API returned %d departures", len(departures))

            # Filter departures by destination (using name matching for robustness)
            filtered_departures = []
            for dep in departures:
                # Check if destination name is in the journey's calling points
                calling_point_names = [name.lower() for name in dep.calling_points]
                dest_name_lower = self.destination_name.lower()
                if any(dest_name_lower in cp for cp in calling_point_names):
                    _LOGGER.debug(
                        "Departure %s to %s passes through %s (calling points: %s)",
                        dep.train_number,
                        dep.direction,
                        self.destination_name,
                        dep.calling_points,
                    )
                    filtered_departures.append(dep)

            _LOGGER.debug(
                "%d departures matched destination filter (looking for: '%s')",
                len(filtered_departures),
                self.destination_name,
            )

            if not filtered_departures and departures:
                _LOGGER.debug(
                    "No departures matched. First departure calling points: %s",
                    departures[0].calling_points if departures else [],
                )

            # Filter departed trains
            filtered_departures = self._filter_departed_trains(filtered_departures, now)

            # Update interval with lock
            async with self._update_lock:
                self.update_interval = self._get_update_interval()

            return filtered_departures

        except Exception as err:
            error_msg = str(err)
            if "quota" in error_msg.lower() or "QuotaExceeded" in error_msg:
                _LOGGER.error(
                    "CFL mobiliteit.lu API quota exceeded. "
                    "Hourly limit reached (500 requests). "
                    "Consider requesting increased quota from opendata-api@atp.etat.lu"
                )
            else:
                _LOGGER.error("Error fetching CFL data: %s", err)

            raise UpdateFailed(f"Failed to fetch data: {err}") from err
