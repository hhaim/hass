"""
Support for tracking MQTT enabled devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mqtt/
"""
import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICES
from homeassistant.components.mqtt import CONF_QOS
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['mqtt']

_LOGGER = logging.getLogger(__name__)

DMSMASQ_JSON_PAYLOAD_SCHEMA = vol.Schema({
    vol.Required("op"): cv.string,
    vol.Required("mac"): cv.string,
    vol.Required("host"): cv.string,
}, extra=vol.ALLOW_EXTRA)


CONF_MQTT_TOPIC = 'topic'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend({
    vol.Required(CONF_MQTT_TOPIC): cv.string,
})

HOME_MODE_AWAY = 'not_home'
HOME_MODE_HOME = 'home'

async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MQTT tracker."""
    topic = config[CONF_MQTT_TOPIC]
    qos = config[CONF_QOS]

    @callback
    def async_message_received(topic, payload, qos, dev_id=None):
        """Handle received MQTT message."""

        try:
            d = DMSMASQ_JSON_PAYLOAD_SCHEMA(json.loads(payload))
        except vol.MultipleInvalid:
            _LOGGER.error("Skipping update for following data "
                          "because of missing or malformatted data: %s",
                          payload)
            return
        except ValueError:
            _LOGGER.error("Error parsing JSON payload: %s", payload)
            return

        localtion=HOME_MODE_HOME
        if d['op']=='del':
            _LOGGER.info("mqtt_dnsmask:  skip {0}-{1}".format(d,localtion))
            return

        #_LOGGER.info("mqtt_dnsmask: {0}-{1}".format(d,localtion))
        hass.async_add_job(
            async_see(mac=d['mac'], host_name=d["host"], location_name=localtion,source_type="dhcp"))

    await mqtt.async_subscribe(
        hass, topic+"/+", async_message_received, qos)

    return True
