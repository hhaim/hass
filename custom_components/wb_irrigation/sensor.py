"""

sensors for 
1. rain in mm (hourly) 
2. rain in mm (day)
3. EV (day)
4. queue - per name 


"""
import logging
import json
import re
from datetime import timedelta
from typing import Optional
from requests import get

import voluptuous as vol
from ..wb_irrigation import (TYPE_RAIN,TYPE_RAIN_DAY,TYPE_EV_DAY,TYPE_EV_RAIN_BUCKET,CONF_RAIN_FACTOR,CONF_TAPS)
from homeassistant.core import callback
from homeassistant.components import sensor
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA

from homeassistant.const import (
    CONF_NAME, CONF_TYPE, 
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, 
    STATE_UNKNOWN, TEMP_CELSIUS)

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (async_track_point_in_utc_time,async_track_time_interval)
from homeassistant.util import dt as dt_util
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    if discovery_info is None:
        await _async_setup_entity(hass, config, async_add_entities)
    else:
        _LOGGER.warning(" discover  {} {}".format(discovery_info,config))
        await _async_setup_entity(hass, config, async_add_entities)


async def _async_setup_entity(hass: HomeAssistantType, config: ConfigType,
                              async_add_entities, discovery_hash=None):

    async_add_entities([WeatherIrrigarion(
        hass,conf)])



#TBD change this 
#MIN_TIME_BETWEEN_FORECAST_UPDATES = timedelta(minutes=60)
MIN_TIME_BETWEEN_FORECAST_UPDATES = timedelta(seconds=1)
OWM_URL = "https://api.openweathermap.org/data/2.5/weather?units=metric&lat={}&lon={}&appid={}"


class WeatherIrrigarion(RestoreEntity):
    """"""
    def __init__(self, hass, conf):
        """Initialize the sensor."""
        self.hass = hass
        self._state = STATE_UNKNOWN
        self._name = conf.get(CONF_NAME)
        self._unit_of_measurement = conf.get(CONF_UNIT_OF_MEASUREMENT)
        self._icon = conf.get(CONF_ICON)
        self._type = conf.get(CONF_TYPE)
        self._rain_factor = conf.get(CONF_RAIN_FACTOR)
        self._lat = conf.get(CONF_LATITUDE)
        self._lon = conf.get(CONF_LONGITUDE)
        self._api = conf.get(CONF_API_KEY)

        self._rain_mm =0
        self._ev = 0
        self._skip = 0

        # TBD change this 23,58,0
        async_track_utc_time_change(
            hass, self._async_update_last_day,
            hour=0, minute=0, second=5)


    def get_data (self):
        url=OWM_URL.format(self._lat,self._lon,self._api)
        d = None
        try:
           r = get(url)
           d = json.loads(r.text)
           _LOGGER.warning(" WB_IR get_data read {}".format(d))
       except Exception  as e:
           _LOGGER.warning("Failed to get OWM URL ")
           pass 
       return d;


    async def _async_update_last_day(self,time=None):

        if self._type == TYPE_RAIN_DAY:
            self._state = self._rain_mm
            self._rain_mm = 0

        if self._type == TYPE_EV_DAY:
            self._state = self._ev

        if self._type == TYPE_EV_RAIN_BUCKET:
            self._state += (-self._ev) + (self._rain_mm * self._rain_factor)
            self._rain_mm = 0   

        self.async_schedule_update_ha_state()


    @Throttle(MIN_TIME_BETWEEN_FORECAST_UPDATES)
    def update(self, **kwargs):
        """Fetch the  status from URL"""
        d=  self.get_data()
        tmean = (d['main']['temp_min'] + d['main']['temp_max'])/2
        hours = (d["sys"]["sunset"] - d["sys"]["sunrise"]) /3600.0
        rain_mm = 0
        if "rain" in d:
            if "1h" in d["rain"]:
                rain_mm = d["rain"]["1h"]
            if "3h" in d["rain"]:
                if self._skip ==0:
                   rain_mm = d["rain"]["3h"]
                   self._skip = 2
                else:
                    self._skip = self._skip -1

        ev = hours * (0.46 * tmean + 8.13)

        _LOGGER.warning(" WB_IR t:{} h:{} r:{} ev:{}".format(tmean,hours,rain_mm,ev))
        if self._type == TYPE_RAIN:
            self._state = rain_mm
        if self._type == TYPE_RAIN_DAY:
            self._rain_mm += rain_mm
        if self._type == TYPE_EV_DAY:
            self._ev = ev
        if self._type == TYPE_EV_RAIN_BUCKET:
            self._ev = ev
            self._rain_mm += rain_mm

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state 

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
         return {}

    @property
    def icon(self):
        """Return the icon."""
        return self._icon


