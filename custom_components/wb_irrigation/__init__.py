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

from homeassistant.const import (
    CONF_DEVICES, CONF_BINARY_SENSORS, CONF_SWITCHES, CONF_HOST, CONF_PORT,
    CONF_ID, CONF_NAME, CONF_TYPE, CONF_PIN, CONF_ZONE, 
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME,
    STATE_UNKNOWN, TEMP_CELSIUS,
    ATTR_ENTITY_ID, ATTR_STATE, STATE_ON)

from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "wb_irrigation"

TYPE_RAIN        = 'rain'
TYPE_RAIN_DAY    = 'rain_day'
TYPE_EV_DAY      = 'ev_day'
TYPE_EV_RAIN_BUCKET = 'bucket'

DEFAULT_NAME = 'wb_irrigation'
CONF_TAPS = "taps"
CONF_RAIN_FACTOR ="rain_factor"

_LOGGER.warning(" async_setup  {} ".format(config))

#MIN_TIME_BETWEEN_FORECAST_UPDATES = timedelta(minutes=60)

# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
           vol.Required(CONF_API_KEY): cv.string
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['discovery']

async def async_setup(hass, config):
    """Set up the platform."""
    _LOGGER.warning(" async_setup  {} ".format(config))

    return True;

    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
        }

    cfgs =[]

    cfg0 = copy.deepcopy(config)
    cfg0[CONF_NAME] = TYPE_RAIN
    cfg0[CONF_UNIT_OF_MEASUREMENT] = "mm"
    cfg0[CONF_TYPE] = TYPE_RAIN
    cfgs.append(cfg0);

    cfg1 = copy.deepcopy(config)
    cfg1[CONF_NAME] = TYPE_RAIN_DAY
    cfg1[CONF_UNIT_OF_MEASUREMENT] = "mm"
    cfg1[CONF_TYPE] = TYPE_RAIN_DAY
    cfgs.append(cfg1);

    cfg2 = copy.deepcopy(config)
    cfg2[CONF_NAME] = TYPE_EV_DAY
    cfg2[CONF_UNIT_OF_MEASUREMENT] = "ev"
    cfg2[CONF_TYPE] = TYPE_EV_DAY
    cfgs.append(cfg2);

    #add devices 
    for dev in config.get(CONF_TAPS):
       cfg = copy.deepcopy(config)
       cfg[CONF_NAME] = dev.get(CONF_NAME)
       cfg[CONF_UNIT_OF_MEASUREMENT] = "ev"
       cfg[CONF_TYPE] = TYPE_EV_RAIN_BUCKET
       cfgs.append(cfg);

    for cfg in cfgs:
       discovery.load_platform(
             self.hass, 'sensor',
              DOMAIN, cfg,cfg)

    return True




