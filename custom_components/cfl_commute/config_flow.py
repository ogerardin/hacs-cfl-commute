"""Config flow for CFL Commute."""

import logging
from typing import Any, Optional
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from .api import CFLCommuteClient
from .const import (
    CONF_ADD_RETURN_JOURNEY,
    CONF_API_KEY,
    CONF_ORIGIN,
    CONF_DESTINATION,
    CONF_COMMUTE_NAME,
    CONF_TIME_WINDOW,
    CONF_NUM_TRAINS,
    CONF_MINOR_THRESHOLD,
    CONF_MAJOR_THRESHOLD,
    CONF_SEVERE_THRESHOLD,
    CONF_NIGHT_UPDATES,
    DEFAULT_TIME_WINDOW,
    DEFAULT_NUM_TRAINS,
    DEFAULT_MINOR_THRESHOLD,
    DEFAULT_MAJOR_THRESHOLD,
    DEFAULT_SEVERE_THRESHOLD,
    DEFAULT_NIGHT_UPDATES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class CFLCommuteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CFL Commute."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._api_key: str = ""
        self._origin_station: dict = {}
        self._destination_station: dict = {}
        self._client: Optional[CFLCommuteClient] = None
        self._origin_stations: list[selector.SelectOptionDict] = []
        self._destination_stations: list[selector.SelectOptionDict] = []
        self._commute_name: str | None = None
        self._time_window: int | None = None
        self._num_trains: int | None = None
        self._minor_threshold: int | None = None
        self._major_threshold: int | None = None
        self._severe_threshold: int | None = None
        self._night_updates: bool | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # Check for existing entries with API key
        existing_entries = self._async_current_entries()
        if existing_entries:
            first_entry = existing_entries[0]
            self._api_key = first_entry.data.get(CONF_API_KEY, "")
            if self._api_key:
                self._client = CFLCommuteClient(self._api_key)
                return await self.async_step_origin()

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            self._client = CFLCommuteClient(self._api_key)
            return await self.async_step_origin()

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
            description_placeholders={
                "instructions": "Get your free API key from opendata-api@atp.etat.lu"
            },
        )

    async def _search_stations(
        self, query: str, client: CFLCommuteClient
    ) -> list[selector.SelectOptionDict]:
        """Search for stations and return formatted results."""
        try:
            stations = await client.search_stations(query)
            return [
                selector.SelectOptionDict(value=s.id, label=s.name) for s in stations
            ]
        except Exception as e:
            _LOGGER.error(f"Station search error: {e}")
            return []

    def _get_station_schema(
        self,
        stations: list[selector.SelectOptionDict],
        default: str | None = None,
    ) -> vol.Schema:
        """Build schema with combobox (dropdown + free-text)."""
        station_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=stations,
                mode=selector.SelectSelectorMode.DROPDOWN,
                custom_value=True,
            )
        )
        if default:
            return vol.Schema(
                {
                    vol.Required("station", default=default): station_selector,
                }
            )
        return vol.Schema(
            {
                vol.Required("station"): station_selector,
            }
        )

    async def async_step_origin(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle origin station selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_value = user_input.get("station", "").strip()

            if station_value:
                self._origin_stations = await self._search_stations(
                    station_value, self._client
                )
                if not self._origin_stations:
                    errors["station"] = "no_results"
                elif len(self._origin_stations) == 1:
                    station_id = self._origin_stations[0]["value"]
                    station_name = self._origin_stations[0]["label"]
                    self._origin_station = {"id": station_id, "name": station_name}
                    return await self.async_step_destination()
                else:
                    matching = next(
                        (
                            r
                            for r in self._origin_stations
                            if r["value"] == station_value
                        ),
                        None,
                    )
                    if matching:
                        self._origin_station = {
                            "id": matching["value"],
                            "name": matching["label"],
                        }
                        return await self.async_step_destination()

        return self.async_show_form(
            step_id="origin",
            data_schema=self._get_station_schema(self._origin_stations),
            errors=errors,
            description_placeholders={"step": "origin"},
        )

    async def async_step_destination(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle destination station selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_value = user_input.get("station", "").strip()

            if station_value:
                self._destination_stations = await self._search_stations(
                    station_value, self._client
                )
                if not self._destination_stations:
                    errors["station"] = "no_results"
                elif len(self._destination_stations) == 1:
                    station_id = self._destination_stations[0]["value"]
                    station_name = self._destination_stations[0]["label"]
                    self._destination_station = {"id": station_id, "name": station_name}
                    return await self.async_step_settings()
                else:
                    matching = next(
                        (
                            r
                            for r in self._destination_stations
                            if r["value"] == station_value
                        ),
                        None,
                    )
                    if matching:
                        self._destination_station = {
                            "id": matching["value"],
                            "name": matching["label"],
                        }
                        return await self.async_step_settings()

        return self.async_show_form(
            step_id="destination",
            data_schema=self._get_station_schema(self._destination_stations),
            errors=errors,
            description_placeholders={"step": "destination"},
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle settings configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._commute_name = user_input.get(
                CONF_COMMUTE_NAME,
                f"{self._origin_station.get('name', 'Origin')} → {self._destination_station.get('name', 'Destination')}",
            )
            self._time_window = user_input.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)
            self._num_trains = user_input.get(CONF_NUM_TRAINS, DEFAULT_NUM_TRAINS)
            self._minor_threshold = user_input.get(
                CONF_MINOR_THRESHOLD, DEFAULT_MINOR_THRESHOLD
            )
            self._major_threshold = user_input.get(
                CONF_MAJOR_THRESHOLD, DEFAULT_MAJOR_THRESHOLD
            )
            self._severe_threshold = user_input.get(
                CONF_SEVERE_THRESHOLD, DEFAULT_SEVERE_THRESHOLD
            )
            self._night_updates = user_input.get(
                CONF_NIGHT_UPDATES, DEFAULT_NIGHT_UPDATES
            )

            return await self.async_step_return_journey()

        default_name = f"{self._origin_station.get('name', 'Origin')} → {self._destination_station.get('name', 'Destination')}"

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMMUTE_NAME,
                        default=default_name,
                        description="Commute Name",
                    ): str,
                    vol.Required(
                        CONF_TIME_WINDOW,
                        default=DEFAULT_TIME_WINDOW,
                        description="Time Window (minutes)",
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
                    vol.Required(
                        CONF_NUM_TRAINS,
                        default=DEFAULT_NUM_TRAINS,
                        description="Number of Trains",
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Required(
                        CONF_MINOR_THRESHOLD,
                        default=DEFAULT_MINOR_THRESHOLD,
                        description="Minor Delays Threshold (min)",
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_MAJOR_THRESHOLD,
                        default=DEFAULT_MAJOR_THRESHOLD,
                        description="Major Delays Threshold (min)",
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_SEVERE_THRESHOLD,
                        default=DEFAULT_SEVERE_THRESHOLD,
                        description="Severe Disruption Threshold (min)",
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_NIGHT_UPDATES,
                        default=DEFAULT_NIGHT_UPDATES,
                        description="Enable Night Updates",
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_return_journey(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Offer to set up the reverse commute if it doesn't already exist."""
        reverse_unique_id = (
            f"{self._destination_station['id']}_{self._origin_station['id']}"
        )
        reverse_exists = any(
            entry.unique_id == reverse_unique_id
            for entry in self._async_current_entries()
        )

        if reverse_exists:
            return self._create_entry()

        if user_input is not None:
            if user_input.get(CONF_ADD_RETURN_JOURNEY, False):
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": config_entries.SOURCE_IMPORT},
                        data={
                            CONF_API_KEY: self._api_key,
                            CONF_ORIGIN: self._destination_station,
                            CONF_DESTINATION: self._origin_station,
                            CONF_COMMUTE_NAME: f"{self._destination_station.get('name', 'Destination')} → {self._origin_station.get('name', 'Origin')}",
                            CONF_TIME_WINDOW: self._time_window,
                            CONF_NUM_TRAINS: self._num_trains,
                            CONF_MINOR_THRESHOLD: self._minor_threshold,
                            CONF_MAJOR_THRESHOLD: self._major_threshold,
                            CONF_SEVERE_THRESHOLD: self._severe_threshold,
                            CONF_NIGHT_UPDATES: self._night_updates,
                        },
                    )
                )
            return self._create_entry()

        return self.async_show_form(
            step_id="return_journey",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADD_RETURN_JOURNEY, default=True
                    ): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "origin": self._origin_station.get("name", "Origin"),
                "destination": self._destination_station.get("name", "Destination"),
            },
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle automatic creation of a return journey config entry."""
        await self.async_set_unique_id(
            f"{user_input[CONF_ORIGIN]['id']}_{user_input[CONF_DESTINATION]['id']}"
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input[CONF_COMMUTE_NAME],
            data=user_input,
        )

    def _create_entry(self) -> FlowResult:
        """Create the config entry using stored instance variables."""
        return self.async_create_entry(
            title=self._commute_name or "",
            data={
                CONF_API_KEY: self._api_key,
                CONF_ORIGIN: self._origin_station,
                CONF_DESTINATION: self._destination_station,
                CONF_COMMUTE_NAME: self._commute_name,
                CONF_TIME_WINDOW: self._time_window,
                CONF_NUM_TRAINS: self._num_trains,
                CONF_MINOR_THRESHOLD: self._minor_threshold,
                CONF_MAJOR_THRESHOLD: self._major_threshold,
                CONF_SEVERE_THRESHOLD: self._severe_threshold,
                CONF_NIGHT_UPDATES: self._night_updates,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow."""
        return CFLCommuteOptionsFlow()


class CFLCommuteOptionsFlow(config_entries.OptionsFlow):
    """Options flow for CFL Commute."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        config_entry = self.hass.config_entries.async_get_entry(self.handler)
        if config_entry is None:
            return self.async_abort(reason="Config entry not found")

        current_options = (
            dict(config_entry.options)
            if config_entry.options
            else dict(config_entry.data)
        )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_COMMUTE_NAME): str,
                vol.Required(
                    CONF_TIME_WINDOW,
                    default=current_options.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                    description="Time Window (minutes)",
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
                vol.Required(
                    CONF_NUM_TRAINS,
                    default=current_options.get(CONF_NUM_TRAINS, DEFAULT_NUM_TRAINS),
                    description="Number of Trains",
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Required(
                    CONF_MINOR_THRESHOLD,
                    default=current_options.get(
                        CONF_MINOR_THRESHOLD, DEFAULT_MINOR_THRESHOLD
                    ),
                    description="Minor Delays Threshold (min)",
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_MAJOR_THRESHOLD,
                    default=current_options.get(
                        CONF_MAJOR_THRESHOLD, DEFAULT_MAJOR_THRESHOLD
                    ),
                    description="Major Delays Threshold (min)",
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_SEVERE_THRESHOLD,
                    default=current_options.get(
                        CONF_SEVERE_THRESHOLD, DEFAULT_SEVERE_THRESHOLD
                    ),
                    description="Severe Disruption Threshold (min)",
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_NIGHT_UPDATES,
                    default=current_options.get(
                        CONF_NIGHT_UPDATES, DEFAULT_NIGHT_UPDATES
                    ),
                    description="Enable Night Updates",
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
