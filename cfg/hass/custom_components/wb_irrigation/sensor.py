"""

sensors for 

1. rain in mm (hourly) 
2. rain in mm (day)
3. EV (day)
4. queue - per tap name. clear by the automation 

the rain_mm is based on actual information from openweathermap and in some cases estimate (in case there is no information)

"""
import asyncio
import logging
import json
import re
import requests 
from ..wb_irrigation import pyeto
from ..wb_irrigation.pyeto import convert,fao
from datetime import timedelta,datetime
from typing import Optional, Any, Dict
import voluptuous as vol
from ..wb_irrigation import (TYPE_EV_FAO56_DAY,TYPE_RAIN,TYPE_RAIN_DAY,TYPE_EV_DAY,TYPE_EV_RAIN_BUCKET,CONF_RAIN_FACTOR,CONF_RAIN_MIN,CONF_TAPS,CONF_MAX_EV,CONF_MIN_EV,CONF_DEBUG,CONF_FAO56_SENSOR,CONF_RAIN_SENSOR,CONF_EXTERNAL_SENSOR_RAIN_SENSOR,CONF_MON_FILTER)
from homeassistant.core import callback,HomeAssistant
from homeassistant.components import sensor
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.util import Throttle
from homeassistant.helpers.event import async_track_utc_time_change

from homeassistant.const import (
    CONF_NAME, CONF_TYPE,CONF_UNIT_OF_MEASUREMENT,CONF_ICON,
    CONF_API_KEY, CONF_ELEVATION,CONF_LATITUDE, CONF_LONGITUDE,CONF_LATITUDE, CONF_MODE, 
    STATE_UNKNOWN)

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import  ConfigType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (async_track_point_in_utc_time,async_track_time_interval)
from homeassistant.util import dt as dt_util
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

DATA_KEY = 'wb_irrigation.devices'


async def async_setup_platform(hass: HomeAssistant, config: ConfigType,
                               async_add_entities, discovery_info=None):

    if discovery_info:
        obj=WeatherIrrigarion(hass,discovery_info)
        async_add_entities([obj])
        hass.data[DATA_KEY].append(obj)



async def _async_setup_entity(hass: HomeAssistant, config: ConfigType,
                              async_add_entities, discovery_hash=None):

    obj=WeatherIrrigarion(hass,conf)
    async_add_entities([obj])
    hass.data[DATA_KEY].append(obj)


OWM_URL = "https://api.openweathermap.org/data/3.0/onecall?units=metric&lat={}&lon={}&exclude=hourly,daily,alerts,minutely&appid={}"


def  estimate_fao56(day_of_year,
                    temperature_celsius,
                    elevation,
                    latitude,
                    rh,
                    wind_m_s,
                    atmos_pres):
           """ Estimate fao56 from weather """

           sha = pyeto.sunset_hour_angle(pyeto.deg2rad(latitude), pyeto.sol_dec(day_of_year))
           
           daylight_hours =  pyeto.daylight_hours(sha)
           
           sunshine_hours = 0.8 *daylight_hours;
           
           ird = pyeto.inv_rel_dist_earth_sun(day_of_year)
           
           et_rad = pyeto.et_rad(pyeto.deg2rad(latitude), pyeto.sol_dec(day_of_year), sha, ird)
      
           sol_rad = pyeto.sol_rad_from_sun_hours(daylight_hours,sunshine_hours,et_rad)

           net_in_sol_rad = pyeto.net_in_sol_rad(sol_rad=sol_rad,albedo=0.23)

           cs_rad = pyeto.cs_rad(elevation, et_rad)

           avp = pyeto.avp_from_rhmin_rhmax(pyeto.svp_from_t(temperature_celsius-1),pyeto.svp_from_t(temperature_celsius),rh,rh)
            
           net_out_lw_rad = pyeto.net_out_lw_rad(temperature_celsius-1, temperature_celsius, sol_rad, cs_rad, avp)

           eto = pyeto.fao56_penman_monteith(
                net_rad = pyeto.net_rad(net_in_sol_rad, net_out_lw_rad),
                t=convert.celsius2kelvin(temperature_celsius),
                ws=wind_m_s,
                svp=pyeto.svp_from_t(temperature_celsius),
                avp=pyeto.avp_from_rhmin_rhmax(pyeto.svp_from_t(temperature_celsius-1),pyeto.svp_from_t(temperature_celsius),rh,rh),
                delta_svp=pyeto.delta_svp(temperature_celsius),
                psy=pyeto.psy_const(atmos_pres))
           return eto 


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
        self._rain_min = conf.get(CONF_RAIN_MIN)
        self._lat = conf.get(CONF_LATITUDE)
        self._elevation  = conf.get(CONF_ELEVATION)
        self._debug = conf.get(CONF_DEBUG)
        self._lon = conf.get(CONF_LONGITUDE)
        self._api = conf.get(CONF_API_KEY)
        self._max_ev = conf.get(CONF_MAX_EV)
        self._min_ev = conf.get(CONF_MIN_EV)
        self._months_filter =[]
        mf = conf.get(CONF_MON_FILTER)
        if (mf != None) and (len(mf)>0):
            self._months_filter = mf
    
        self._update_lock = asyncio.Lock()
        self._state = 0.0
        self._last_rain_mm = None
        self._rain_sensor_inc =False # does the rain sensor is going up (external sensor)
        if self._type == TYPE_EV_RAIN_BUCKET:
            self._state = 500.0
            self._sensor_id = conf.get(CONF_FAO56_SENSOR)
            if len(conf.get(CONF_EXTERNAL_SENSOR_RAIN_SENSOR))>0:
               self._rain_sensor_id = conf.get(CONF_EXTERNAL_SENSOR_RAIN_SENSOR) 
               self._rain_sensor_inc = True 
               self.init_rain_sensor()
            else:    
               self._rain_sensor_id = conf.get(CONF_RAIN_SENSOR) 
        
        self.reset_data ()

        sync_min = 58
        if self._type in (TYPE_EV_FAO56_DAY,TYPE_RAIN_DAY) :
            sync_min = 50

        async_track_utc_time_change(
               hass, self._async_update_last_day,
                hour = 23, minute = sync_min, second = 0)

        #
        if (self._type != TYPE_EV_RAIN_BUCKET):
          async_track_utc_time_change(
              hass, self._async_update_every_hour,
               minute =0,second = 0)


    async def async_added_to_hass(self):
       """Call when entity about to be added to Home Assistant."""
       await super().async_added_to_hass()
       state = await self.async_get_last_state()
       if state is not None:
           self._state = float(state.state)
           _LOGGER.info("wbi async_added_to_hass %s",str(state.attributes)) 
           for attr, var, t in (('rain_total','_rain_mm',float),
                                ('ev','_ev',float),
                                ('fao56','_fao56',float)):
               if attr in state.attributes:
                   try:
                     setattr(self, var, t(state.attributes[attr]))
                   except Exception as e:
                     _LOGGER.info("converting %s to %s ",state.attributes[attr],var)

        

    def reset_data (self):
        self._rain_mm =0
        self._max_temp = -50;
        self._min_temp = 50;
        self._ev = 180
        self._fao56 = 0

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

    def init_rain_sensor (self):
        if self._rain_sensor_inc == True:
           if  self._last_rain_mm == None:
                rain_state = self.hass.states.get(self._rain_sensor_id)
                if rain_state:
                    try: 
                       self._last_rain_mm = int(rain_state.state)
                    except (ValueError,TypeError):
                        pass
   



    def read_rain_sensor (self):
            # filter by months, reason for this feature that in hot months there are sporadic rain indications 
            if len(self._months_filter)>0:
                if (datetime.now().timetuple().tm_mon) in self._months_filter:
                    return 0.0
                
            if self._rain_sensor_inc == False:
                rain_mm = 0.0
                rain_state = self.hass.states.get(self._rain_sensor_id)
                if rain_state :
                    rain_mm = float(rain_state.state)
                return  rain_mm
            else:    
                self.init_rain_sensor ()
                rain_state = self.hass.states.get(self._rain_sensor_id)
                rain_mm = 0.0 # delta
                if rain_state :
                    new_rain_mm = int(rain_state.state) 
                    if self._last_rain_mm != None:
                        if new_rain_mm > self._last_rain_mm:
                            rain_mm = float(new_rain_mm - self._last_rain_mm)
                    self._last_rain_mm = new_rain_mm
                return rain_mm 


    async def _async_update_last_day(self,time=None):

        if self._type == TYPE_EV_FAO56_DAY:
            self._state = round(self._fao56,1)

        if self._type == TYPE_EV_DAY:
            self._state = self._ev

        if self._type == TYPE_EV_RAIN_BUCKET:
            # first time
            if not isinstance(self._state, float):
                self._state = 500.0

            # read fao56 sensor 
            ev = 0
            rain_mm = 0

            ev_state = self.hass.states.get(self._sensor_id)
            if ev_state :
                 ev = float(ev_state.state)

            rain_mm = self.read_rain_sensor ()
            if (rain_mm > 0) and (self._rain_min > 0):
                if rain_mm < self._rain_min:
                    rain_mm = 0

            self._state += (-ev) + (rain_mm * self._rain_factor)
            if self._state > self._max_ev:
               self._state = self._max_ev
            if self._state < self._min_ev:
               self._state = self._min_ev
            self._state = round(self._state,1)

        self.reset_data ()
        self.async_write_ha_state()

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

    def get_fao56_factor (self,owm_d):
             d =  owm_d
             dt=d['dt']
             factor = 0.0
             if dt > d['sunrise']:
                 if dt < d['sunset']:
                    factor = min(float(dt - d['sunrise'])/3600.0,1.0)
             else:
                 if dt > d['sunset']:
                     factor = (dt - d['sunrise'])/3600.0
                     if factor < 1.0:
                        factor = 1.0 - factor
             return factor           
    
    async def _async_update_every_hour(self,time=None):
        async with self._update_lock:
            await self.hass.async_add_executor_job(self._update_every_hour)
            self.async_write_ha_state()     


    def _update_every_hour(self):
        """Fetch the  status from URL"""
        
        # make sure we have last value 
        self.init_rain_sensor ()

        d1 = self.get_data()
        if d1 is None:
            return;


        if 'current' not in d1:
            _LOGGER.error(" Invalid response from OWM {} ".format(d1))
            return

        if self._debug and self._type == TYPE_RAIN:
            _LOGGER.error(" wbi_raw_data {} ".format(d1))

        # estimate rain
        rain_mm = 0
        d = d1['current']
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
                
        if self._type == TYPE_EV_FAO56_DAY:
             f = self.get_fao56_factor (d)
             if f > 0.0:
               self._fao56 += f * self.calc_fao56(d)


        if self._type == TYPE_RAIN:
            self._state = rain_mm
        if self._type == TYPE_RAIN_DAY:
            self._rain_mm += rain_mm
            self._state = self._rain_mm

        self._state = round(self._state,1)

    def calc_fao56 (self,owm_d):
           day_of_year = datetime.now().timetuple().tm_yday
           t = owm_d['temp']
           rh =owm_d['humidity']
           ws = owm_d['wind_speed']
           atmos_pres = owm_d['pressure']

           # multiply it by 2 to norm it to 300ev a day 
           fao56 =  2 * estimate_fao56(day_of_year,
                                   t,
                                   self._elevation,
                                   self._lat,
                                   rh,
                                   ws,
                                   atmos_pres);

           return fao56

       
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
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        if self._type == TYPE_RAIN_DAY:
           return { 'rain_total' :  round(self._rain_mm,1) }
        elif self._type == TYPE_EV_DAY:
           return { 'ev' :  round(self._ev,1) }
        elif self._type == TYPE_EV_FAO56_DAY:
           return { 'fao56' :  round(self._fao56,1) }
        else:
           return {}

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    async def async_set_value(self, value):
        """Set new value."""
        num_value = float(value)
        if num_value < self._min_ev or num_value > self._max_ev:
            _LOGGER.warning("Invalid value: %s (range %s - %s)",
                            num_value, self._min_ev, self._max_ev)
            return
        self._state = num_value
        self.async_write_ha_state()

