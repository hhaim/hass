"""
Support for MQTT tasmota with MCP23017 that used for alarm device 

"""
import logging
from typing import Optional, Any, Dict
import json

import voluptuous as vol

from ..mytasmota import (get_tasmota_avail_topic,get_tasmota_result,get_tasmota_tele,get_tasmota_state,get_tasmota_command)
from homeassistant.core import callback,HomeAssistant
from homeassistant.components import mqtt, binary_sensor
from homeassistant.components.binary_sensor import (
    BinarySensorEntity, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_BINARY_SENSORS, CONF_DEVICES, CONF_FORCE_UPDATE, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_ON,
    CONF_PAYLOAD_OFF, CONF_DEVICE_CLASS)

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.mqtt import subscription


from homeassistant.components.mqtt.const import (
    CONF_AVAILABILITY_MODE,
    CONF_AVAILABILITY_TOPIC,
    CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE,
    AVAILABILITY_LATEST,
    CONF_QOS,
    CONF_STATE_TOPIC,
    CONF_RETAIN,CONF_ENCODING
)


from homeassistant.components.mqtt.const import (
    CONF_QOS,CONF_STATE_TOPIC,CONF_ENCODING
)

from homeassistant.components.template.const import CONF_AVAILABILITY_TEMPLATE

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import  ConfigType
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = 'MQTT Binary sensor'
CONF_UNIQUE_ID = 'unique_id'
DEFAULT_FORCE_UPDATE = False
DEFAULT_QOS = 1
CONF_ID ='aid'
CONF_POLAR ='polar'
CONF_SHORT_TOPIC ='stopic' # short_topic
TASMOTA_ONLINE ="Online"
TASMOTA_OFFLINE = "Offline"


DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): cv.byte,
    vol.Required(CONF_POLAR): cv.boolean,
    vol.Required(CONF_SHORT_TOPIC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass: HomeAssistant, config: ConfigType,
                               async_add_entities, discovery_info=None):
    if discovery_info is None:
        await _async_setup_entity(hass, config, async_add_entities)
    else:
        data = hass.data['mytasmota']
        device_id = discovery_info['device_id']
        device = data[CONF_DEVICES][device_id]
        await _async_setup_discover(hass,device,async_add_entities)


async def _async_setup_discover(hass, device, async_add_entities):

    s = []
    name = device.get(CONF_NAME)
    stopic = device.get(CONF_SHORT_TOPIC)
    _id=0
    for conf in device[CONF_BINARY_SENSORS]:
        dname="{}{}".format(name,_id)
        cfg={}
        cfg[CONF_NAME] = dname
        cfg[CONF_ID] = _id
        cfg[CONF_POLAR] = conf.get(CONF_POLAR)
        cfg[CONF_SHORT_TOPIC] = stopic
        s.append(MqttTasmotaAlarmBinarySensor(hass,cfg,None))
        _id +=1
    async_add_entities(s)




async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT binary sensor."""

    async_add_entities([MqttTasmotaAlarmBinarySensor(
        hass,
        config,
        discovery_hash,
    )])

#####
# topic looks like this
#tele/alarm/SENSOR = {"Time":"2018-12-08T18:52:50","MCP230XX":{"D0":0,"D1":0,"D2":0,"D3":0,"D4":0,"D5":0,"D6":0,"D7":0,"D8":1,"D9":1,"D10":1,"D11":0,"D12":1,"D13":1,"D14":0,"D15":0}}
#stat/alarm/RESULT = {"Time":"2018-12-08T18:52:53","MCP230XX_INT":{"D1":1,"MS":3095}}
#stat/alarm/RESULT = {"Event":"Done"}
#####

class MqttTasmotaAlarmBinarySensor(BinarySensorEntity):
    """Representation a binary sensor that is updated by MQTT."""

    def __init__(self, hass,config,discovery_hash):
        """Initialize the MQTT binary sensor."""
        self.hass = hass
        stopic = config.get(CONF_SHORT_TOPIC)
        pindex = int(config.get(CONF_ID))
        self._name = config.get(CONF_NAME)
        self._state = None
        self._aid = config.get(CONF_ID)
        polar = config.get(CONF_POLAR)
        self._polar = polar
        self._state_topic_result = get_tasmota_result(stopic)
        self._state_topic_tele = get_tasmota_tele(stopic)
        self._short_topic = stopic
        self._avail_topic = get_tasmota_avail_topic(stopic)
        self._device_class = None
        if polar:
          self._payload_on = "1"
          self._payload_off = "0"
        else:
          self._payload_on = "0"
          self._payload_off = "1"

        self._int_id="D{}".format(self._aid)
        self._qos = DEFAULT_QOS
        self._force_update = DEFAULT_FORCE_UPDATE
        self._discovery_hash = discovery_hash
        self._sub_state = None
        self._sub_availability = None
        self._available = True
        self._attr_unique_id = f"tasmota_{slugify(stopic)}_{slugify(str(pindex)) if pindex else 'main'}"


    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DEPENDENCIES[0], self._short_topic)},
            name=f"Tasmota {self._short_topic}",
            manufacturer="Tasmota",
            model="Binary",
        )

    async def async_added_to_hass(self):
        """Subscribe mqtt events."""
        await super().async_added_to_hass()

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

        @callback
        def result_received(msg: ReceiveMessage):
            payload = msg.payload
            self.update_mqtt_results(payload,'MCP230XX_INT')

        @callback
        def tele_received(msg: ReceiveMessage):
            payload = msg.payload
            self.update_mqtt_results(payload,'MCP230XX')

        self._sub_state = subscription.async_prepare_subscribe_topics(self.hass, self._sub_state,
            {
                "state_topic": {
                    "topic": self._state_topic_result,
                    "msg_callback": result_received,
                    "qos": self._qos,
                },
                "state_topic2": {
                    "topic": self._state_topic_tele,
                    "msg_callback": tele_received,
                    "qos": self._qos,
                },
            },
         )

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

    def update_mqtt_results (self,payload,top):
        try:
            message = json.loads(payload)
            if top in message:
                events=message[top]
                if self._int_id in events:
                    val = str(events[self._int_id])
                    self.update_state(val)
        except ValueError:
            # If invalid JSON
          _LOGGER.error("Unable to parse payload as JSON: %s", payload)
          return

        self.async_write_ha_state()


    def update_state (self,val):
        if val == self._payload_on:
            self._state = True
        elif val == self._payload_off:
            self._state = False
        else:
            _LOGGER.warning('unknown state %s val:%s',self._name,val)


    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def available(self):
        """Return true if the device is available."""
        return self._available


    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update


