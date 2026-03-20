"""Tests for sensor logic."""

from custom_components.cfl_commute.const import (
    STATUS_NORMAL,
    STATUS_MINOR,
    STATUS_MAJOR,
    STATUS_SEVERE,
    STATUS_CRITICAL,
)


def calculate_status(departures, minor_threshold, major_threshold, severe_threshold):
    """Extract status calculation logic for testing."""
    if not departures:
        return STATUS_NORMAL

    if any(d.get("is_cancelled") for d in departures):
        return STATUS_CRITICAL

    max_delay = max((d.get("delay_minutes", 0) for d in departures), default=0)

    if max_delay >= severe_threshold:
        return STATUS_SEVERE
    elif max_delay >= major_threshold:
        return STATUS_MAJOR
    elif max_delay >= minor_threshold:
        return STATUS_MINOR

    return STATUS_NORMAL


def calculate_summary(departures, minor_threshold):
    """Extract summary calculation logic for testing."""
    if not departures:
        return "No trains"

    on_time = sum(
        1
        for d in departures
        if not d.get("is_cancelled") and d.get("delay_minutes", 0) < minor_threshold
    )
    delayed = sum(
        1
        for d in departures
        if not d.get("is_cancelled") and d.get("delay_minutes", 0) >= minor_threshold
    )
    cancelled = sum(1 for d in departures if d.get("is_cancelled"))

    parts = []
    if on_time:
        parts.append(f"{on_time} on time")
    if delayed:
        parts.append(f"{delayed} delayed")
    if cancelled:
        parts.append(f"{cancelled} cancelled")

    return ", ".join(parts) if parts else "No trains"


class TestStatusHierarchy:
    """Test cases for status hierarchy."""

    def test_no_trains_returns_normal(self):
        """Test that no trains returns Normal status."""
        result = calculate_status([], 3, 10, 15)
        assert result == STATUS_NORMAL

    def test_on_time_returns_normal(self):
        """Test that on-time train returns Normal status."""
        departures = [{"is_cancelled": False, "delay_minutes": 0}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_NORMAL

    def test_delay_below_minor_threshold_returns_normal(self):
        """Test delay below minor threshold returns Normal."""
        departures = [{"is_cancelled": False, "delay_minutes": 2}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_NORMAL

    def test_delay_at_minor_threshold_returns_minor(self):
        """Test delay at minor threshold returns Minor Delays."""
        departures = [{"is_cancelled": False, "delay_minutes": 3}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_MINOR

    def test_delay_above_minor_returns_minor(self):
        """Test delay above minor threshold returns Minor."""
        departures = [{"is_cancelled": False, "delay_minutes": 5}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_MINOR

    def test_delay_at_major_threshold_returns_major(self):
        """Test delay at major threshold returns Major Delays."""
        departures = [{"is_cancelled": False, "delay_minutes": 10}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_MAJOR

    def test_delay_above_major_returns_major(self):
        """Test delay above major threshold returns Major."""
        departures = [{"is_cancelled": False, "delay_minutes": 12}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_MAJOR

    def test_delay_at_severe_threshold_returns_severe(self):
        """Test delay at severe threshold returns Severe Disruption."""
        departures = [{"is_cancelled": False, "delay_minutes": 15}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_SEVERE

    def test_delay_above_severe_returns_severe(self):
        """Test delay above severe threshold returns Severe."""
        departures = [{"is_cancelled": False, "delay_minutes": 20}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_SEVERE

    def test_cancelled_returns_critical(self):
        """Test that cancelled train returns Critical status."""
        departures = [{"is_cancelled": True, "delay_minutes": 0}]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_CRITICAL

    def test_cancelled_overrides_delay(self):
        """Test that cancelled overrides any delay."""
        departures = [
            {"is_cancelled": True, "delay_minutes": 0},
            {"is_cancelled": False, "delay_minutes": 2},
        ]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_CRITICAL

    def test_max_delay_from_multiple_trains(self):
        """Test that max delay is used from multiple trains."""
        departures = [
            {"is_cancelled": False, "delay_minutes": 2},
            {"is_cancelled": False, "delay_minutes": 12},
            {"is_cancelled": False, "delay_minutes": 5},
        ]
        result = calculate_status(departures, 3, 10, 15)
        assert result == STATUS_MAJOR


class TestSummaryCalculation:
    """Test cases for summary string generation."""

    def test_no_trains_returns_no_trains(self):
        """Test that no trains returns 'No trains'."""
        result = calculate_summary([], 3)
        assert result == "No trains"

    def test_single_on_time_returns_on_time(self):
        """Test single on-time train."""
        departures = [{"is_cancelled": False, "delay_minutes": 0}]
        result = calculate_summary(departures, 3)
        assert result == "1 on time"

    def test_single_delayed_returns_delayed(self):
        """Test single delayed train."""
        departures = [{"is_cancelled": False, "delay_minutes": 5}]
        result = calculate_summary(departures, 3)
        assert result == "1 delayed"

    def test_single_cancelled_returns_cancelled(self):
        """Test single cancelled train."""
        departures = [{"is_cancelled": True, "delay_minutes": 0}]
        result = calculate_summary(departures, 3)
        assert result == "1 cancelled"

    def test_multiple_on_time(self):
        """Test multiple on-time trains."""
        departures = [
            {"is_cancelled": False, "delay_minutes": 0},
            {"is_cancelled": False, "delay_minutes": 1},
        ]
        result = calculate_summary(departures, 3)
        assert result == "2 on time"

    def test_mixed_on_time_and_delayed(self):
        """Test mixed on-time and delayed trains."""
        departures = [
            {"is_cancelled": False, "delay_minutes": 0},
            {"is_cancelled": False, "delay_minutes": 5},
        ]
        result = calculate_summary(departures, 3)
        assert result == "1 on time, 1 delayed"

    def test_all_three_categories(self):
        """Test all three categories present."""
        departures = [
            {"is_cancelled": False, "delay_minutes": 0},
            {"is_cancelled": False, "delay_minutes": 5},
            {"is_cancelled": True, "delay_minutes": 0},
        ]
        result = calculate_summary(departures, 3)
        assert result == "1 on time, 1 delayed, 1 cancelled"

    def test_threshold_respected(self):
        """Test that minor threshold is respected."""
        # At threshold (3) should be delayed
        departures = [{"is_cancelled": False, "delay_minutes": 3}]
        result = calculate_summary(departures, 3)
        assert result == "1 delayed"

        # Below threshold should be on time
        departures = [{"is_cancelled": False, "delay_minutes": 2}]
        result = calculate_summary(departures, 3)
        assert result == "1 on time"


class TestCustomThresholds:
    """Test with custom threshold values."""

    def test_custom_minor_threshold(self):
        """Test with custom minor threshold."""
        departures = [{"is_cancelled": False, "delay_minutes": 5}]
        # With threshold at 5, 5 minutes is at threshold = delayed
        result = calculate_status(departures, 5, 10, 15)
        assert result == STATUS_MINOR

    def test_custom_major_threshold(self):
        """Test with custom major threshold."""
        departures = [{"is_cancelled": False, "delay_minutes": 8}]
        # With major at 8, 8 minutes is at threshold = major
        result = calculate_status(departures, 3, 8, 15)
        assert result == STATUS_MAJOR
