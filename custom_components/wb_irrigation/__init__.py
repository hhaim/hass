"""

Weather base irrigation  - uses simple model of leaky bucket from networking (policer)

1. Rain will fill the bucket 
2. Evaporation reduce the bucket - there are many model for ev 
The simplet Blaney-Criddle is used here (base on mean temperature and p - hours of daylight )

see 
https://en.wikipedia.org/wiki/Blaney%E2%80%93Criddle_equation

3. Irrigation time is based on the buket level at the time choosen (only if bucket level is negative)
After Irrigation the bucket is fill again and have zero value

Example : 

    Day    |  bucket level   |  desc
    ----------------------------------
      0    |      +100        |   rain - 5 mm 
      1    |      +150        |   rain - 2 mm 
      2    |      Irrigation  |   No need
      2    |      +150-50     |   Sunny - 10 hours
      3    |      +100-50     |   Sunny - 10 hours
      4    |      +50-50      |   Sunny - 10 hours
      5    |      +0-50       |   Sunny - 10 hours
      6    |      Irigation   |   yes, calculate base on -50 

As you can see this simple model tunnes the Irrigation time dynamically base on the weather actual data ( no forcast needed)
The feedback/calculation is slow and done per day 

"""
import logging
import json
import voluptuous as vol
import copy

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_UNIT_OF_MEASUREMENT,CONF_API_KEY, CONF_LATITUDE, CONF_ELEVATION,CONF_LONGITUDE,CONF_DEVICES, CONF_BINARY_SENSORS, CONF_SWITCHES, CONF_HOST, CONF_PORT,
    CONF_ID, CONF_NAME, CONF_TYPE, CONF_PIN, CONF_ZONE, 
    ATTR_ENTITY_ID, ATTR_STATE, STATE_ON)
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent


_LOGGER = logging.getLogger(__name__)

DOMAIN = "wb_irrigation"


TYPE_RAIN        = 'rain'
TYPE_RAIN_DAY    = 'rain_day'
TYPE_EV_DAY      = 'ev_day'
TYPE_EV_RAIN_BUCKET = 'bucket'
TYPE_EV_FAO56_DAY = 'fao56' #FAO-56 Penman-Monteith based on Mark Richards

DEFAULT_NAME = 'wb_irrigation'
CONF_TAPS = "taps"
CONF_RAIN_FACTOR ="rain_factor"
CONF_MAX_EV = "max_ev"
CONF_MIN_EV = "min_ev"
CONF_DEBUG = "debug"
CONF_FAO56_SENSOR = "fao56"

DATA_KEY = 'wb_irrigation.devices'


_TAP_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_NAME): cv.string,
    }), 
)

SERVICE_SET_VALUE  = 'set_value'
ATTR_VALUE = 'value'

SERVICE_SET_VALUE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): vol.Coerce(float),
})


# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
           vol.Required(CONF_API_KEY): cv.string,
           vol.Required(CONF_NAME): cv.string,
           vol.Optional(CONF_LATITUDE): cv.latitude,
           vol.Optional(CONF_LONGITUDE): cv.longitude,
           vol.Optional(CONF_ELEVATION): vol.Coerce(int),
           vol.Optional(CONF_DEBUG,default=False): cv.boolean,
           vol.Required(CONF_RAIN_FACTOR): vol.Coerce(float),
           vol.Required(CONF_MAX_EV): vol.Coerce(float),
           vol.Required(CONF_MIN_EV): vol.Coerce(float),
           vol.Optional(CONF_TAPS): vol.All(
                    cv.ensure_list, [_TAP_SCHEMA]),
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['discovery']

def  fix_name(cfg,name):
    return cfg[CONF_NAME]+"_"+name

async def async_setup(hass, config):
    """Set up the platform."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = []

    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
        }

    cfgs =[]

    cfg0 = copy.deepcopy(cfg)
    cfg0[CONF_NAME] = fix_name(cfg,TYPE_RAIN)
    cfg0[CONF_UNIT_OF_MEASUREMENT] = "mm"
    cfg0[CONF_TYPE] = TYPE_RAIN
    cfgs.append(cfg0);


    cfg1 = copy.deepcopy(cfg)
    cfg1[CONF_NAME] = fix_name(cfg,TYPE_RAIN_DAY)
    cfg1[CONF_UNIT_OF_MEASUREMENT] = "mm"
    cfg1[CONF_TYPE] = TYPE_RAIN_DAY
    cfgs.append(cfg1);

    cfg2 = copy.deepcopy(cfg)
    cfg2[CONF_NAME] = fix_name(cfg,TYPE_EV_DAY)
    cfg2[CONF_UNIT_OF_MEASUREMENT] = "ev"
    cfg2[CONF_TYPE] = TYPE_EV_DAY
    cfgs.append(cfg2);

    cfg3 = copy.deepcopy(cfg)
    cfg3[CONF_NAME] = fix_name(cfg,TYPE_EV_FAO56_DAY)
    cfg3[CONF_UNIT_OF_MEASUREMENT] = "ev"
    cfg3[CONF_TYPE] = TYPE_EV_FAO56_DAY
    cfgs.append(cfg3);

    #add devices 
    for dev in cfg.get(CONF_TAPS):
       c = copy.deepcopy(cfg)
       c[CONF_NAME] = fix_name(cfg,dev.get(CONF_NAME))
       c[CONF_UNIT_OF_MEASUREMENT] = "ev"
       c[CONF_TYPE] = TYPE_EV_RAIN_BUCKET
       c[CONF_FAO56_SENSOR] = "sensor."+fix_name(cfg,TYPE_EV_FAO56_DAY)
       cfgs.append(c);


    for c in cfgs:
       discovery.load_platform(hass, 'sensor',DOMAIN, c, c)

    async def async_set_value(service_call):
        """Handle calls to alert services."""
        entity_id = service_call.data.get("entity_id", None)
        value = service_call.data.get(ATTR_VALUE)

        for device in hass.data[DATA_KEY]:
            if device.entity_id != entity_id[0]:
                continue

            device.async_set_context(service_call.context)
            if service_call.service == SERVICE_SET_VALUE:
                await device.async_set_value(value)


    hass.services.async_register(
        DOMAIN, SERVICE_SET_VALUE, async_set_value,
        schema=SERVICE_SET_VALUE_SCHEMA)

    return True



