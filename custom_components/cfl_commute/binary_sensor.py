"""Binary sensor for CFL Commute disruption detection."""

from typing import Any
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_COMMUTE_NAME,
    CONF_DESTINATION,
    CONF_MAJOR_THRESHOLD,
    CONF_MINOR_THRESHOLD,
    CONF_NUM_TRAINS,
    CONF_ORIGIN,
    CONF_SEVERE_THRESHOLD,
    DOMAIN,
    STATUS_CRITICAL,
    STATUS_MAJOR,
    STATUS_MINOR,
    STATUS_NORMAL,
    STATUS_SEVERE,
)
from .coordinator import CFLCommuteDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CFL Commute binary sensor."""
    # Get coordinator from hass.data
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry_data["coordinator"]

    commute_name = config_entry.data.get(CONF_COMMUTE_NAME, "cfl_commute")
    origin = config_entry.data.get(CONF_ORIGIN, {})
    destination = config_entry.data.get(CONF_DESTINATION, {})
    num_trains = config_entry.data.get(CONF_NUM_TRAINS, 3)
    minor_threshold = config_entry.data.get(CONF_MINOR_THRESHOLD, 3)
    major_threshold = config_entry.data.get(CONF_MAJOR_THRESHOLD, 10)
    severe_threshold = config_entry.data.get(CONF_SEVERE_THRESHOLD, 15)

    sensor = CFLCommuteDisruptionSensor(
        coordinator=coordinator,
        commute_name=commute_name,
        origin=origin,
        destination=destination,
        num_trains=num_trains,
        minor_threshold=minor_threshold,
        major_threshold=major_threshold,
        severe_threshold=severe_threshold,
    )

    async_add_entities([sensor])


class CFLCommuteDisruptionSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for disruption detection."""

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
        """Initialize the binary sensor."""
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
    def name(self) -> str:
        return f"{self._commute_name} Has Disruption"

    @property
    def unique_id(self) -> str:
        return f"{self._commute_name}_has_disruption"

    @property
    def translation_key(self) -> str:
        return "has_disruption"

    @property
    def is_on(self) -> bool:
        """Return true if disruption detected."""
        return self._get_status() != STATUS_NORMAL

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:alert-circle"
        return "mdi:check-circle"

    @property
    def state(self) -> StateType:
        return "on" if self.is_on else "off"

    def _get_status(self) -> str:
        """Get the current status."""
        departures = self.coordinator.data if self.coordinator.data else []

        if not departures:
            return STATUS_NORMAL

        if any(d.is_cancelled for d in departures):
            return STATUS_CRITICAL

        max_delay = max((d.delay_minutes for d in departures), default=0)

        if max_delay >= self._severe_threshold:
            return STATUS_SEVERE
        elif max_delay >= self._major_threshold:
            return STATUS_MAJOR
        elif max_delay >= self._minor_threshold:
            return STATUS_MINOR

        return STATUS_NORMAL

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {
            "origin": self._origin_name,
            "destination": self._destination_name,
            "origin_id": self._origin_id,
            "destination_id": self._destination_id,
        }

        departures = self.coordinator.data if self.coordinator.data else []

        cancelled = sum(1 for d in departures if d.is_cancelled)
        delayed = sum(
            1
            for d in departures
            if not d.is_cancelled and d.delay_minutes >= self._minor_threshold
        )
        max_delay = max((d.delay_minutes for d in departures), default=0)

        attrs.update(
            {
                "current_status": self._get_status(),
                "cancelled_count": cancelled,
                "delayed_count": delayed,
                "max_delay_minutes": max_delay,
                "disruption_reasons": self._get_disruption_reasons(),
            }
        )

        return attrs

    def _get_disruption_reasons(self) -> list[str]:
        """Get list of disruption reasons."""
        reasons = []
        departures = self.coordinator.data if self.coordinator.data else []

        for d in departures:
            if d.is_cancelled:
                reasons.append(f"Cancelled: {d.direction}")
            elif d.delay_minutes >= self._minor_threshold:
                reasons.append(f"Delayed {d.delay_minutes}min: {d.direction}")
        return reasons
