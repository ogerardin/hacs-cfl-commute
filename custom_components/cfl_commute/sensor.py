"""Sensor entities for CFL Commute."""

from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Departure
from .const import (
    CONF_COMMUTE_NAME,
    CONF_DESTINATION,
    CONF_MAJOR_THRESHOLD,
    CONF_MINOR_THRESHOLD,
    CONF_NUM_TRAINS,
    CONF_ORIGIN,
    CONF_SEVERE_THRESHOLD,
    DEFAULT_NUM_TRAINS,
    DOMAIN,
    STATUS_CRITICAL,
    STATUS_MAJOR,
    STATUS_MINOR,
    STATUS_NORMAL,
    STATUS_SEVERE,
    TRAIN_CANCELLED,
    TRAIN_DELAYED,
    TRAIN_NO_TRAIN,
    TRAIN_ON_TIME,
)
from .coordinator import CFLCommuteDataUpdateCoordinator

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CFL Commute sensors."""
    # Get coordinator from hass.data
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry_data["coordinator"]

    commute_name = config_entry.data.get(CONF_COMMUTE_NAME, "cfl_commute")
    origin = config_entry.data.get(CONF_ORIGIN, {})
    destination = config_entry.data.get(CONF_DESTINATION, {})
    num_trains = config_entry.data.get(CONF_NUM_TRAINS, DEFAULT_NUM_TRAINS)
    minor_threshold = config_entry.data.get(CONF_MINOR_THRESHOLD, 3)
    major_threshold = config_entry.data.get(CONF_MAJOR_THRESHOLD, 10)
    severe_threshold = config_entry.data.get(CONF_SEVERE_THRESHOLD, 15)

    sensors = [
        CFLCommuteSummarySensor(
            coordinator=coordinator,
            commute_name=commute_name,
            origin=origin,
            destination=destination,
            num_trains=num_trains,
            minor_threshold=minor_threshold,
            major_threshold=major_threshold,
            severe_threshold=severe_threshold,
        ),
        CFLCommuteStatusSensor(
            coordinator=coordinator,
            commute_name=commute_name,
            origin=origin,
            destination=destination,
            num_trains=num_trains,
            minor_threshold=minor_threshold,
            major_threshold=major_threshold,
            severe_threshold=severe_threshold,
        ),
        CFLCommuteNextTrainSensor(
            coordinator=coordinator,
            commute_name=commute_name,
            origin=origin,
            destination=destination,
            num_trains=num_trains,
            minor_threshold=minor_threshold,
            major_threshold=major_threshold,
            severe_threshold=severe_threshold,
        ),
    ]

    for i in range(1, num_trains + 1):
        sensors.append(
            CFLCommuteTrainSensor(
                coordinator=coordinator,
                commute_name=commute_name,
                origin=origin,
                destination=destination,
                num_trains=num_trains,
                minor_threshold=minor_threshold,
                major_threshold=major_threshold,
                severe_threshold=severe_threshold,
                train_number=i,
            )
        )

    async_add_entities(sensors)


class CFLCommuteBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for CFL Commute."""

    def __init__(
        self,
        coordinator: CFLCommuteDataUpdateCoordinator,
        commute_name: str,
        origin: dict,
        destination: dict,
        num_trains: int,
        minor_threshold: int,
        major_threshold: int,
        severe_threshold: int,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._commute_name = commute_name
        self._origin_name = origin.get("name", "")
        self._destination_name = destination.get("name", "")
        self._origin_id = origin.get("id", "")
        self._destination_id = destination.get("id", "")
        self._num_trains = num_trains
        self._minor_threshold = minor_threshold
        self._major_threshold = major_threshold
        self._severe_threshold = severe_threshold

    @property
    def departures(self) -> list[Departure]:
        """Return departures from coordinator data."""
        return self.coordinator.data if self.coordinator.data else []

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "origin": self._origin_name,
            "destination": self._destination_name,
            "origin_id": self._origin_id,
            "destination_id": self._destination_id,
        }


class CFLCommuteSummarySensor(CFLCommuteBaseSensor):
    """Summary sensor showing overall commute status."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._commute_name} Summary"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._commute_name}_summary"

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        if not self.departures:
            return "No trains"

        on_time = sum(
            1
            for d in self.departures
            if not d.is_cancelled and d.delay_minutes < self._minor_threshold
        )
        delayed = sum(
            1
            for d in self.departures
            if not d.is_cancelled and d.delay_minutes >= self._minor_threshold
        )
        cancelled = sum(1 for d in self.departures if d.is_cancelled)

        parts = []
        if on_time:
            parts.append(f"{on_time} on time")
        if delayed:
            parts.append(f"{delayed} delayed")
        if cancelled:
            parts.append(f"{cancelled} cancelled")

        return ", ".join(parts) if parts else "No trains"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes

        on_time = sum(
            1
            for d in self.departures
            if not d.is_cancelled and d.delay_minutes < self._minor_threshold
        )
        delayed = sum(
            1
            for d in self.departures
            if not d.is_cancelled and d.delay_minutes >= self._minor_threshold
        )
        cancelled = sum(1 for d in self.departures if d.is_cancelled)

        attrs.update(
            {
                "on_time_count": on_time,
                "delayed_count": delayed,
                "cancelled_count": cancelled,
                "total_trains": len(self.departures),
                "all_trains": [
                    {
                        "departure_time": d.expected_departure,
                        "scheduled_departure": d.scheduled_departure,
                        "delay_minutes": d.delay_minutes,
                        "is_cancelled": d.is_cancelled,
                        "platform": d.platform,
                        "direction": d.direction,
                    }
                    for d in self.departures
                ],
            }
        )

        return attrs


class CFLCommuteStatusSensor(CFLCommuteBaseSensor):
    """Status sensor with hierarchical status."""

    @property
    def name(self) -> str:
        return f"{self._commute_name} Status"

    @property
    def unique_id(self) -> str:
        return f"{self._commute_name}_status"

    @property
    def state(self) -> StateType:
        if not self.departures:
            return STATUS_NORMAL

        if any(d.is_cancelled for d in self.departures):
            return STATUS_CRITICAL

        max_delay = max((d.delay_minutes for d in self.departures), default=0)

        if max_delay >= self._severe_threshold:
            return STATUS_SEVERE
        elif max_delay >= self._major_threshold:
            return STATUS_MAJOR
        elif max_delay >= self._minor_threshold:
            return STATUS_MINOR

        return STATUS_NORMAL

    @property
    def icon(self) -> str:
        state = self.state
        if state == STATUS_CRITICAL:
            return "mdi:alert-octagon"
        elif state == STATUS_SEVERE:
            return "mdi:alert-circle"
        elif state == STATUS_MAJOR:
            return "mdi:clock-alert"
        elif state == STATUS_MINOR:
            return "mdi:train-variant"
        return "mdi:train"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes

        cancelled = sum(1 for d in self.departures if d.is_cancelled)
        delayed = sum(
            1
            for d in self.departures
            if not d.is_cancelled and d.delay_minutes >= self._minor_threshold
        )
        max_delay = max((d.delay_minutes for d in self.departures), default=0)

        attrs.update(
            {
                "total_trains": len(self.departures),
                "on_time_count": len(self.departures) - cancelled - delayed,
                "minor_delays_count": delayed,
                "major_delays_count": sum(
                    1
                    for d in self.departures
                    if not d.is_cancelled and d.delay_minutes >= self._major_threshold
                ),
                "cancelled_count": cancelled,
                "max_delay_minutes": max_delay,
            }
        )

        return attrs


class CFLCommuteNextTrainSensor(CFLCommuteBaseSensor):
    """Next train sensor."""

    @property
    def name(self) -> str:
        return f"{self._commute_name} Next Train"

    @property
    def unique_id(self) -> str:
        return f"{self._commute_name}_next_train"

    @property
    def state(self) -> StateType:
        if not self.departures:
            return TRAIN_NO_TRAIN

        train = self.departures[0]
        if train.is_cancelled:
            return TRAIN_CANCELLED
        elif train.delay_minutes > 0:
            return TRAIN_DELAYED
        return TRAIN_ON_TIME

    @property
    def icon(self) -> str:
        state = self.state
        if state == TRAIN_CANCELLED:
            return "mdi:alert-circle"
        elif state == TRAIN_DELAYED:
            return "mdi:train-variant"
        return "mdi:train-car"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes

        if self.departures:
            train = self.departures[0]
            attrs.update(
                {
                    "train_number": 1,
                    "total_trains": len(self.departures),
                    "departure_time": train.expected_departure,
                    "scheduled_departure": train.scheduled_departure,
                    "expected_departure": train.expected_departure,
                    "platform": train.platform,
                    "operator": train.operator,
                    "train_id": train.train_number,
                    "delay_minutes": train.delay_minutes,
                    "is_cancelled": train.is_cancelled,
                    "calling_points": train.calling_points,
                    "direction": train.direction,
                }
            )

        return attrs


class CFLCommuteTrainSensor(CFLCommuteBaseSensor):
    """Individual train sensor (train_1, train_2, etc.)."""

    def __init__(self, *args, train_number: int, **kwargs):
        """Initialize train sensor."""
        super().__init__(*args, **kwargs)
        self._train_number = train_number

    @property
    def name(self) -> str:
        return f"{self._commute_name} Train {self._train_number}"

    @property
    def unique_id(self) -> str:
        return f"{self._commute_name}_train_{self._train_number}"

    @property
    def state(self) -> StateType:
        if len(self.departures) < self._train_number:
            return TRAIN_NO_TRAIN

        train = self.departures[self._train_number - 1]
        if train.is_cancelled:
            return TRAIN_CANCELLED
        elif train.delay_minutes > 0:
            return TRAIN_DELAYED
        return TRAIN_ON_TIME

    @property
    def icon(self) -> str:
        state = self.state
        if state == TRAIN_CANCELLED:
            return "mdi:alert-circle"
        elif state == TRAIN_DELAYED:
            return "mdi:train-variant"
        elif self._train_number == 1:
            return "mdi:train-car"
        return "mdi:train"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes

        if len(self.departures) >= self._train_number:
            train = self.departures[self._train_number - 1]
            attrs.update(
                {
                    "train_number": self._train_number,
                    "total_trains": len(self.departures),
                    "departure_time": train.expected_departure,
                    "scheduled_departure": train.scheduled_departure,
                    "expected_departure": train.expected_departure,
                    "platform": train.platform,
                    "operator": train.operator,
                    "train_id": train.train_number,
                    "delay_minutes": train.delay_minutes,
                    "is_cancelled": train.is_cancelled,
                    "calling_points": train.calling_points,
                    "direction": train.direction,
                }
            )

        return attrs
