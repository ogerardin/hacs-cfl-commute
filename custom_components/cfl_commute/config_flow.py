"""Config flow for CFL Commute."""

import asyncio
import logging
from typing import Any, Optional
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from .api import CFLCommuteClient
from .const import (
    CONF_API_KEY,
    CONF_ORIGIN,
    CONF_DESTINATION,
    CONF_COMMUTE_NAME,
    CONF_TIME_WINDOW,
    CONF_NUM_SERVICES,
    CONF_MINOR_THRESHOLD,
    CONF_MAJOR_THRESHOLD,
    CONF_SEVERE_THRESHOLD,
    CONF_NIGHT_UPDATES,
    DEFAULT_TIME_WINDOW,
    DEFAULT_NUM_SERVICES,
    DEFAULT_MINOR_THRESHOLD,
    DEFAULT_MAJOR_THRESHOLD,
    DEFAULT_SEVERE_THRESHOLD,
    DEFAULT_NIGHT_UPDATES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMUTE_NAME): str,
        vol.Required(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
            vol.Coerce(int), vol.Range(min=15, max=120)
        ),
        vol.Required(CONF_NUM_SERVICES, default=DEFAULT_NUM_SERVICES): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10)
        ),
        vol.Required(CONF_MINOR_THRESHOLD, default=DEFAULT_MINOR_THRESHOLD): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Required(CONF_MAJOR_THRESHOLD, default=DEFAULT_MAJOR_THRESHOLD): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Required(CONF_SEVERE_THRESHOLD, default=DEFAULT_SEVERE_THRESHOLD): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Required(CONF_NIGHT_UPDATES, default=DEFAULT_NIGHT_UPDATES): bool,
    }
)

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
        self._origin_results: list = []
        self._destination_results: list = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

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
    ) -> list[dict]:
        """Search for stations and return formatted results."""
        try:
            stations = await client.search_stations(query)
            return [{"value": s.id, "label": s.name} for s in stations]
        except Exception as e:
            _LOGGER.error(f"Station search error: {e}")
            return []

    async def async_step_origin(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle origin station selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for station selection FIRST - takes priority over search
            if "station" in user_input and user_input["station"]:
                station_id = user_input["station"]
                station_name = next(
                    (
                        r["label"]
                        for r in self._origin_results
                        if r["value"] == station_id
                    ),
                    station_id,
                )
                self._origin_station = {"id": station_id, "name": station_name}
                return await self.async_step_destination()
            # Then check for search query
            elif "station_query" in user_input:
                query = user_input["station_query"]
                if query and self._client:
                    self._origin_results = await self._search_stations(
                        query, self._client
                    )
                return self.async_show_form(
                    step_id="origin",
                    data_schema=vol.Schema(
                        {
                            vol.Required("station_query"): str,
                            vol.Optional("station"): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=self._origin_results,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    errors=errors,
                    description_placeholders={"step": "origin"},
                )

        return self.async_show_form(
            step_id="origin",
            data_schema=vol.Schema(
                {
                    vol.Required("station_query"): str,
                }
            ),
            errors=errors,
            description_placeholders={"step": "origin"},
        )

    async def async_step_destination(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle destination station selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for station selection FIRST - takes priority over search
            if "station" in user_input and user_input["station"]:
                station_id = user_input["station"]
                station_name = next(
                    (
                        r["label"]
                        for r in self._destination_results
                        if r["value"] == station_id
                    ),
                    station_id,
                )
                self._destination_station = {"id": station_id, "name": station_name}
                return await self.async_step_settings()
            # Then check for search query
            elif "station_query" in user_input:
                query = user_input["station_query"]
                if query and self._client:
                    self._destination_results = await self._search_stations(
                        query, self._client
                    )
                return self.async_show_form(
                    step_id="destination",
                    data_schema=vol.Schema(
                        {
                            vol.Required("station_query"): str,
                            vol.Optional("station"): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=self._destination_results,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    errors=errors,
                    description_placeholders={"step": "destination"},
                )

        return self.async_show_form(
            step_id="destination",
            data_schema=vol.Schema(
                {
                    vol.Required("station_query"): str,
                }
            ),
            errors=errors,
            description_placeholders={"step": "destination"},
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle settings configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            origin_name = self._origin_station.get("name", "Origin")
            destination_name = self._destination_station.get("name", "Destination")

            return self.async_create_entry(
                title=user_input.get(
                    CONF_COMMUTE_NAME, f"{origin_name} → {destination_name}"
                ),
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_ORIGIN: self._origin_station,
                    CONF_DESTINATION: self._destination_station,
                    CONF_COMMUTE_NAME: user_input.get(
                        CONF_COMMUTE_NAME, f"{origin_name} → {destination_name}"
                    ),
                    CONF_TIME_WINDOW: user_input.get(
                        CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW
                    ),
                    CONF_NUM_SERVICES: user_input.get(
                        CONF_NUM_SERVICES, DEFAULT_NUM_SERVICES
                    ),
                    CONF_MINOR_THRESHOLD: user_input.get(
                        CONF_MINOR_THRESHOLD, DEFAULT_MINOR_THRESHOLD
                    ),
                    CONF_MAJOR_THRESHOLD: user_input.get(
                        CONF_MAJOR_THRESHOLD, DEFAULT_MAJOR_THRESHOLD
                    ),
                    CONF_SEVERE_THRESHOLD: user_input.get(
                        CONF_SEVERE_THRESHOLD, DEFAULT_SEVERE_THRESHOLD
                    ),
                    CONF_NIGHT_UPDATES: user_input.get(
                        CONF_NIGHT_UPDATES, DEFAULT_NIGHT_UPDATES
                    ),
                },
            )

        default_name = f"{self._origin_station.get('name', 'Origin')} → {self._destination_station.get('name', 'Destination')}"

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COMMUTE_NAME, default=default_name): str,
                    vol.Required(
                        CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=120)),
                    vol.Required(
                        CONF_NUM_SERVICES, default=DEFAULT_NUM_SERVICES
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Required(
                        CONF_MINOR_THRESHOLD, default=DEFAULT_MINOR_THRESHOLD
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_MAJOR_THRESHOLD, default=DEFAULT_MAJOR_THRESHOLD
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_SEVERE_THRESHOLD, default=DEFAULT_SEVERE_THRESHOLD
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_NIGHT_UPDATES, default=DEFAULT_NIGHT_UPDATES
                    ): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow."""
        return CFLCommuteOptionsFlow(config_entry)


class CFLCommuteOptionsFlow(SchemaOptionsFlowHandler):
    """Options flow for CFL Commute."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        super().__init__(config_entry)
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self._config_entry.data
            ),
        )
