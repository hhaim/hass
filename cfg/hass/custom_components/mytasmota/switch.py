"""
MQTT switches for Tasmota. no need for startup script 
simplify the way you can work with Tasmota 
"""
import logging
from typing import Optional
import json
import re


import voluptuous as vol

from ..mytasmota import (get_tasmota_avail_topic,get_tasmota_result,get_tasmota_tele,get_tasmota_state,get_tasmota_command)
from homeassistant.core import callback
from homeassistant.components.mqtt.mixins import (
        MQTT_AVAILABILITY_SCHEMA, CONF_PAYLOAD_AVAILABLE,CONF_PAYLOAD_NOT_AVAILABLE,CONF_AVAILABILITY_TOPIC, CONF_AVAILABILITY_MODE,AVAILABILITY_LATEST,MqttAvailability)
from homeassistant.components.switch import SwitchEntity

from homeassistant.components.mqtt.const import (
    CONF_QOS,CONF_STATE_TOPIC,CONF_RETAIN,CONF_ENCODING
)


from homeassistant.const import (
    ATTR_ENTITY_ID,CONF_NAME, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_ICON)

from homeassistant.components.template.const import CONF_AVAILABILITY_TEMPLATE

from homeassistant.components import mqtt, switch
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.helpers.restore_state import RestoreEntity


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']


DEFAULT_INDEX =""
DEFAULT_NAME = 'MQTT Switch'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
CONF_INDEX = 'index'
CONF_SHORT_TOPIC ='stopic' # short_topic
DEFAULT_QOS = 1
TASMOTA_ONLINE ="Online"
TASMOTA_OFFLINE = "Offline"
ATTR_UPTIME = 'uptime_sec'
TASMOTA_EVENT = "tasmota.event"
TASMOTA_POWER_UP = "power_up"


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SHORT_TOPIC): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_INDEX, default=DEFAULT_INDEX): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_QOS, default=DEFAULT_QOS):
         vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
}).extend(MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    if discovery_info is None:
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_info)



async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT switch."""

    newswitch = MqttTasmotaSwitch(
        config
    )

    async_add_entities([newswitch])



class MqttTasmotaSwitch(MqttAvailability, SwitchEntity, RestoreEntity):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, config):
        """Initialize the MQTT switch."""

        stopic = config.get(CONF_SHORT_TOPIC)
        pindex  = config.get(CONF_INDEX)
        avail_cfg={}
        avail_cfg[CONF_PAYLOAD_AVAILABLE] = TASMOTA_ONLINE
        avail_cfg[CONF_PAYLOAD_NOT_AVAILABLE] = TASMOTA_OFFLINE 
        avail_cfg[CONF_AVAILABILITY_TOPIC] = get_tasmota_avail_topic(stopic)
        avail_cfg[CONF_AVAILABILITY_MODE] = AVAILABILITY_LATEST
        avail_cfg[CONF_QOS] = DEFAULT_QOS
        avail_cfg[CONF_ENCODING] = "utf8"

        MqttAvailability.__init__(self, avail_cfg)
        self._uptime_sec = 100000000000 # uptime in seconds
        self._valid_ref = False
        self._state = False
        self._name = config.get(CONF_NAME)
        self._icon = config.get(CONF_ICON)
        self._short_topic = stopic
        self._index = config.get(CONF_INDEX) # str
        self._status_str = "POWER{}".format(pindex)
        self._command_topic = get_tasmota_command (stopic,pindex)
        self._result_topic = get_tasmota_result (stopic)
        self._state_topic = get_tasmota_state (stopic)
        self._qos = config.get(CONF_QOS)
        self._retain = config.get(CONF_RETAIN)
        self._payload_on = config.get(CONF_PAYLOAD_ON)
        self._payload_off = config.get(CONF_PAYLOAD_OFF)
        self._optimistic = False


    def _get_d(self, state):
        d = self.state_attributes()
        if not d: 
            d ={}    
        d[ATTR_ENTITY_ID] = self.entity_id
        d["state"] = state
        return d

    def update_uptime(self, uptime_sec):
        if uptime_sec < 0:
            return # nothing to update
        if self._valid_ref == False:
            self._uptime_sec = uptime_sec    
            self._valid_ref = True 
            return 
        if uptime_sec < self._uptime_sec:
           # we had a reboot, need to take a new ref
           _LOGGER.error("switch event  JSON: {}".format( self._get_d(TASMOTA_POWER_UP)))
           self.hass.bus.async_fire(TASMOTA_EVENT,
                                self._get_d(TASMOTA_POWER_UP)) 
           self._uptime_sec = uptime_sec
        else:
            self._uptime_sec = uptime_sec
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await MqttAvailability.async_added_to_hass(self)

        @callback
        def state_message_received(msg):
            payload = msg.payload
            self.update_mqtt_results(payload)

        await mqtt.async_subscribe(
             self.hass, self._result_topic, state_message_received,
             self._qos)
        await mqtt.async_subscribe(
             self.hass, self._state_topic, state_message_received,
             self._qos)

    def _uptime_to_sec(self, uptime_str):
        """ convert uptime string to sec """
        m = re.match(r"(\d+)T(\d\d)\:(\d\d)\:(\d\d)", uptime_str)
        if m:
            return(int(m.group(4))+(int(m.group(3))*60)+int(m.group(2))*60*60+int(m.group(1))*60*60*24)
        _LOGGER.error("Unable to parse uptime string %s", uptime_str)
        return (-1)

    def update_mqtt_results(self, payload):
        UT='Uptime'
        try:
            message = json.loads(payload)
            if UT in message:
                uptime_str = message[UT]
                uptime_sec = self._uptime_to_sec(uptime_str)
                self.update_uptime(uptime_sec)

            if self._status_str in message:
                val=message[self._status_str]
                if val == self._payload_on:
                    self._state = True
                elif val == self._payload_off:
                    self._state = False
                else:
                    _LOGGER.warning('unknown state %s val:%s',self._status_str,val)
        except ValueError:
            # If invalid JSON
          _LOGGER.error("Unable to parse payload as JSON: %s", payload)
          return

        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    async def async_turn_on(self, **kwargs):
        await mqtt.async_publish(
            self.hass, self._command_topic, self._payload_on, self._qos,
            self._retain)

    async def async_turn_off(self, **kwargs):
        await mqtt.async_publish(
            self.hass, self._command_topic, self._payload_off, self._qos,
            self._retain)

    @property
    def state_attributes(self):
        """Return the state attributes."""

        return {
            ATTR_UPTIME : self._uptime_sec
        }
