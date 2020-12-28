"""

Load jewish Holidays(Yom Kipur)/Candles/Havdalah from the web (www.hebcal.com) 
The json information is converted to a table of records in this format:

 * star_time: the date and time that start the holiday/sat
 * stop_time: the date and time that end the holiday/sat
 * normal: is it a normal sat?
 * help: holiday name (if it is not normal)

@start_time, there are two events triggered
  -10 min
  -0 min
  with this information

EVENT_TURN_PRE = "hebcal.event"  data{"state": "pre", "start" datetime, "end" datetime} 
EVENT_TURN_ON = "hebcal.event" data{"state": "on", "start" datetime, "end" datetime} 

@ end_time there are one events triggered 
EVENT_TURN_OFF = "hebcal.event" data{"state": "off"} 


How it works:
 It queries  www.hebcal.com with json information. It always queries 2 years (now.year and now.year+1)
 To have enough information in the db (at least ~60 records, per year)
 Once the active number of records is below a watermark(~10), there is another try to read. 

KISS 

 hebcal:
  debug: False/True # to enable debug messages 


"""
import logging
import voluptuous as vol
import copy
import datetime
import requests 
import json
import pickle
from homeassistant.core import HomeAssistant, callback

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_STATE, STATE_ON, STATE_OFF)
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util
from homeassistant.helpers import event, service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from datetime import timedelta


_LOGGER = logging.getLogger(__name__)

DOMAIN = "hebcal"

ENTITY_ID = "hebcal.hebcal"
DATA_KEY = 'hebcal.devices'

DEFAULT_NAME = 'hebcal'
CONF_DEBUG = "debug"


STATE_ATTR_NEXT_S_EVENT_FORMAT = "start_format"
STATE_ATTR_NEXT_S_EVENT = "start"
STATE_ATTR_NEXT_E_EVENT = "end"
STATE_ATTR_HELP_EVENT = "help"
STATE_ATTR_NORM_EVENT = "normal"

HEBCAL_EVENT = "hebcal.event"
EVENT_STATE_PRE = "pre"



# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
           vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['discovery']

async def async_setup(hass, config):
    """Track the state of the sun."""
    HebcalSensor(hass, config)
    return True

HEBCAL_URL = 'https://www.hebcal.com/hebcal/?i=on&b=28&m=50&v=1&cfg=json&maj=on&year={}&c=on&geo=pos&latitude={}&longitude={}&tzid={}'

# to be compatiable with python 3.6,%z can't be used 
def convToDateObject(s):
    if len(s) == 10: # in case of Hannukah bug we don't have the time so set it to high 
        s+="T20:00:00"
    if len(s) > 19:
        s=s[:19]
    o = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
    return o

class TimeRec:
        def __init__(self):
            self.s = None  # start time, date object 
            self.e = None  # end time, date object 
            self.help = ""  # string 
            self.normal = False  # is it normal friday/sat
        
        def update(self):
            if self.s.weekday() == 4 and self.e.weekday() ==5 and len(self.help) == 0:
                self.normal = True 

        def __str__(self):
            n=" "
            if self.normal:
                n="n"
            s = "[{} : {}] {},{:20} {}".format(self.s,self.e,n,self.help,self.e-self.s)
            return s

class CalandarDb:
        
        def __init__(self):
            self.list = []
            self.state = STATE_OFF
            self.latitude = 0
            self.longitude = 0
            self.tz = ""
            self.tindex = 0
        
        def set_cord(self, lat, long):
            self.latitude = lat
            self.longitude = long
        
        def set_tz(self, mtz):
            self.tz = mtz

        def loadExample(self):

            t = TimeRec()
            t.s = convToDateObject("2020-07-03T11:07:00+03:00")
            t.e = convToDateObject("2020-07-03T11:08:00+03:00")
            t.normal = True
            t.help = ""
            self.list.append(t)


        def get_head(self):
            return self.list[self.tindex]
        
        def inc_head(self):
            self.tindex += 1
        
        def get_size(self):
            return len(self.list) - self.tindex

        def need_to_reread(self):

            if self.get_size() < 10:
                return True
            return False     

        def load(self):
            year = datetime.date.today().year
            s = self._load_year(year)
            s.extend(self._load_year(year+1))
            self._process(s)
            #self.dump_log()

        def _load_year(self, year):
            url = HEBCAL_URL.format(year, self.latitude, 
                                    self.longitude, 
                                    self.tz)
            r = requests.get(url)
            y = json.loads(r.text)
            return y['items']

        def _update_list(self, now):
            drop = 0
            for o in self.list:
                if now >= o.e:
                    drop += 1
                elif now < o.s:
                    break
                else:
                    self.state = STATE_ON
            if drop > 0:
                self.list = self.list[drop:]

        def _process(self, items):
            self.list = []
            state = "s"
            for o in items:
                c = o['category']

                if state == "s":
                    if c == "candles": 
                        d = convToDateObject(o['date'])
                        if d.weekday() == 4:
                            last = TimeRec()
                            last.s = d 
                            state = "e"
                elif state == "e":
                    if c == "holiday":
                        last.help = o['title']
                    if c == "havdalah": 
                        d = convToDateObject(o['date'])
                        last.e = d 
                        last.update()
                        self.list.append(last)
                        last = None
                        state = "s"

        def dump_log(self):
            cnt = 0            
            for o in self.list:
                cnt += 1
                _LOGGER.error("Error hebcal {:02d} : {}: ".format(cnt, o))

        def _dump(self):
            cnt = 0            
            for o in self.list:
                cnt += 1
                print(" {:02d} : {} ".format(cnt, o))       
        
        def save_to_file(self, filename):
            with open(filename, 'wb') as config_dictionary_file:
               pickle.dump(self.list, config_dictionary_file)
        
        def load_from_file(self, filename):
            with open(filename, 'rb') as config_dictionary_file:
               self.list = pickle.load(config_dictionary_file)


class HebcalSensor(Entity):

    entity_id = ENTITY_ID

    """"""
    def __init__(self, hass, conf):
        """Initialize the sensor."""
        self.hass = hass
        hcfg = self.hass.config
        self._lat = hcfg.latitude
        self._lon = hcfg.longitude
        self._tz = hcfg.time_zone
        self._state = STATE_OFF
        self._debug = conf.get(CONF_DEBUG)
        self._cancel = None
        self.start_loading_db()


    def start_loading_db(self):
        self._db = None 
        self.do = None  
        self._unsubscribe_auto_updater = async_track_utc_time_change(
              self.hass, self._async_update_startup,
                second=0)


    async def _async_update_startup(self, now):
        """Load the db from the web"""
        # have the info 
        try:
          await self.hass.async_add_executor_job(self.load_db_from_web)
        except Exception as err:
            _LOGGER.error("Error while trying to get hebcal: %s", err)
        if self._db != None:  # we manage to get the db, else retry 
            self.load_timers()
            if self._unsubscribe_auto_updater != None:
                self._unsubscribe_auto_updater()
        self.async_schedule_update_ha_state()     

    def load_db_from_web(self):    
        db = CalandarDb()
        db.set_cord(self._lat,self._lon)
        db.set_tz(self._tz)
        if self._debug:
           _LOGGER.error(" {} {} {} ".format(self._lat,self._lon,self._tz)) 
        db.load()
        now = datetime.datetime.now()
        db._update_list(now)
        self._db = db
        if self._debug:
            db._dump()
            _LOGGER.error(" db loaded {}".format(str(db))) 
    
    def _get_d(self, full, state):
        d = {}
        if full:
            d = self.state_attributes
        d[ATTR_ENTITY_ID] = self.entity_id
        d["state"] = state
        return d

    @callback
    def _pre_on(self, now):
        if self._debug:
            _LOGGER.error(" ==> pre_on  ")
        self.hass.bus.async_fire(HEBCAL_EVENT,
                                 self._get_d(True, EVENT_STATE_PRE)) 
        self.async_schedule_update_ha_state()     

    @callback
    def _on(self, now):
        self._state = STATE_ON
        if self._debug:
            _LOGGER.error(" ==>  on  ")
        self.hass.bus.async_fire(HEBCAL_EVENT, self._get_d(True, STATE_ON))
        self.async_schedule_update_ha_state()     

    @callback
    def _off(self, now):
        self._state = STATE_OFF
        if self._debug:
           _LOGGER.error(" ==>  off  ")
        self.hass.bus.async_fire(HEBCAL_EVENT, self._get_d(False, STATE_OFF))
        self._db.inc_head()
        if self._db.need_to_reread():
            self.start_loading_db()
        else:
            self.load_timers()
        self.async_schedule_update_ha_state()     


    # load the timers from the database 
    def load_timers(self):
        if self._db.state == STATE_OFF:
            do = self._db.get_head()
            self.do = do
            if self._debug:
               _LOGGER.error(" start start {} ".format(self.do)) 
            #trigger 3 events 
            if do.e - do.s < datetime.timedelta(days=1):
                 _LOGGER.error(" hebcal something wrong with the record {} ".format(self.do)) 

            event.async_track_point_in_time(
                self.hass, self._pre_on, do.s - timedelta(minutes=10))
            event.async_track_point_in_time(
                self.hass, self._on, do.s)
            event.async_track_point_in_time(
                self.hass, self._off, do.e)
    
        else:
            self._db.state = STATE_OFF
            do = self._db.get_head() 
          
            event.async_track_point_in_time(
                self.hass, self._pre_on, dt_util.now())
            event.async_track_point_in_time(
                self.hass, self._off, do.e)

    @property
    def name(self):
        """Return the name."""
        return "Hebcal"

    @property
    def state(self):
        """Return the state of the sun."""
        return self._state

    @property
    def should_poll(self):
       """No polling needed."""
       return False

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.do != None:
            next_format =  self.do.s.strftime("%a - %H:%M") +" "+self.do.help
            return { STATE_ATTR_NEXT_S_EVENT_FORMAT : next_format,
                    STATE_ATTR_NEXT_S_EVENT   : self.do.s,
                     STATE_ATTR_NEXT_E_EVENT  : self.do.e,
                     STATE_ATTR_HELP_EVENT    : self.do.help, 
                     STATE_ATTR_NORM_EVENT    : self.do.normal } 
        else:
            return { }
