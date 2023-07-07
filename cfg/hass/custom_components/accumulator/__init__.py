"""variable implementation for Homme Assistant."""
import asyncio
import logging
import json

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_NAME, ATTR_ICON,EVENT_HOMEASSISTANT_START
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import TemplateError
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval, async_track_utc_time_change)

import datetime
from datetime import timedelta
import math



_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:chart-line'

DOMAIN = "accumulator"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

ATTR_VALUE = 'value'
ATTR_COUNT = 'count'

CONF_ATTRIBUTES = "attributes"
CONF_VALUE = "value"
CONF_RESTORE = "restore"

ATTR_VARIABLE = "variable"
ATTR_VALUE = "value"
ATTR_VALUE_TEMPLATE = "value_template"
ATTR_ATTRIBUTES = "attributes"
ATTR_ATTRIBUTES_TEMPLATE = "attributes_template"
ATTR_REPLACE_ATTRIBUTES = "replace_attributes"

CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"
CONF_SWITCH_ID = "switch_id"

M_STATE_ON ="on"
M_STATE_OFF ="off"
KEEPALIVE_UPDATE_SEC = 60*10


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.slug: vol.Any(
                    {
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(CONF_SWITCH_ID):cv.string,
                        vol.Optional(CONF_STATE_ON): cv.string,
                        vol.Optional(CONF_STATE_OFF): cv.string,

                    },
                    None,
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)



async def async_setup(hass, config):
    """Set up variables."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)


    entities = []

    for _id, _config in config[DOMAIN].items():
        if not _config:
            _config = {}

        name =_config.get(CONF_NAME)
        on = _config.get(CONF_STATE_ON)
        off = _config.get(CONF_STATE_OFF)
        eid = _config.get(CONF_SWITCH_ID)


        entities.append(
            AccumStatsSensor(hass,_id, eid,on, off,name)
        )


    await component.async_add_entities(entities)
    return True



class AccumStatsSensor(RestoreEntity):
    """Accumulator sensor"""

    def __init__(
            self, 
            hass, 
            id,
            remote_id, 
            entity_state_on,
            entity_state_off,
            name):

        self.hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(id)
        self.remote_entity_id = remote_id
        self._entity_state_on = entity_state_on
        self._entity_state_off = entity_state_off
        self._name = name
        self._unit_of_measurement = "hours"
        self.value = None
        self.count = None
        self._m_state =None
        self.start_time=None

        self.update_state_startup()
        async_track_state_change(
            hass, self.remote_entity_id, self._async_changed)

        async_track_time_interval(
            hass, self._async_keepalive, timedelta(seconds=KEEPALIVE_UPDATE_SEC))


        @callback
        def start_refresh(*args):
            """Register state tracking."""
            @callback
            def force_refresh(*args):
                """Force the component to refresh."""
                self.async_schedule_update_ha_state(True)

            force_refresh()
            async_track_state_change(self.hass, self.remote_entity_id, force_refresh)



    @callback
    def _async_changed(self, entity_id, old_state, new_state):

        if new_state is None:
             return
        if self._m_state == M_STATE_OFF:
            if new_state.state == self._entity_state_on :
                self.update_start_time()
        else:
            if new_state.state == self._entity_state_off :
                self.update_stop_time()

        self.async_schedule_update_ha_state()

    async def _async_keepalive(self,time=None):
        if self._m_state == M_STATE_ON:
            self.update_stop_time(False)
            self.update_start_time()
            self.async_schedule_update_ha_state()


    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self.value is not None:
             return


        state = await self.async_get_last_state()
        if not state:
            _LOGGER.info("async_added_to_hass no state %s",str(state)) 
            _LOGGER.info("first init, should be once") 
            self.value = 0.0; 
            self.count = 0
            return

        self._state = state.state


        # restore from recorder
        for attr, var, t in ((ATTR_VALUE,'value',float),
                             (ATTR_COUNT,'count',float)
                     ):
            if attr in state.attributes:
                try:
                  setattr(self, var, t(state.attributes[attr]))
                except Exception as e:
                  _LOGGER.error("converting %s to %s ",state.attributes[attr],var)
          

    def update_state_startup (self):
        # update the state 
        sstate = self.hass.states.get(self.remote_entity_id)
        if sstate == self._entity_state_on:
            self.update_start_time()
        else:
            if sstate == self._entity_state_off:
                self._m_state = M_STATE_OFF
            else:
                self._m_state = M_STATE_OFF


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
        self._m_state = M_STATE_OFF


    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.value is None or self.count is None:
            return 0

        return round(self.value, 4)


    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    def round_val (self,val,dig):
        if val is None:
            return 0.0
        return round(val,dig)
    
    @property
    def state_attributes(self):
        """Return the state attributes of the sensor."""
        if self.value is None:
            return None 

        d =  {
            ATTR_VALUE: round(self.value,4),
            ATTR_COUNT: self.count,
            }
        return  d

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        pass




