"""
Support for MQTT tasmota with MCP23017 that used for alarm device 

"""
import logging
from typing import Optional
import json

import voluptuous as vol

from ..mytasmota import (get_tasmota_avail_topic,get_tasmota_result,get_tasmota_tele,get_tasmota_state,get_tasmota_command)
from homeassistant.core import callback
from homeassistant.components import mqtt, binary_sensor
from homeassistant.components.binary_sensor import (
    BinarySensorEntity, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_BINARY_SENSORS, CONF_DEVICES, CONF_FORCE_UPDATE, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_ON,
    CONF_PAYLOAD_OFF, CONF_DEVICE_CLASS)
from homeassistant.components.mqtt.mixins import (
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_AVAILABILITY_TOPIC,CONF_AVAILABILITY_MODE,AVAILABILITY_LATEST,
    MqttAvailability)

from homeassistant.components.mqtt.const import (
    CONF_QOS,CONF_STATE_TOPIC,CONF_ENCODING
)

from homeassistant.components.template.const import CONF_AVAILABILITY_TEMPLATE

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

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


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
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
        s.append(MqttTasmotaAlarmBinarySensor(cfg,None))
        _id +=1
    async_add_entities(s)




async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT binary sensor."""

    async_add_entities([MqttTasmotaAlarmBinarySensor(
        config,
        discovery_hash,
    )])

#####
# topic looks like this
#tele/alarm/SENSOR = {"Time":"2018-12-08T18:52:50","MCP230XX":{"D0":0,"D1":0,"D2":0,"D3":0,"D4":0,"D5":0,"D6":0,"D7":0,"D8":1,"D9":1,"D10":1,"D11":0,"D12":1,"D13":1,"D14":0,"D15":0}}
#stat/alarm/RESULT = {"Time":"2018-12-08T18:52:53","MCP230XX_INT":{"D1":1,"MS":3095}}
#stat/alarm/RESULT = {"Event":"Done"}
#####

class MqttTasmotaAlarmBinarySensor(MqttAvailability, BinarySensorEntity):
    """Representation a binary sensor that is updated by MQTT."""

    def __init__(self, config,discovery_hash):
        """Initialize the MQTT binary sensor."""

        stopic = config.get(CONF_SHORT_TOPIC)

        avail_cfg={ }
        avail_cfg[CONF_PAYLOAD_AVAILABLE] = TASMOTA_ONLINE
        avail_cfg[CONF_PAYLOAD_NOT_AVAILABLE] = TASMOTA_OFFLINE 
        avail_cfg[CONF_AVAILABILITY_TOPIC] = get_tasmota_avail_topic(stopic)
        avail_cfg[CONF_AVAILABILITY_MODE] = AVAILABILITY_LATEST
        avail_cfg[CONF_QOS] = DEFAULT_QOS
        avail_cfg[CONF_ENCODING] = "utf8"

        MqttAvailability.__init__(self, avail_cfg)
        self._name = config.get(CONF_NAME)
        self._state = None
        self._aid = config.get(CONF_ID)
        polar = config.get(CONF_POLAR)
        self._polar = polar
        self._state_topic_result = get_tasmota_result(stopic)
        self._state_topic_tele = get_tasmota_tele(stopic)
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

    async def async_added_to_hass(self):
        """Subscribe mqtt events."""
        await MqttAvailability.async_added_to_hass(self)

        @callback
        def result_received(msg):
            payload = msg.payload
            self.update_mqtt_results(payload,'MCP230XX_INT')

        @callback
        def tele_received(msg):
            payload = msg.payload
            self.update_mqtt_results(payload,'MCP230XX')

        await mqtt.async_subscribe(
            self.hass, self._state_topic_result, result_received, self._qos)
        await mqtt.async_subscribe(
            self.hass, self._state_topic_tele, tele_received, self._qos)


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

        self.async_schedule_update_ha_state()


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


