"""

sync openWrt multi-wan ipv4 public ip and local public ipv6 to cloudflare domains specified spec using API and token. 

How it works:
 at startup it just sync local to remote after that it pool the local and in case it was changed update the remote 

"""
import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import (
    CONF_API_KEY, 
    CONF_NAME
    )

from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later
from .sync import IPInterfaceV4, IPInterfaceV6, IPSynchronizer
from homeassistant.helpers.entity_component import EntityComponent


_LOGGER = logging.getLogger(__name__)

DOMAIN = "cloudflare_dns"

DEFAULT_NAME = 'cloudflare_dns'
CONF_DEBUG = "debug"

CONF_OWRT_HOST ="owrt_host" # router openwrt user 
CONF_OWRT_USER ="owrt_user" # router openwrt user 
CONF_OWRT_PASS ="owrt_pass" # router openwrt 
CONF_CF_DOMAIN ="domain" 
CONF_CF_IPV4_DOMAIN ="ipv4_domain" 
CONF_CF_IPV6_DOMAIN ="ipv6_domain" 
CONF_SYNC_CNT ="sync_count" 
CONF_SYNC_SEC ="sync_sec" 



# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
           vol.Required(CONF_API_KEY): cv.string, # cloudflare API 
           vol.Required(CONF_NAME): cv.string,
           vol.Required(CONF_OWRT_HOST): cv.string,
           vol.Required(CONF_OWRT_USER): cv.string,
           vol.Required(CONF_OWRT_PASS): cv.string,
           vol.Required(CONF_CF_DOMAIN):cv.string,
           vol.Required(CONF_CF_IPV4_DOMAIN):cv.string,
           vol.Required(CONF_CF_IPV6_DOMAIN):cv.string,
          
           vol.Optional(CONF_DEBUG, default=False): cv.boolean,
           vol.Optional(CONF_SYNC_SEC, default=10.0): vol.Coerce(float),
           vol.Optional(CONF_SYNC_CNT, default=3600): vol.Coerce(int),
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

ENTITY_ID = "cloudflare_dns.cloudflare_dns"
DATA_KEY = 'cloudflare_dns.devices'

DEPENDENCIES = ['discovery']

async def async_setup(hass, config):
    """Track the state of the sun."""
    cfg = config.get(DOMAIN)
    if DOMAIN not in hass.data:
       hass.data[DOMAIN] = {
    }


    component = EntityComponent(_LOGGER, DOMAIN, hass)
    
    # Create your entities
    entities = [
        CFDnsSensor(hass, cfg, False),
        CFDnsSensor(hass, cfg, True)
    ]
    
    # Add entities through the component
    await component.async_add_entities(entities)
    
    return True


class CFDnsSensor(Entity):


    """"""
    def __init__(self, hass, conf,ipv6):
        """Initialize the sensor."""
        super().__init__()
        self.hass = hass
        _synco =None
        self._ipv6 =ipv6

        if ipv6 == False:
            _synco = IPInterfaceV4( conf.get(CONF_OWRT_HOST),
                                    conf.get(CONF_OWRT_USER),
                                    conf.get(CONF_OWRT_PASS),
                                    conf.get(CONF_API_KEY) ,
                                    conf.get(CONF_CF_DOMAIN),
                                    conf.get(CONF_CF_IPV4_DOMAIN))
            self._name ='cf_ipv4'

        else:
            _synco = IPInterfaceV6(
                                       conf.get(CONF_API_KEY) ,
                                       conf.get(CONF_CF_DOMAIN),
                                       conf.get(CONF_CF_IPV6_DOMAIN))
            self._name ='cf_ipv6'

        self.entity_id = f"{DOMAIN}.cloudflare_dns_{self._name}"
        self._sync= IPSynchronizer(_synco)

        self._timer_sec = conf.get(CONF_SYNC_SEC)

        self._debug = conf.get(CONF_DEBUG)
        self._cnt_max = conf.get(CONF_SYNC_CNT)
        self._cnt = 0
        self._timer_handler = None 
        self._state =0
        self.start_timer()


    def start_timer(self):
        if self._timer_handler != None :
            self._timer_handler()
            self._timer_handler= None

        self._timer_handler = async_call_later(
            self.hass, self._timer_sec, self._timer_callback)


    async def _timer_callback(self, now):
        try:
          self._timer_handler = None
          await self.hass.async_add_executor_job(self.blocking_sync) # run blocking job 
        except Exception as err:
            self._sync.do_backoff()
            _LOGGER.error("Error while trying to get : %s", err)

        self.async_write_ha_state()     
        self.start_timer()


    def blocking_sync(self):
        self._sync.do_sync()
        self._state = self._state + 1
        self._cnt =self._cnt +1
        if self._cnt > self._cnt_max:
            self._cnt =0
            self._sync.force_sync() # from time to time force sync to make sure



       
    @property
    def name(self):
        """Return the name."""
        return self._name

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
        return { 
                    "is_ipv6"  : self._ipv6}
