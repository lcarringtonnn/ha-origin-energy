"""The Origin Energy integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import OriginEnergyConfigEntry, OriginEnergyCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: OriginEnergyConfigEntry) -> bool:
    """Set up Origin Energy from a config entry."""
    coordinator = OriginEnergyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OriginEnergyConfigEntry) -> bool:
    """Unload an Origin Energy config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded
