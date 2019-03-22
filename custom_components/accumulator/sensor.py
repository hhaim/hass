"""
Accumolator of state 

"""
import datetime
import logging
import math
from datetime import timedelta
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, CONF_STATE, CONF_TYPE,
    EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval, async_track_utc_time_change)

from homeassistant.helpers.restore_state import RestoreEntity


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'accumulator'

ICON = 'mdi:chart-line'

ATTR_VALUE = 'value'
ATTR_COUNT = 'count'

# last day 
ATTR_DAY_VALUE = 'day_value'
ATTR_DAY_COUNT = 'day_count'
ATTR_DAY_VALUE_LAST = 'day_value_last'
ATTR_DAY_COUNT_LAST = 'day_count_last'

#last month
ATTR_MONTH_VALUE = 'month_value'
ATTR_MONTH_COUNT = 'month_count'
ATTR_MONTH_VALUE_LAST = 'month_value_last'
ATTR_MONTH_COUNT_LAST = 'month_count_last'

CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"

M_STATE_ON ="on"
M_STATE_OFF ="off"
KEEPALIVE_UPDATE_SEC = 60*10

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_STATE_ON): cv.string,
    vol.Required(CONF_STATE_OFF): cv.string,
    vol.Required(CONF_NAME): cv.string,
})


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Accumulator Stats sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    entity_state_on = config.get(CONF_STATE_ON)
    entity_state_off = config.get(CONF_STATE_OFF)
    name = config.get(CONF_NAME)

    add_entities([AccumStatsSensor(hass, entity_id, entity_state_on, entity_state_off, name)])

    return True


class AccumStatsSensor(RestoreEntity):
    """Accumulator sensor"""

    def __init__(
            self, hass, 
            entity_id, 
            entity_state_on,
            entity_state_off,
            name ):

        self.hass = hass
        self._entity_id = entity_id
        self._entity_state_on = entity_state_on
        self._entity_state_off = entity_state_off
        self._name = name
        self._unit_of_measurement = "h"
        self.value = None
        self.count = None
        self.day_value = None
        self.day_count = None
        self.day_value_last = None
        self.day_count_last = None

        self.month_value = None
        self.month_count = None
        self.month_value_last = None
        self.month_count_last = None


        self._m_state =None
        self.start_time=None

        self.update_state()
        async_track_state_change(
            hass, self._entity_id, self._async_changed)

        async_track_time_interval(
            hass, self._async_keepalive, timedelta(seconds=KEEPALIVE_UPDATE_SEC))

        async_track_utc_time_change(
            hass, self._async_update_last_day,
            hour=0, minute=0, second=0)


        @callback
        def start_refresh(*args):
            """Register state tracking."""
            @callback
            def force_refresh(*args):
                """Force the component to refresh."""
                self.async_schedule_update_ha_state(True)

            force_refresh()
            async_track_state_change(self.hass, self._entity_id, force_refresh)

        # Delay first refresh to keep startup fast
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_refresh)


    @callback
    def _async_changed(self, entity_id, old_state, new_state):

        if new_state is None:
             return
        if self._m_state == M_STATE_OFF:
            if new_state.state == self._entity_state_on :
                self.update_start_time();
        else:
            if new_state.state == self._entity_state_off :
                self.update_stop_time();

        self.async_schedule_update_ha_state()

    async def _async_keepalive(self,time=None):
        if self._m_state == M_STATE_ON:
            self.update_stop_time(False)
            self.update_start_time()


    async def _async_update_last_day(self,time=None):
         if (self.value is None):
             return;

         if ((self.day_value_last is None) or 
            (self.day_count_last is None)):
            self.day_value_last = self.day_value
            self.day_count_last = self.day_count

         # latch the last value
         self.day_value = self.value - self.day_value_last;
         self.day_count = self.count - self.day_count_last;
         self.day_value_last = self.value
         self.day_count_last = self.count

         # check first of the month 
         now = datetime.datetime.now()
         if now.day != 1:
             return

         if ((self.month_value_last is None) or 
            (self.month_count_last is None)):
            self.month_value_last = self.month_value
            self.month_count_last = self.month_count

         # latch the last value
         self.month_value = self.value - self.month_value_last;
         self.month_count = self.count - self.month_count_last;
         self.month_value_last = self.value
         self.month_count_last = self.count


    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self.value is not None:
             return

        state = await self.async_get_last_state()
        if not state:
            _LOGGER.info("async_added_to_hass no state %s",str(state)) 
            _LOGGER.error("first init, should be once") 
            self.value = 0.0; 
            self.count = 0
            self.day_value =0.0
            self.day_count =0
            return

        self._state = state.state

        _LOGGER.info("async_added_to_hass %s",str(state.attributes)) 

        # restore from recorder
        for attr, var, t in ((ATTR_VALUE,'value',float),
                             (ATTR_COUNT,'count',int),

                             (ATTR_DAY_VALUE,'day_value',float),
                             (ATTR_DAY_COUNT,'day_count',int),
                             (ATTR_DAY_VALUE_LAST,'day_value_last',float),
                             (ATTR_DAY_COUNT_LAST,'day_count_last',int),

                             (ATTR_MONTH_VALUE,'month_value',float),
                             (ATTR_MONTH_COUNT,'month_count',int),
                             (ATTR_MONTH_VALUE_LAST,'month_value_last',float),
                             (ATTR_MONTH_COUNT_LAST,'month_count_last',int),

                     ):
            if attr in state.attributes:
                try:
                  setattr(self, var, t(state.attributes[attr]))
                except Exception as e:
                  _LOGGER.error("converting %s to %s ",state.attributes[attr],var)

    def update_state (self):
        # update the state 
        sstate = self.hass.states.get(self._entity_id)
        if sstate == self._entity_state_on:
            self.update_start_time()
        else:
            if sstate == self._entity_state_off:
                self._m_state = M_STATE_OFF
            else:
                self.update_start_time()


    def get_now_ts (self):
        now = datetime.datetime.now()
        now_timestamp = math.floor(dt_util.as_timestamp(now))
        return now_timestamp



    def update_start_time(self):
        self.start_time = self.get_now_ts()
        self._m_state = M_STATE_ON

    def update_stop_time(self,inc_counter=True):
        if self.start_time != None:
           d_sec = (self.get_now_ts() - self.start_time)
           if self.value == None:
               self._m_state = M_STATE_OFF
               return

           self.value += (float(d_sec)/3600.0)
           if inc_counter:
              self.count += 1
           _LOGGER.info("update value is %f %f",self.value,self.count) 
        self._m_state = M_STATE_OFF


    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.value is None or self.count is None:
            return None

        return round(self.value, 2)


    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def round_val (self,val,dig):
        if val is None:
            return 0.0
        return round(val,dig)
    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self.value is None:
            return {}

        return {
            ATTR_VALUE: round(self.value,2),
            ATTR_COUNT: self.count,

            ATTR_DAY_VALUE: self.round_val(self.day_value,1),
            ATTR_DAY_COUNT: self.day_count,
            ATTR_DAY_VALUE_LAST: self.round_val(self.day_value_last,1),
            ATTR_DAY_COUNT_LAST: self.day_count_last,

            ATTR_MONTH_VALUE: self.round_val(self.month_value,0),
            ATTR_MONTH_COUNT: self.month_count,
            ATTR_MONTH_VALUE_LAST: self.round_val(self.month_value_last,0),
            ATTR_MONTH_COUNT_LAST: self.month_count_last,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        pass;




