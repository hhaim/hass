"""
Support for Tasmota alarm based on MCP23017 I2C device

"""
import logging
import json
import voluptuous as vol

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_DEVICES, CONF_BINARY_SENSORS, CONF_SWITCHES, CONF_HOST, CONF_PORT,
    CONF_ID, CONF_NAME, CONF_TYPE, CONF_PIN, CONF_ZONE, 
    ATTR_ENTITY_ID, ATTR_STATE, STATE_ON)
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mytasmota"

CONF_SHORT_TOPIC ='stopic' # short_topic
CONF_POLAR ='polar'


def get_tasmota_avail_topic (topic):
    return ('tele/{}/LWT'.format(topic))

def get_tasmota_result (topic):
    return ('stat/{}/RESULT'.format(topic))

def get_tasmota_tele (topic):
    return ('tele/{}/SENSOR'.format(topic))

def get_tasmota_state (topic):
    return ('tele/{}/STATE'.format(topic))

def get_tasmota_command (topic,_index):
    return ('cmnd/{}/POWER{}'.format(topic,_index))


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

DEPENDENCIES = ['discovery']

async def async_setup(hass, config):
    """Set up the platform."""
    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
        }

    devices = cfg.get(CONF_DEVICES)
    if devices is not None:
       for device in devices:
          ConfiguredDevice(hass, device).save_data()

    return True


class ConfiguredDevice:

    def __init__(self, hass, config):
        self.hass = hass
        self.config = config

    @property
    def device_id(self):
        return self.config.get(CONF_SHORT_TOPIC)

    def save_data(self):
        """Save the device configuration to `hass.data`."""
        device_data = self.config

        if CONF_DEVICES not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][CONF_DEVICES] = {}

        self.hass.data[DOMAIN][CONF_DEVICES][self.device_id] = device_data

        discovery.load_platform(
            self.hass, 'binary_sensor',
            'mytasmota', {'device_id': self.device_id},self.config)

        #discovery.load_platform(
        #    self.hass, 'switch', DOMAIN,
        #    {'device_id': self.device_id})



