"""
Support for Tasmota alarm based on MCP23017 I2C device

"""
import logging
import json
from typing import Dict, Any
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_BINARY_SENSORS,
    CONF_SWITCHES,
    CONF_HOST,
    CONF_PORT,
    CONF_ID,
    CONF_NAME,
    CONF_TYPE,
    CONF_PIN,
    CONF_ZONE,
    ATTR_ENTITY_ID,
    ATTR_STATE,
    STATE_ON,
    Platform
)
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mytasmota"

CONF_SHORT_TOPIC ='stopic' # short_topic
CONF_POLAR ='polar'

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]


def get_tasmota_avail_topic(topic: str) -> str:
    """Get Tasmota availability topic."""
    return f'tele/{topic}/LWT'


def get_tasmota_result(topic: str) -> str:
    """Get Tasmota result topic."""
    return f'stat/{topic}/RESULT'


def get_tasmota_tele(topic: str) -> str:
    """Get Tasmota telemetry topic."""
    return f'tele/{topic}/SENSOR'


def get_tasmota_state(topic: str) -> str:
    """Get Tasmota state topic."""
    return f'tele/{topic}/STATE'


def get_tasmota_command(topic: str, _index: str) -> str:
    """Get Tasmota command topic."""
    return f'cmnd/{topic}/POWER{_index}'

_BINARY_SENSOR_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_POLAR): cv.boolean,
    }), 
)

_SWITCH_SCHEMA = vol.All(
    vol.Schema({
         vol.Required(CONF_NAME): cv.string,
         vol.Required(CONF_POLAR): cv.boolean,
    }), 
)

# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_DEVICES): [{
                vol.Required(CONF_SHORT_TOPIC): cv.string,
                vol.Required(CONF_NAME): cv.string,
                vol.Optional(CONF_BINARY_SENSORS): vol.All(
                    cv.ensure_list, [_BINARY_SENSOR_SCHEMA]),
                vol.Optional(CONF_SWITCHES): vol.All(
                    cv.ensure_list, [_SWITCH_SCHEMA]),
            }],
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['mqtt']


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tasmota component."""
    cfg = config.get(DOMAIN, {})

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    devices = cfg.get(CONF_DEVICES, [])
    
    if devices:
        for device in devices:
            configured_device = ConfiguredDevice(hass, device)
            await configured_device.async_save_data()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tasmota from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ConfiguredDevice:
    """Representation of a configured Tasmota device."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize the configured device."""
        self.hass = hass
        self.config = config

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self.config.get(CONF_SHORT_TOPIC)

    async def async_save_data(self) -> None:
        """Save the device configuration to hass.data and load platforms."""
        device_data = self.config

        if CONF_DEVICES not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][CONF_DEVICES] = {}

        self.hass.data[DOMAIN][CONF_DEVICES][self.device_id] = device_data

        # Load binary sensor platform if configured
        if CONF_BINARY_SENSORS in device_data:
            self.hass.async_create_task(
                discovery.async_load_platform(
                    self.hass,
                    Platform.BINARY_SENSOR,
                    DOMAIN,
                    {'device_id': self.device_id},
                    self.config
                )
            )

        # Load switch platform if configured
        if CONF_SWITCHES in device_data:
            self.hass.async_create_task(
                discovery.async_load_platform(
                    self.hass,
                    Platform.SWITCH,
                    DOMAIN,
                    {'device_id': self.device_id},
                    self.config
                )
            )


def get_device_config(hass: HomeAssistant, device_id: str) -> Dict[str, Any]:
    """Get device configuration by device ID."""
    return hass.data[DOMAIN][CONF_DEVICES].get(device_id, {})


def get_all_devices(hass: HomeAssistant) -> Dict[str, Dict[str, Any]]:
    """Get all configured devices."""
    return hass.data[DOMAIN].get(CONF_DEVICES, {})
