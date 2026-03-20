"""Tests for config flow."""

import pytest
import voluptuous as vol
from unittest.mock import AsyncMock, MagicMock
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from custom_components.cfl_commute.config_flow import (
    CFLCommuteConfigFlow,
    CONFIG_SCHEMA,
)
from custom_components.cfl_commute.const import (
    CONF_API_KEY,
    CONF_ADD_RETURN_JOURNEY,
    CONF_ORIGIN,
    CONF_DESTINATION,
    DEFAULT_TIME_WINDOW,
    DEFAULT_NUM_TRAINS,
)


class TestConfigSchema:
    """Test configuration schemas."""

    def test_config_schema_requires_api_key(self):
        """Test that API key is required."""
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({})

    def test_config_schema_accepts_valid_api_key(self):
        """Test that valid API key is accepted."""
        result = CONFIG_SCHEMA({"api_key": "test_key_123"})
        assert result["api_key"] == "test_key_123"


class TestConfigFlowInit:
    """Test config flow initialization."""

    def test_config_flow_initial_state(self):
        """Test initial state of config flow."""
        flow = CFLCommuteConfigFlow()
        assert flow._api_key == ""
        assert flow._origin_station == {}
        assert flow._destination_station == {}
        assert flow._client is None

    def test_config_flow_has_version(self):
        """Test config flow has version."""
        flow = CFLCommuteConfigFlow()
        assert flow.VERSION == 1


class TestCommuteNameGeneration:
    """Test commute name generation."""

    def test_default_commute_name_format(self):
        """Test default commute name format."""
        origin = "Luxembourg"
        destination = "Esch-sur-Alzette"
        expected = "Luxembourg → Esch-sur-Alzette"
        assert f"{origin} → {destination}" == expected


class TestReturnJourneyFeature:
    """Test return journey tracking feature."""

    def _create_mock_hass(self, existing_entries: list = None):
        """Create mock hass with optional existing entries."""
        hass = MagicMock()
        hass.config_entries = MagicMock()
        hass.config_entries.flow = MagicMock()
        hass.config_entries.flow.async_init = AsyncMock(return_value=MagicMock())
        return hass

    def _create_flow_with_stations(self):
        """Create a flow with origin and destination set."""
        flow = CFLCommuteConfigFlow()
        flow._api_key = "test_api_key"
        flow._origin_station = {"id": "200405060", "name": "Luxembourg"}
        flow._destination_station = {"id": "200417010", "name": "Esch-sur-Alzette"}
        flow._commute_name = "Luxembourg → Esch-sur-Alzette"
        flow._time_window = DEFAULT_TIME_WINDOW
        flow._num_trains = DEFAULT_NUM_TRAINS
        flow._minor_threshold = 3
        flow._major_threshold = 10
        flow._severe_threshold = 15
        flow._night_updates = False
        return flow

    @pytest.mark.asyncio
    async def test_return_journey_step_shown_when_no_reverse(self):
        """Test return journey step is shown when reverse doesn't exist."""
        flow = self._create_flow_with_stations()
        flow.hass = self._create_mock_hass()
        flow._async_current_entries = MagicMock(return_value=[])

        result = await flow.async_step_return_journey()

        assert result["step_id"] == "return_journey"
        assert CONF_ADD_RETURN_JOURNEY in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_return_journey_step_skipped_when_reverse_exists(self):
        """Test return journey step is skipped when reverse already exists."""
        flow = self._create_flow_with_stations()
        flow.hass = self._create_mock_hass()

        existing_entry = MagicMock()
        existing_entry.unique_id = "200417010_200405060"
        flow._async_current_entries = MagicMock(return_value=[existing_entry])

        result = await flow.async_step_return_journey()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_API_KEY] == "test_api_key"

    @pytest.mark.asyncio
    async def test_return_journey_accepted_creates_reverse(self):
        """Test that accepting return journey creates reverse entry."""
        flow = self._create_flow_with_stations()
        flow.hass = self._create_mock_hass()
        flow._async_current_entries = MagicMock(return_value=[])

        await flow.async_step_return_journey({CONF_ADD_RETURN_JOURNEY: True})

        flow.hass.config_entries.flow.async_init.assert_called_once()
        call_args = flow.hass.config_entries.flow.async_init.call_args
        assert call_args[1]["context"]["source"] == config_entries.SOURCE_IMPORT
        assert call_args[1]["data"][CONF_API_KEY] == "test_api_key"
        assert call_args[1]["data"][CONF_ORIGIN]["id"] == "200417010"
        assert call_args[1]["data"][CONF_DESTINATION]["id"] == "200405060"

    @pytest.mark.asyncio
    async def test_return_journey_declined_creates_single_entry(self):
        """Test that declining return journey only creates forward entry."""
        flow = self._create_flow_with_stations()
        flow.hass = self._create_mock_hass()
        flow._async_current_entries = MagicMock(return_value=[])

        result = await flow.async_step_return_journey({CONF_ADD_RETURN_JOURNEY: False})

        flow.hass.config_entries.flow.async_init.assert_not_called()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ORIGIN]["id"] == "200405060"
        assert result["data"][CONF_DESTINATION]["id"] == "200417010"

    def test_helper_create_entry_returns_config_entry(self):
        """Test _create_entry helper returns proper config entry."""
        flow = self._create_flow_with_stations()
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()

        result = flow._create_entry()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Luxembourg → Esch-sur-Alzette"
        assert result["data"][CONF_ORIGIN]["id"] == "200405060"
        assert result["data"][CONF_DESTINATION]["id"] == "200417010"

    def test_create_entry_returns_config_entry(self):
        """Test _create_entry helper returns proper config entry."""
        flow = self._create_flow_with_stations()
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()

        result = flow._create_entry()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Luxembourg → Esch-sur-Alzette"
        assert result["data"][CONF_ORIGIN]["id"] == "200405060"
        assert result["data"][CONF_DESTINATION]["id"] == "200417010"
