"""
MQTT switches for Tasmota. no need for startup script 
simplify the way you can work with Tasmota 
"""
import logging
from typing import Optional, Any, Dict
import json
import re


import voluptuous as vol

from ..mytasmota import (get_tasmota_avail_topic,get_tasmota_result,get_tasmota_tele,get_tasmota_state,get_tasmota_command)
from homeassistant.core import callback


from ..mytasmota import (
    get_tasmota_avail_topic,
    get_tasmota_result,
    get_tasmota_tele,
    get_tasmota_state,
    get_tasmota_command
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.typing import  ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.mqtt import subscription
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.mqtt.const import (
    CONF_QOS,
    CONF_STATE_TOPIC,
    CONF_RETAIN,
    CONF_ENCODING
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_ICON,
    STATE_ON,
    STATE_OFF
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify




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
    vol.Optional(CONF_RETAIN, default=False): cv.boolean,
})



async def async_setup_platform(hass: HomeAssistant, config: ConfigType,
                               async_add_entities, discovery_info=None):
    if discovery_info is None:
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_info)



async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT switch."""

    newswitch = MqttTasmotaSwitch(hass,
        config
    )

    async_add_entities([newswitch])



class MqttTasmotaSwitch(SwitchEntity, RestoreEntity):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, hass, config):
        """Initialize the MQTT switch."""
        stopic = config.get(CONF_SHORT_TOPIC)
        pindex = config.get(CONF_INDEX)
        self.hass = hass
        self._uptime_sec = 100000000000  # uptime in seconds
        self._valid_ref = False
        self._state = False
        self._name = config.get(CONF_NAME)
        self._icon = config.get(CONF_ICON)
        self._short_topic = stopic
        self._index = config.get(CONF_INDEX)  # str
        self._status_str = f"POWER{pindex}"
        self._command_topic = get_tasmota_command(stopic, pindex)
        self._result_topic = get_tasmota_result(stopic)
        self._state_topic = get_tasmota_state(stopic)
        self._avail_topic = get_tasmota_avail_topic(stopic)
        self._qos = config.get(CONF_QOS)
        self._retain = config.get(CONF_RETAIN)
        self._payload_on = config.get(CONF_PAYLOAD_ON)
        self._payload_off = config.get(CONF_PAYLOAD_OFF)
        self._optimistic = False
        self._available = True
        
        # Create unique entity ID
        self._attr_unique_id = f"tasmota_{slugify(stopic)}_{slugify(str(pindex)) if pindex else 'main'}"
        
        # MQTT subscriptions
        self._sub_state = None
        self._sub_availability = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DEPENDENCIES[0], self._short_topic)},
            name=f"Tasmota {self._short_topic}",
            manufacturer="Tasmota",
            model="Switch",
        )

    def _get_d(self, state):
        """Get device attributes dictionary."""
        d = self.extra_state_attributes or {}
        d[ATTR_ENTITY_ID] = self.entity_id
        d["state"] = state
        return d

    def update_uptime(self, uptime_sec):
        """Update uptime and detect reboots."""
        if uptime_sec < 0:
            return  # nothing to update
        
        if not self._valid_ref:
            self._uptime_sec = uptime_sec
            self._valid_ref = True
            return
        
        if uptime_sec < self._uptime_sec:
            # we had a reboot, need to take a new ref
            _LOGGER.info("Tasmota device rebooted: %s", self._short_topic)
            self.hass.bus.async_fire(
                TASMOTA_EVENT,
                self._get_d(TASMOTA_POWER_UP)
            )
            self._uptime_sec = uptime_sec
        else:
            self._uptime_sec = uptime_sec
        
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        
        # Restore last state
        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state == STATE_ON

        @callback
        def state_message_received(msg: ReceiveMessage):
            """Handle state messages."""
            self.update_mqtt_results(msg.payload)

        @callback
        def availability_message_received(msg: ReceiveMessage):
            """Handle availability messages."""
            if msg.payload == TASMOTA_ONLINE:
                self._available = True
            elif msg.payload == TASMOTA_OFFLINE:
                self._available = False
            else:
                _LOGGER.warning(
                    "Invalid availability payload: %s for %s",
                    msg.payload,
                    self.entity_id
                )
                return
            self.async_write_ha_state()

        self._sub_state = subscription.async_prepare_subscribe_topics(self.hass, self._sub_state,{
                "state_topic": {
                    "topic": self._result_topic,
                    "msg_callback": state_message_received,
                    "qos": self._qos,
                },
                "state_topic2": {
                    "topic": self._state_topic,
                    "msg_callback": state_message_received,
                    "qos": self._qos,
                },
            },
         )

        # Subscribe to state topics
        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state)

        self._sub_availability = subscription.async_prepare_subscribe_topics(self.hass, self._sub_availability,
            {
                "availability_topic": {
                    "topic": self._avail_topic,
                    "msg_callback": availability_message_received,
                    "qos": self._qos,
                },
            },
         )

        # Subscribe to availability topic
        self._sub_availability = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_availability
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        self._sub_availability = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_availability
        )

    def _uptime_to_sec(self, uptime_str):
        """Convert uptime string to seconds."""
        m = re.match(r"(\d+)T(\d\d):(\d\d):(\d\d)", uptime_str)
        if m:
            days = int(m.group(1))
            hours = int(m.group(2))
            minutes = int(m.group(3))
            seconds = int(m.group(4))
            return seconds + (minutes * 60) + (hours * 3600) + (days * 86400)
        
        _LOGGER.error("Unable to parse uptime string %s", uptime_str)
        return -1

    def update_mqtt_results(self, payload):
        """Update the state based on MQTT payload."""
        UT = 'Uptime'
        try:
            message = json.loads(payload)
            
            if UT in message:
                uptime_str = message[UT]
                uptime_sec = self._uptime_to_sec(uptime_str)
                self.update_uptime(uptime_sec)

            if self._status_str in message:
                val = message[self._status_str]
                if val == self._payload_on:
                    self._state = True
                elif val == self._payload_off:
                    self._state = False
                else:
                    _LOGGER.warning(
                        'Unknown state %s val:%s', self._status_str, val
                    )
                    
        except (ValueError, json.JSONDecodeError):
            _LOGGER.error("Unable to parse payload as JSON: %s", payload)
            return

        self.async_write_ha_state()

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
    def available(self):
        """Return true if the device is available."""
        return self._available

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""

        return {
            ATTR_UPTIME: self._uptime_sec
        }

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        from homeassistant.components.mqtt import async_publish
        
        await async_publish(
            self.hass,
            self._command_topic,
            self._payload_on,
            self._qos,
            self._retain
        )

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        from homeassistant.components.mqtt import async_publish
        
        await async_publish(
            self.hass,
            self._command_topic,
            self._payload_off,
            self._qos,
            self._retain
        )
