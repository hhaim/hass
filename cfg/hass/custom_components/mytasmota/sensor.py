"""
Support Tasmota MQTT counter sensor

Tasmota forget the counter value at reset.
It is a problem to save it to Flash any update (wear the flash)
The solution is to check uptime and add diff to the counter value 

"""
import logging
import json
import re
from datetime import timedelta
from typing import Optional, Any, Dict

import voluptuous as vol
from ..mytasmota import (
    get_tasmota_avail_topic,
    get_tasmota_result,
    get_tasmota_tele,
    get_tasmota_state,
    get_tasmota_command
)

from homeassistant.core import callback, HomeAssistant
from homeassistant.components import sensor
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.mqtt import subscription
from homeassistant.helpers.entity import DeviceInfo

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

from homeassistant.util import slugify


#from homeassistant.components.mqtt.mixins import (
#    CONF_PAYLOAD_NOT_AVAILABLE, CONF_PAYLOAD_AVAILABLE,CONF_AVAILABILITY_TOPIC, CONF_AVAILABILITY_MODE,AVAILABILITY_LATEST,
#    MqttAvailability)

#from homeassistant.components.mqtt.const import (
#    CONF_QOS,CONF_STATE_TOPIC,CONF_ENCODING
#)

from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, STATE_UNKNOWN,
    CONF_UNIT_OF_MEASUREMENT, CONF_ICON, CONF_DEVICE_CLASS)
from homeassistant.helpers.entity import Entity
from homeassistant.components import mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import  ConfigType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (async_track_point_in_utc_time,async_track_time_interval)
from homeassistant.util import dt as dt_util
from homeassistant.helpers.restore_state import RestoreEntity

from homeassistant.components.template.const import CONF_AVAILABILITY_TEMPLATE


_LOGGER = logging.getLogger(__name__)



DEPENDENCIES = ['mqtt']
CONF_SHORT_TOPIC ='stopic' # short_topic
CONF_ID = 'id'
SENSOR_TYPE = 'type'

CONF_MAX_DIFF = 'max_valid_diff'
CONF_EXPIRE_AFTER = 'expire_after'
CONF_DEFAULT_MAX_DIFF = 2000



PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SHORT_TOPIC): cv.string,
    vol.Required(CONF_ID):cv.positive_int,
    vol.Optional(SENSOR_TYPE,default='counter'):cv.string,
    vol.Optional(CONF_MAX_DIFF,default=CONF_DEFAULT_MAX_DIFF):cv.positive_int,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
})


async def async_setup_platform(hass: HomeAssistant, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT sensors through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)



async def _async_setup_entity(hass: HomeAssistant, config: ConfigType,
                              async_add_entities, discovery_hash=None):
    """Set up MQTT sensor."""

    async_add_entities([MqttTasmotaCounter(
        hass,config)])
######
#
#09:16:59 MQT: tele/water_out/STATE = {"Time":"2018-12-21T09:16:59","Uptime":"0T00:00:23","Vcc":2.723,"Wifi":{"AP":1,"SSId":"fbi-4","RSSI":36,"APMac":"F8:D1:11:A0:AA:68"}}
#09:16:59 MQT: tele/water_out/SENSOR = {"Time":"2018-12-21T09:16:59","COUNTER":{"C1":0}}
#
######


ATTR_VALUE = 'value'
ATTR_OLD_VALUE = 'old_value'
ATTR_UPTIME = 'uptime_sec'
DEFAULT_QOS = 1
TASMOTA_ONLINE ="Online"
TASMOTA_OFFLINE = "Offline"



class MqttTasmotaCounter(RestoreEntity):
    """Representation of a Tasmota counter using MQTT."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        stopic = config.get(CONF_SHORT_TOPIC)
        pindex = config.get(CONF_ID)

        self.hass = hass
        self._state = STATE_UNKNOWN
        self._old_value = None
        self._value = None # counter value 
        self._uptime_sec = 100000000000 # uptime in seconds
        self._valid_ref = False
        self._name = config.get(CONF_NAME)
        self._max_valid_diff = config.get(CONF_MAX_DIFF)
        self._state_tele = get_tasmota_tele(stopic)
        self._state_state = get_tasmota_state(stopic)
        self._avail_topic = get_tasmota_avail_topic(stopic)
        #self._result_topic = get_tasmota_result(stopic)
        self._short_topic = stopic
                
        self._expire_after = config.get(CONF_EXPIRE_AFTER)
        self._couner_id = config.get(CONF_ID)
        self._qos = DEFAULT_QOS
        self._unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._mqtt_update = True
        self._icon = config.get(CONF_ICON)
        self._available = True
        self._attr_unique_id = f"tasmota_{slugify(stopic)}_{slugify(str(pindex)) if pindex else 'main'}"
                # MQTT subscriptions
        self._sub_state = None
        self._sub_availability = None
        
        # start keepalive 
        if self._expire_after is not None and self._expire_after > 0:
            async_track_time_interval(
                 self.hass, self._async_keepalive, timedelta(seconds=self._expire_after))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DEPENDENCIES[0], self._short_topic)},
            name=f"Tasmota {self._short_topic}",
            manufacturer="Tasmota",
            model="Counter",
        )


    async def async_added_to_hass(self):
        """Subscribe mqtt events."""
        await super().async_added_to_hass()

        await self.load_state_from_recorder()


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
        def tele_received(msg: ReceiveMessage):
            payload = msg.payload
            self.update_mqtt_sensor(payload)

        @callback
        def state_received(msg: ReceiveMessage):
            payload = msg.payload
            self.update_mqtt_state(payload)

        self._sub_state = subscription.async_prepare_subscribe_topics(self.hass, self._sub_state,
            {
                "state_topic": {
                    "topic": self._state_state,
                    "msg_callback": state_received,
                    "qos": self._qos,
                },
                "state_topic2": {
                    "topic": self._state_tele,
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


    #COUNTER":{"C1":0}
    def update_mqtt_sensor (self,payload):
        CNT='COUNTER'
        try:
            message = json.loads(payload)
            if CNT in message:
                c='C{}'.format(self._couner_id)
                new_counter=int(message[CNT][c])
                self.update_counter(new_counter)
            else:
               _LOGGER.error("Unable to find %s in payload %s", CNT,payload)
               return
        except ValueError:
            # If invalid JSON
          _LOGGER.error("Unable to parse payload as JSON: %s", payload)
          return


    async def _async_keepalive(self,time=None):
        # kind of watchdog 
        if self._mqtt_update:
            self._mqtt_update = False
        else:
            self._m_state = STATE_UNKNOWN
            self.async_write_ha_state()


    def update_counter(self,new_counter):
        if self._valid_ref:
            diff = 0  
            if new_counter > self._old_value:
                  diff = new_counter - self._old_value
            else:
               self._old_value = new_counter
               self.update_state_value ()
               self.async_write_ha_state()

            if diff == 0:
                return;
            if diff > self._max_valid_diff:
                _LOGGER.error("diff is too high (%d) somthing is wrong new:(%d) - old:(%d) ", diff,new_counter ,self._old_value)
                diff = self._max_valid_diff
            else:
               self._mqtt_update = True
               self._value += diff
               self._old_value = new_counter
               self.update_state_value ()
               self.async_write_ha_state()
        else:
            # set new value 
            self._old_value = new_counter
            self._valid_ref = True
            self.async_write_ha_state()


    def update_state_value (self):
        if self._template is None:
           self._state = self._value
        else:
           self._template.hass = self.hass
           self._state = self._template.async_render({'value': self._value})


    def uptime_to_sec (self,uptime_str):
        """ convert uptime string to sec """
        m = re.match(r"(\d+)T(\d\d)\:(\d\d)\:(\d\d)", uptime_str)
        if m:
            return(int(m.group(4))+(int(m.group(3))*60)+int(m.group(2))*60*60+int(m.group(1))*60*60*24)
        _LOGGER.error("Unable to parse uptime string %s", uptime_str)
        return (-1)


    #"Uptime":"0T00:00:23"
    def update_mqtt_state (self,payload):
        UT='Uptime'
        try:
            message = json.loads(payload)
            if UT in message:
                uptime_str=message[UT]
                uptime_sec = self.uptime_to_sec(uptime_str)
                self.update_uptime(uptime_sec)
            else:
              _LOGGER.error("Unable to find %s  in payload %s", UT,payload)
              return

        except ValueError:
            # If invalid JSON
          _LOGGER.error("Unable to parse payload as JSON: %s", payload)
          return


    def update_uptime(self,uptime_sec):
        if uptime_sec < 0:
            return # nothing to update
        if uptime_sec < self._uptime_sec:
           # we had a reboot, need to take a new ref
           self._valid_ref = False 
           self._uptime_sec = uptime_sec
        else:
            self._uptime_sec = uptime_sec
        self.async_write_ha_state()
        

    async def load_state_from_recorder(self) -> None:
        """Load entity state from recorder with modern HA 2025 practices."""
        if self._value is not None:
            return

        # Use the modern state restoration method
        state = await self.async_get_last_state()
        
        if not state:
            _LOGGER.info(
                "load_state_from_recorder: No previous state found for %s, initializing defaults",
                self.entity_id
            )
            # Initialize default values for first run
            self._value = 0
            self._old_value = 0
            self._valid_ref = False
            self.update_state_value()
            self.async_write_ha_state()
            return

        # Store the state value
        self._state = state.state
        _LOGGER.debug(
            "load_state_from_recorder: Restoring state for %s with attributes: %s",
            self.entity_id,
            state.attributes
        )

        # Modern attribute restoration with type safety
        attribute_mappings = [
            (ATTR_VALUE, '_value', int, 0),
            (ATTR_OLD_VALUE, '_old_value', int, 0),
            (ATTR_UPTIME, '_uptime_sec', int, 0)
        ]
        
        for attr_name, instance_var, type_converter, default_value in attribute_mappings:
            if attr_name in state.attributes:
                try:
                    raw_value = state.attributes[attr_name]
                    converted_value = type_converter(raw_value)
                    setattr(self, instance_var, converted_value)
                    _LOGGER.debug(
                        "Restored %s = %s for %s",
                        instance_var,
                        converted_value,
                        self.entity_id
                    )
                except (ValueError, TypeError) as exc:
                    _LOGGER.warning(
                        "Failed to convert attribute %s (value: %s) to %s for %s: %s. Using default: %s",
                        attr_name,
                        raw_value,
                        type_converter.__name__,
                        self.entity_id,
                        exc,
                        default_value
                    )
                    setattr(self, instance_var, default_value)
            else:
                # Set default if attribute doesn't exist
                setattr(self, instance_var, default_value)
                _LOGGER.debug(
                    "Attribute %s not found, using default %s = %s for %s",
                    attr_name,
                    instance_var,
                    default_value,
                    self.entity_id
                )

        # Ensure _value is never None (defensive programming)
        if self._value is None:
            self._value = 0
            _LOGGER.warning("_value was None after restoration, defaulting to 0 for %s", self.entity_id)

        # Update valid reference flag based on uptime
        self._valid_ref = self._uptime_sec > 0
        
        # Update the state after restoration
        self.update_state_value()
        
        _LOGGER.info(
            "State restoration completed for %s: value=%s, old_value=%s, uptime=%s, valid_ref=%s",
            self.entity_id,
            self._value,
            self._old_value,
            self._uptime_sec,
            self._valid_ref
        )

    async def load_state_from_recorder1 (self):
        if self._value is not None:
           return

        state = await self.async_get_last_state()
        if not state:
            _LOGGER.info(" async_added_to_hass can't find stats %s",str(state)) 
            # first time init
            self._value = 0
            self._old_value = 0
            self._valid_ref = False
            self.update_state_value ()
            self.async_write_ha_state()
            return

        self._state = state.state

        _LOGGER.info("async_added_to_hass %s",str(state.attributes)) 

        # restore from recorder
        for attr, var, t in ((ATTR_VALUE,'_value',int),
                             (ATTR_OLD_VALUE,'_old_value',int),
                             (ATTR_UPTIME,'_uptime_sec',int)
                     ):
            if attr in state.attributes:
                try:
                  setattr(self, var, t(state.attributes[attr]))
                except Exception as e:
                  _LOGGER.error("converting %s to %s ",state.attributes[attr],var)

        if self._value is None:
            self._value =0

       # update valid ref 
        if self._uptime_sec > 0:
           self._valid_ref = True
        self.update_state_value ()


    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Return true if the device is available."""
        return self._available


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
        if self._value is None:
            return {}

        return {
            ATTR_VALUE: self._value,
            ATTR_OLD_VALUE: self._old_value,
            ATTR_UPTIME : self._uptime_sec
        }

    @property
    def icon(self):
        """Return the icon."""
        return self._icon


