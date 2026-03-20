"""CFL Commute - Home Assistant integration for Luxembourg railways."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_NUM_TRAINS,
    DOMAIN,
    CONF_API_KEY,
    CONF_ORIGIN,
    CONF_DESTINATION,
)
from .api import CFLCommuteClient
from .coordinator import CFLCommuteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CFL Commute from a config entry."""
    # Create API client
    api = CFLCommuteClient(entry.data[CONF_API_KEY])

    # Get station info
    origin = entry.data[CONF_ORIGIN]
    destination = entry.data[CONF_DESTINATION]

    # Create coordinator
    coordinator = CFLCommuteDataUpdateCoordinator(
        hass=hass,
        api=api,
        origin_id=origin["id"],
        origin_name=origin["name"],
        destination_id=destination["id"],
        destination_name=destination["name"],
        config=dict(entry.data),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and API in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "config": entry.data,
    }

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data:
            api = entry_data.get("api")
            if api:
                await api.close()

    return unload_ok


async def async_cleanup_stale_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stale train entities when num_trains is reduced.

    Args:
        hass: Home Assistant instance
        entry: Config entry to clean up
    """
    new_num_trains = entry.options.get(
        CONF_NUM_TRAINS,
        entry.data.get(CONF_NUM_TRAINS, 3),
    )

    entity_reg = er.async_get(hass)

    entities_to_remove = []
    for entity in entity_reg.entities.values():
        if entity.config_entry_id != entry.entry_id:
            continue
        if not entity.entity_id.startswith("sensor."):
            continue
        if "_train_" not in entity.entity_id:
            continue

        entity_train_num = entity.entity_id.split("_train_")[-1]
        try:
            train_num = int(entity_train_num)
            if train_num > new_num_trains:
                entities_to_remove.append(entity.entity_id)
                _LOGGER.debug(
                    "Marking stale entity for removal: %s (train %d > %d)",
                    entity.entity_id,
                    train_num,
                    new_num_trains,
                )
        except ValueError:
            pass

    for entity_id in entities_to_remove:
        entity_reg.async_remove(entity_id)
        _LOGGER.info("Removed stale entity: %s", entity_id)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reload a config entry with cleanup of stale entities.

    Args:
        hass: Home Assistant instance
        entry: Config entry to reload

    Returns:
        True if reload was successful
    """
    await async_cleanup_stale_entities(hass, entry)
    return await hass.config_entries.async_reload(entry.entry_id)
