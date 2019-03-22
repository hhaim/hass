"""
Support for my home TP-Link routers that has many type of old firmware 
hass drivers didn't work for my old routers and I wanted to extend the capability 

"""
import base64
from datetime import datetime
import hashlib
import logging
import re
from requests import get
from urllib.parse import quote
import urllib
import time


from aiohttp.hdrs import (
    ACCEPT, COOKIE, PRAGMA, REFERER, CONNECTION, KEEP_ALIVE, USER_AGENT,
    CONTENT_TYPE, CACHE_CONTROL, ACCEPT_ENCODING, ACCEPT_LANGUAGE)
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (STATE_ON, STATE_OFF,
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, HTTP_HEADER_X_REQUESTED_WITH)
import homeassistant.helpers.config_validation as cv



_LOGGER = logging.getLogger(__name__)

HTTP_HEADER_NO_CACHE = 'no-cache'

CONF_TPLINK_FW = 'firmware'
CONF_TPLINK_NAME = 'zname'
CONF_DISABLE_SWITCH = 'disable_input'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_TPLINK_FW): cv.string,
    vol.Required(CONF_TPLINK_NAME): cv.string,
    vol.Optional(CONF_DISABLE_SWITCH): cv.entity_id
})


def get_scanner(hass, config):
    """
    Validate the configuration and return a TP-Link scanner.

    The default way of integrating devices is to use a pypi

    package, The TplinkDeviceScanner has been refactored

    to depend on a pypi package, the other implementations

    should be gradually migrated in the pypi package

    """
    fw = config[DOMAIN][CONF_TPLINK_FW]
    fw_map = { 'base' : TPLinkBase ,'ac7':TPLinkAC7 ,'wr900': TPLinkWR900 , 'wr940':TPLinkWR940N}
    cls =fw_map[fw]
    scanner =  TPlinkScanner(config[DOMAIN],cls,hass)
    return (scanner)


class TpLinkLoginFail(Exception):
     pass

class TpLinkParseError(Exception):
     pass


class TPLinkBase:

    def __init__(self,ip,user,password):
        self.ip = ip
        self.user = user
        self.password = password
        self.ref=True
        self.reset_router_url()
        self.session_url=''
        self.do_hash=False
        self.dual_band=True
        self.login_state=False

    def reset_router_url (self):
        self.router_url = 'http://{0}/'.format(self.ip) 

    def set_name (self,name):
        self.name = name

    def convert_mac (self,mac):
        s=':'.join(mac.split('-'))
        s=s.lower()
        return(s);

    def parse_response (self,response):
        res= { 'hosts':[],
               'stats' : []}
        lines=response.split('\n');
        state='wait_for_stat'
        for l in lines :
            if state == 'wait_for_stat':
                if 'var wlanHostPara = new Array(' in l:
                    state = 'read_stats'
                continue
            if state == 'read_stats':
                a=l.split(',')
                if (len(a)>3):
                    k=list(map(int,a[:3]))
                    res['stats']=k
                    state = 'wait_for_hosts_start'
                else:
                    break;
                continue
            if state == 'wait_for_hosts_start':
                if 'var hostList = new Array(' in l:
                    state = 'wait_for_hosts'
                continue
            if state == 'wait_for_hosts':
                a=l.split(',')
                if (len(a)>4):
                   k=''.join(a[0].split('"'))
                   res['hosts'].append(self.convert_mac(k));
                   continue
                else:
                   return(res);
        raise TpLinkParseError("ERROR no host list"+response)

    def get_cookie (self,do_hash):
        password = self.password
        user = self.user
        if do_hash:
            password=hashlib.md5(password.encode('utf-8')).hexdigest()
        auth_bytes = bytes(user+":"+password, 'utf-8')
        auth_b64_bytes = base64.b64encode(auth_bytes)
        auth_b64_str = str(auth_b64_bytes, 'utf-8')
        auth_str='Authorization=Basic'+quote(' '+auth_b64_str)
        return (auth_str)

    def run_cmd (self,cmd):
        auth = {
        'Cookie': self.cookie
        }
        if self.ref:
           auth['Referer']=self.router_url

        url = "{0}userRpm/{1}".format(self.router_url,cmd)
        r = get(url, headers=auth)
        s=r.text;
        s1=s.encode('utf-8').decode('ascii', errors='ignore')
        return(s1)

    def logout (self):
        self.login_state=False

    def login (self):
       self.cookie = self.get_cookie(self.do_hash)
       self.login_state=True

    def check_login (self):
        if not self.login_state:
            self.login()
        return (self.login_state)

    def get_mp_devices (self,url):
        r=[]
        page=1
        pages = None
        while True:
          if page==1:
              page_str=''
          else:
              page_str="?Page={}".format(page)
          s=self.run_cmd(url+page_str)
          #print(s);
          tr=self.parse_response (s);
          #print(tr);
          if pages == None:
            # set pages onces 
            if len(tr['stats'])<3:
                break; # somthing wrong
            pages = min(int(tr['stats'][0]/(tr['stats'][2]+1)),5) # total/pages count
          r += tr['hosts']
          if page>pages:
              break;
          page +=1

        return r

    def get_list_devices (self):
       # retry login
       if not self.check_login ():
          return ([])
       r=[]
       r += self.get_mp_devices ('WlanStationRpm.html')
       if self.dual_band:
           r +=self.get_mp_devices ('WlanStationRpm_5g.html')
       return(r);




class TPLinkAC7(TPLinkBase): 

     def __init__(self,ip,user,password):
            super(TPLinkAC7, self).__init__(ip,user,password)
            self.do_hash =True


     def login (self):
         self.reset_router_url()
         self.cookie = self.get_cookie(self.do_hash)
         s=self.run_cmd('LoginRpm.htm?Save=Save')
         if self.router_url in s:
             url_auth_string = s.split(self.ip + '/')[1].split('/')[0]
             self.session_url = url_auth_string
             self.router_url = self.router_url +url_auth_string+'/'
             self.login_state=True
         else:
             raise TpLinkLoginFail(s)

     def logout (self):
        if not self.check_login ():
           return;
        self.run_cmd('LogoutRpm.html')
        self.login_state=False


class TPLinkWR940N(TPLinkAC7):

    def __init__(self,ip,user,password):
           super(TPLinkWR940N, self).__init__(ip,user,password)
           self.dual_band=False


class TPLinkWR900(TPLinkBase): 

    def __init__(self,ip,user,password):
           super(TPLinkWR900, self).__init__(ip,user,password)
           self.dual_band=False

    def get_cookie (self,do_hash):
        password = self.password
        user = self.user
        auth_bytes = bytes(user+":"+password, 'utf-8')
        auth_b64_bytes = base64.b64encode(auth_bytes)
        auth_b64_str = str(auth_b64_bytes, 'utf-8')
        auth_str='Basic '+auth_b64_str
        return (auth_str)


    def run_cmd (self,cmd):
        auth = {
        'Authorization': self.cookie
        }
        if self.ref:
           auth['Referer']=self.router_url

        url = "{0}userRpm/{1}".format(self.router_url,cmd)
        r = get(url, headers=auth)
        s=r.text;
        s1=s.encode('utf-8').decode('ascii', errors='ignore')
        return(s1)



class TPlinkScanner(DeviceScanner):

    def __init__(self, config,cls,hass):
        """Initialize the scanner."""

        host = config[CONF_HOST]
        password = config[CONF_PASSWORD]
        username = config[CONF_USERNAME]
        name =config[CONF_TPLINK_NAME]
        disable_switch = config.get(CONF_DISABLE_SWITCH, None)

        self.tp = cls(host,username,password);
        self.tp.set_name(name)
        self.last_results = []
        self.success_init = True
        self.switch = disable_switch
        self.hass = hass

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Get the name of the device."""
        return None

    def get_extra_attributes(self, device):
        return {'ap_name': self.tp.name }

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """

        self.last_results = []

        if self.switch:
            disable_read = self.hass.states.is_state(self.switch , STATE_ON)
            if disable_read:
               _LOGGER.error("wireless client {0} was disabled by user  ".format(self.tp.name))
               return True

        valid = False
        for i in range(0,3):
            try:
                self.tp.login(); 
                self.last_results = self.tp.get_list_devices ()
                self.tp.logout(); 
                #_LOGGER.info("wireless clients {0}: {1}".format(self.tp.name,str(self.last_results)))
                valid =True
                break;
            except Exception as e:
                pass;
                
        if not valid:
            _LOGGER.error("ERROR wireless getting device macs from device: " + self.tp.name)

        return valid ;



