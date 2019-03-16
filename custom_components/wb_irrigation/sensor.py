"""

sensors for 

1. rain in mm (hourly) 
2. rain in mm (day)
3. EV (day)
4. queue - per tap name. clear by the automation 

the rain_mm is based on actual information from openweathermap and in some cases estimate (in case there is no information)

"""
import logging
import json
import re
import requests 

from datetime import timedelta
from typing import Optional

import voluptuous as vol
from ..wb_irrigation import (TYPE_RAIN,TYPE_RAIN_DAY,TYPE_EV_DAY,TYPE_EV_RAIN_BUCKET,CONF_RAIN_FACTOR,CONF_TAPS,CONF_MAX_EV,CONF_MIN_EV)
from homeassistant.core import callback
from homeassistant.components import sensor
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.util import Throttle
from homeassistant.helpers.event import async_track_utc_time_change

from homeassistant.const import (
    CONF_NAME, CONF_TYPE,CONF_UNIT_OF_MEASUREMENT,CONF_ICON,
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

    if discovery_info:
        async_add_entities([WeatherIrrigarion(hass,discovery_info)])


async def _async_setup_entity(hass: HomeAssistantType, config: ConfigType,
                              async_add_entities, discovery_hash=None):

    async_add_entities([WeatherIrrigarion(
        hass,conf)])



MIN_TIME_BETWEEN_FORECAST_UPDATES = timedelta(minutes=60)
#MIN_TIME_BETWEEN_FORECAST_UPDATES = timedelta(seconds=1)
OWM_URL = "https://api.openweathermap.org/data/2.5/weather?units=metric&lat={}&lon={}&appid={}"


class WeatherIrrigarion(RestoreEntity):
    """"""
    def __init__(self, hass, conf):
        """Initialize the sensor."""
        self.hass = hass
        self._name = conf.get(CONF_NAME)
        self._unit_of_measurement = conf.get(CONF_UNIT_OF_MEASUREMENT)
        self._icon = conf.get(CONF_ICON)
        self._type = conf.get(CONF_TYPE)
        self._rain_factor = conf.get(CONF_RAIN_FACTOR)
        self._lat = conf.get(CONF_LATITUDE)
        self._lon = conf.get(CONF_LONGITUDE)
        self._api = conf.get(CONF_API_KEY)
        self._max_ev = conf.get(CONF_MAX_EV)
        self._min_ev = conf.get(CONF_MIN_EV)
        self._state = 0.0
        if self._type == TYPE_EV_RAIN_BUCKET:
            self._state = 500.0
        self.reset_data ()

        async_track_utc_time_change(
            hass, self._async_update_last_day,
             hour=23, minute=58,second=0)
        async_track_utc_time_change(
            hass, self._async_update_every_hour,
              minute=0,second=0)


    async def async_added_to_hass(self):
       """Call when entity about to be added to Home Assistant."""
       await super().async_added_to_hass()
       state = await self.async_get_last_state()
       if state is not None:
           self._state = float(state.state)

    def reset_data (self):
        self._rain_mm =0
        self._max_temp = -50;
        self._min_temp = 50;
        self._ev = 0

    def get_data (self):
        url=OWM_URL.format(self._lat,self._lon,self._api)
        d = None
        try:
           r = requests.get(url)
           d = json.loads(r.text)
           #_LOGGER.warning(" WB_IR get_data read {}".format(d))
        except Exception  as e:
           _LOGGER.warning("Failed to get OWM URL {}".format(r.text))
           pass 
        return d;


    async def _async_update_last_day(self,time=None):

        if self._type == TYPE_RAIN_DAY:
            self._state = self._rain_mm

        if self._type == TYPE_EV_DAY:
            self._state = self._ev

        if self._type == TYPE_EV_RAIN_BUCKET:
            # first time
            if not isinstance(self._state, float):
                self._state = 500.0
            self._state += (-self._ev) + (self._rain_mm * self._rain_factor)
            if self._state > self._max_ev:
               self._state = self._max_ev
            if self._state < self._min_ev:
               self._state = self._min_ev
            self._state = round(self._state,1)

        self.reset_data ()
        self.async_schedule_update_ha_state()

    def rain_desc_to_mm (self,code):
        CONVERT= {500:1.0,
                 501:2.0,
                 502:5.0,
                 503:20.0,
                 504:60.0,
                 511:5.0,
                 520:5.0,
                 521:5.0,
                 522:20.0,
                 531:50.0}
        if code in CONVERT:
            return CONVERT[code]
        _LOGGER.warning(" can't findany key in {}".format(code))
        return 10.0 


    async def _async_update_every_hour(self,time=None):
        """Fetch the  status from URL"""
        d=  self.get_data()
        if d is None:
            return;

        tmean = None
        hours = None

        if "main" in d:
           tmax = d['main']['temp_max']
           tmin = d['main']['temp_min']
           if tmax > self._max_temp:
              self._max_temp = tmax
           if tmin < self._min_temp:
              self._min_temp = tmin
        
           tmean = (self._max_temp + self._min_temp)/2
        else:
           _LOGGER.warning(" can't find main in {}".format(d))

        if "sys" in d:
           hours = (d["sys"]["sunset"] - d["sys"]["sunrise"]) /3600.0

        rain_mm = 0
        if "rain" in d:
            # accurate 
            if "1h" in d["rain"]:
                rain_mm = float(d["rain"]["1h"])
            if "3h" in d["rain"]:
                rain_mm = float(d["rain"]["3h"])/3.0
        else:
            # this is estimation base on string 
            if "weather" in d:
                w = d['weather']
                for obj in w:
                    if obj['main']=='Rain':
                        rain_mm = self.rain_desc_to_mm(obj['id'])
        if "snow" in d:
            # not acurate, in case of snow 
            rain_mm = rain_mm + 50

        ev = None; 
        if tmean and hours:
           ev = round(hours * (0.46 * tmean + 8.13),0)
            

        if self._type == TYPE_RAIN:
            self._state = rain_mm
        if self._type == TYPE_RAIN_DAY:
            self._rain_mm += rain_mm
        if self._type == TYPE_EV_DAY:
            if ev:
               self._ev = ev
        if self._type == TYPE_EV_RAIN_BUCKET:
            if ev:
               self._ev = ev
            self._rain_mm += rain_mm

    @property
    def should_poll(self):
       """No polling needed."""
       return False

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


