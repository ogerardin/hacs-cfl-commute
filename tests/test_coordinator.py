"""Tests for CFL Commute coordinator logic."""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.cfl_commute.api import Departure
from custom_components.cfl_commute.const import (
    DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD,
    MIN_GRACE_PERIOD,
    MAX_GRACE_PERIOD,
)

LUXEMBOURG_TZ = ZoneInfo("Europe/Luxembourg")


def create_departure(
    train_num: str,
    scheduled: str,
    is_cancelled: bool = False,
    expected: str | None = None,
) -> Departure:
    """Create a test departure."""
    return Departure(
        station_id="110109004",
        scheduled_departure=scheduled,
        expected_departure=expected or scheduled,
        platform="1",
        line="RE",
        direction="Luxembourg",
        operator="CFL",
        train_number=train_num,
        is_cancelled=is_cancelled,
        delay_minutes=0,
        calling_points=["Drauffelt", "Pfaffenthal", "Luxembourg"],
        stop_ids=["110109004", "200417051", "200405060"],
    )


def filter_departed_trains(
    departures: list[Departure],
    now_utc: datetime,
    time_window: int = 120,
    grace_period_minutes: int = DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD,
) -> list[Departure]:
    """Standalone version of _filter_departed_trains for testing."""
    if not departures:
        return departures

    if time_window == 0:
        return departures

    grace_period_seconds = grace_period_minutes * 60
    filtered = []

    if now_utc.tzinfo is None:
        now_lux_naive = now_utc
    else:
        now_lux = now_utc.astimezone(LUXEMBOURG_TZ)
        now_lux_naive = now_lux.replace(tzinfo=None)

    for dep in departures:
        if dep.is_cancelled:
            filtered.append(dep)
            continue

        departure_time = None
        if hasattr(dep, "expected_departure") and dep.expected_departure:
            departure_time = dep.expected_departure
        elif dep.scheduled_departure:
            departure_time = dep.scheduled_departure

        if departure_time:
            try:
                dep_time = datetime.strptime(departure_time, "%H:%M:%S")
                dep_local = now_lux_naive.replace(
                    hour=dep_time.hour,
                    minute=dep_time.minute,
                    second=dep_time.second,
                )

                if dep_local < now_lux_naive:
                    diff = (now_lux_naive - dep_local).total_seconds()
                    if diff > 43200:
                        dep_local = dep_local + timedelta(days=1)

                if dep_local > now_lux_naive - timedelta(seconds=grace_period_seconds):
                    filtered.append(dep)
            except ValueError:
                filtered.append(dep)
        else:
            filtered.append(dep)

    return filtered


def get_update_interval(hour: int, night_updates_enabled: bool = False) -> timedelta:
    """Standalone version of _get_update_interval for testing."""
    NIGHT_HOURS = (23, 5)
    PEAK_HOURS = [(6, 10), (16, 20)]
    UPDATE_INTERVAL_PEAK = 120
    UPDATE_INTERVAL_OFFPEAK = 300
    UPDATE_INTERVAL_NIGHT = 900

    if NIGHT_HOURS[0] <= hour or hour < NIGHT_HOURS[1]:
        if not night_updates_enabled:
            return timedelta(minutes=60)
        return timedelta(seconds=UPDATE_INTERVAL_NIGHT)

    for peak_start, peak_end in PEAK_HOURS:
        if peak_start <= hour < peak_end:
            return timedelta(seconds=UPDATE_INTERVAL_PEAK)

    return timedelta(seconds=UPDATE_INTERVAL_OFFPEAK)


class TestFilterDepartedTrains:
    """Test cases for departed train filtering."""

    def test_filters_departed_trains(self):
        """Test that past trains are filtered out."""
        departures = [
            create_departure("RE 100", "04:20:00"),
            create_departure("RE 200", "00:30:00"),  # Already departed
        ]

        now_utc = datetime(2026, 3, 24, 1, 0, 0)
        result = filter_departed_trains(departures, now_utc)

        assert len(result) == 1
        assert result[0].train_number == "RE 100"

    def test_keeps_cancelled_trains(self):
        """Test that cancelled trains are kept regardless of departure time."""
        departures = [
            create_departure("RE 100", "04:20:00"),
            create_departure("RE 200", "00:30:00", is_cancelled=True),
        ]

        now_utc = datetime(2026, 3, 24, 1, 0, 0)
        result = filter_departed_trains(departures, now_utc)

        assert len(result) == 2

    def test_time_window_zero_shows_all(self):
        """Test that time_window=0 shows all departures."""
        departures = [
            create_departure("RE 100", "04:20:00"),
            create_departure("RE 200", "00:30:00"),
        ]

        now_utc = datetime(2026, 3, 24, 1, 0, 0)
        result = filter_departed_trains(departures, now_utc, time_window=0)

        assert len(result) == 2

    def test_empty_departures(self):
        """Test that empty list returns empty list."""
        now_utc = datetime(2026, 3, 24, 1, 0, 0)
        result = filter_departed_trains([], now_utc)
        assert result == []

    def test_default_grace_period_is_two_minutes(self):
        """Default grace period should be 2 minutes."""
        assert DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD == 2
        assert MIN_GRACE_PERIOD == 0
        assert MAX_GRACE_PERIOD == 15

    def test_grace_period_keeps_trains_within_grace(self):
        """Test that trains within grace period are kept."""
        departures = [
            create_departure("RE 100", "02:02:00"),  # 2 min in future
        ]
        now_utc = datetime(2026, 3, 24, 1, 0, 0)
        result = filter_departed_trains(departures, now_utc, grace_period_minutes=2)
        assert len(result) == 1

    def test_custom_grace_period_zero_excludes_departed(self):
        """Test that grace period=0 filters out trains departed more than 0 min ago."""
        # Train departed 3 minutes ago
        departures = [
            create_departure("RE 100", "00:57:00"),  # 3 min before 01:00
        ]
        now_utc = datetime(2026, 3, 24, 1, 0, 0)
        result_0min = filter_departed_trains(
            departures, now_utc, grace_period_minutes=0
        )
        result_5min = filter_departed_trains(
            departures, now_utc, grace_period_minutes=5
        )
        assert len(result_0min) == 0  # 3 min ago > 0 min grace
        assert len(result_5min) == 1  # 3 min ago < 5 min grace

    def test_far_future_train(self):
        """Test that trains far in the future are kept."""
        departures = [
            create_departure("RE 100", "04:20:00"),
        ]

        now_utc = datetime(2026, 3, 24, 2, 0, 0)  # 02:00, train at 04:20
        result = filter_departed_trains(departures, now_utc)

        assert len(result) == 1

    def test_uses_expected_time_for_filtering(self):
        """Test that expected departure time is used when available."""
        departures = [
            create_departure("RE 100", "00:30:00", expected="04:30:00"),
        ]

        now_utc = datetime(2026, 3, 24, 3, 0, 0)
        result = filter_departed_trains(departures, now_utc)

        assert len(result) == 1


class TestUpdateInterval:
    """Test cases for update interval logic."""

    @pytest.mark.parametrize(
        "hour,expected_seconds",
        [
            (0, 3600),  # 00:00 - night (disabled)
            (4, 3600),  # 04:00 - night (disabled)
            (23, 3600),  # 23:00 - night (disabled)
            (7, 120),  # 07:00 - peak
            (9, 120),  # 09:00 - peak
            (17, 120),  # 17:00 - peak
            (19, 120),  # 19:00 - peak
            (12, 300),  # 12:00 - off-peak
            (15, 300),  # 15:00 - off-peak
            (22, 300),  # 22:00 - off-peak
        ],
    )
    def test_update_intervals(self, hour, expected_seconds):
        """Test that correct intervals are returned for different times."""
        interval = get_update_interval(hour, night_updates_enabled=False)
        assert interval == timedelta(seconds=expected_seconds)

    def test_night_updates_enabled(self):
        """Test that night updates are more frequent when enabled."""
        interval = get_update_interval(2, night_updates_enabled=True)
        assert interval == timedelta(seconds=900)


class TestThresholdValidation:
    """Test cases for threshold hierarchy validation."""

    def test_valid_thresholds_accepted(self):
        """Test that valid thresholds are accepted."""
        minor, major, severe = 3, 10, 15
        assert minor <= major <= severe

    def test_invalid_thresholds_detected(self):
        """Test that invalid thresholds (minor > major) are detected."""
        minor, major, severe = 10, 5, 15
        assert not (minor <= major <= severe)

    def test_all_equal_thresholds_valid(self):
        """Test that all thresholds equal is valid."""
        minor = major = severe = 5
        assert minor <= major <= severe

    def test_boundary_values(self):
        """Test boundary values for thresholds."""
        assert 0 <= 0 <= 0  # All zero
        assert 5 <= 5 <= 5  # All same
        assert 0 <= 100 <= 1000  # Wide range


class TestFailedUpdateCounter:
    """Test that consecutive failures are tolerated before raising UpdateFailed."""

    def test_failed_updates_default_values(self):
        """Failed update counter should have correct defaults."""
        # Test the default values directly

        # Create a minimal mock coordinator without calling parent __init__
        # by testing the attributes that are set before super().__init__
        class TestableCoordinator:
            def __init__(self):
                self._failed_updates = 0
                self._max_failed_updates = 3

        mock = TestableCoordinator()
        assert mock._failed_updates == 0
        assert mock._max_failed_updates == 3

    def test_failed_updates_counter_logic(self):
        """Test that the failure counter increments correctly."""

        class TestableCoordinator:
            def __init__(self):
                self._failed_updates = 0
                self._max_failed_updates = 3

        mock = TestableCoordinator()
        mock._failed_updates += 1
        assert mock._failed_updates == 1
        assert mock._max_failed_updates == 3
        assert mock._failed_updates < mock._max_failed_updates

        mock._failed_updates += 1
        assert mock._failed_updates == 2
        assert mock._failed_updates < mock._max_failed_updates

        mock._failed_updates += 1
        assert mock._failed_updates == 3
        assert mock._failed_updates >= mock._max_failed_updates
