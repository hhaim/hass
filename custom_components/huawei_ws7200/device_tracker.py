"""
Support for my home huawei ws7200 ax3 wifi6 routers 
it is based on reverse engineering the js code and found similar code 
SCRAM challenge from https://github.com/jinxo13/HuaweiB525Router 
and this https://github.com/juacas/honor_x3

"""
from datetime import datetime
from requests import get
from urllib.parse import quote
import urllib
import time
import base64
from collections import namedtuple
import logging
import re
import json
import requests
import uuid
import hashlib
import hmac
from binascii import hexlify
import math
from requests import session 
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey.RSA import construct


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


CONF_ROUTER_FW = 'firmware'
CONF_ROUTER_NAME = 'zname'
CONF_DISABLE_SWITCH = 'disable_input'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_ROUTER_FW): cv.string,
    vol.Required(CONF_ROUTER_NAME): cv.string,
    vol.Optional(CONF_DISABLE_SWITCH): cv.entity_id
})


def get_scanner(hass, config):
    """
    Validate the configuration and return a TP-Link scanner.

    The default way of integrating devices is to use a pypi

    package, The DeviceScanner has been refactored

    to depend on a pypi package, the other implementations

    should be gradually migrated in the pypi package

    """
    fw = config[DOMAIN][CONF_ROUTER_FW]
    fw_map = { 'ws7200':HuaweiWS7200 }
    cls = fw_map[fw]
    scanner =  HuaweiScanner(config[DOMAIN],cls,hass)
    return (scanner)


class HuaweiLoginFail(Exception):
     pass

class HuaweiParseError(Exception):
     pass


def generate_nonce():
    """ generate random clientside nonce """
    return uuid.uuid4().hex + uuid.uuid4().hex


def get_client_proof(clientnonce, servernonce, password, salt, iterations):
    """ calculates server client proof (part of the SCRAM algorithm) """
    msg = "%s,%s,%s" % (clientnonce, servernonce, servernonce)
    salted_pass = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf_8'), bytearray.fromhex(salt), iterations)
    client_key = hmac.new(b'Client Key', msg=salted_pass,
                          digestmod=hashlib.sha256)
    stored_key = hashlib.sha256()
    stored_key.update(client_key.digest())
    signature = hmac.new(msg.encode('utf_8'),
                         msg=stored_key.digest(), digestmod=hashlib.sha256)
    client_key_digest = client_key.digest()
    signature_digest = signature.digest()
    client_proof = bytearray()
    i = 0
    while i < client_key.digest_size:
        client_proof.append(client_key_digest[i] ^ signature_digest[i])
        i = i + 1
    return hexlify(client_proof)


def rsa_encrypt(rsae, rsan, data):
    if data is None or data == '':
        return ''
    N = int(rsan, 16)
    E = int(rsae, 16)
    b64data = base64.b64encode(data)
    pubkey = construct((N, E))
    cipher = PKCS1_v1_5.new(pubkey)
    blocks = int(math.ceil(len(b64data) / 245.0))
    result = []
    for i in range(blocks):
        block = b64data[i * 245:(i + 1) * 245]
        d = cipher.encrypt(block)
        result.append(d)
    result = hexlify(''.join(result))
    if ((len(result) & 1) == 0):
        return result
    else:
        return '0' + result


class HuaweiWS7200:
    def __init__(self, host, username, password):
        """Initialize the client."""
        self.statusmsg = None
        self.host = host
        self.username = username
        self.password = password
        self.session = None
        self.login_data = None
        self.status = 'off'
        self.device_info = None
        self.name = 'unknown'

    def set_name (self,name):
        self.name = name

    # REBOOT THE ROUTER
    def reboot(self) -> bool:
        if not self.login:
            return False
        # REBOOT REQUEST
        try:
            data = {
                'csrf': {'csrf_param': self.login_data['csrf_param'], 'csrf_token': self.login_data['csrf_token']}}
            r = self.session.post('http://{0}/api/service/reboot.cgi'.format(self.host),
                                  data=json.dumps(data, separators=(',', ':')))
            data = json.loads(re.search('({.*?})', r.text).group(1))
            assert data['errcode'] == 0, data
            return True
        except Exception as e:
            return False
        finally:
            self.logout()

    # LOGIN PROCEDURE
    def login(self) -> bool:
        """
        Login procedure using SCRAM challenge
        :return: true if the login has succeeded
        """
        pass_hash = hashlib.sha256(self.password.encode()).hexdigest()
        pass_hash = base64.b64encode(pass_hash.encode()).decode()
        # INITIAL CSRF

        try:
            self.session = session()
            r = self.session.get('http://{0}/api/system/deviceinfo'.format(self.host), verify=False)
            self.status = 'on'
            device_info = r.json()
            assert device_info['csrf_param'] and device_info['csrf_token'], 'Empty csrf_param or csrf_token'
        except Exception as e:
            self.statusmsg = str(e)
            self.status = 'off'
            return False

        ## LOGIN ##
        try:
            pass_hash = self.username + pass_hash + \
                        device_info['csrf_param'] + device_info['csrf_token']
            firstnonce = hashlib.sha256(pass_hash.encode()).hexdigest()
            data = {'csrf': {'csrf_param': device_info['csrf_param'],
                             'csrf_token': device_info['csrf_token']},
                    'data': {'username': self.username, 'firstnonce': firstnonce}}
            r = self.session.post('http://{0}/api/system/user_login_nonce'.format(self.host),
                                  data=json.dumps(data, separators=(',', ':')), verify=False)
            responsenonce = r.json()
            salt = responsenonce['salt']
            servernonce = responsenonce['servernonce']
            iterations = responsenonce['iterations']
            client_proof = get_client_proof(firstnonce, servernonce, self.password, salt,
                                                   iterations).decode('UTF-8')

            data = {'csrf': {'csrf_param': responsenonce['csrf_param'],
                             'csrf_token': responsenonce['csrf_token']},
                    'data': {'clientproof': client_proof,
                             'finalnonce': servernonce}
                    }
            r = self.session.post('http://{0}/api/system/user_login_proof'.format(self.host),
                                  data=json.dumps(data, separators=(',', ':')), verify=False)
            loginproof = r.json()

            assert loginproof['err'] == 0

            self.login_data = loginproof
            self.statusmsg = None
            return True
        except Exception as e:
            self.statusmsg = 'Failed login: {0}'.format(e)
            self.login_data = None
            self.session.close()
            return False

    ## LOGOUT ##
    def logout(self):
        try:
            if self.login_data is None:
                return False
            data = {'csrf': {
                'csrf_param': self.login_data['csrf_param'],
                'csrf_token': self.login_data['csrf_token']
            }
            }
            r = self.session.post('http://{0}/api/system/user_logout'.format(
                self.host), data=json.dumps(data, separators=(',', ':')), verify=False)
            data = r.json()
            assert r.ok, r
        except Exception as e:
            pass
        finally:
            self.session.close()
            self.login_data = None

    def get_devices_response(self):
        """Get the raw string with the devices from the router."""
        # GET DEVICES RESPONSE
        macs =[]
        try:
            query = 'http://{0}/api/system/HostInfo'.format(self.host)
            r = self.session.get(query, verify=False)
            devices = r.json()
            for d in devices:
                if (d["Layer2Interface"]=="SSID1") or (d["Layer2Interface"]=="SSID5"): ## filter for wifi devices
                   macs.append(d["MACAddress"])
                    
            self.statusmsg = 'OK'
        except Exception as e:
            self.statusmsg = str(e)
            return macs
        return macs



class HuaweiScanner(DeviceScanner):

    def __init__(self, config,cls,hass):
        """Initialize the scanner."""

        host = config[CONF_HOST]
        password = config[CONF_PASSWORD]
        username = config[CONF_USERNAME]
        name =config[CONF_ROUTER_NAME]
        disable_switch = config.get(CONF_DISABLE_SWITCH, None)

        self.c = cls(host,username,password);
        self.c.set_name(name)
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
        return {'ap_name': self.c.name }

    def _update_info(self):
        """Ensure the information from the router is up to date.
           Return boolean if scanning successful.
        """

        self.last_results = []

        if self.switch:
            disable_read = self.hass.states.is_state(self.switch , STATE_ON)
            if disable_read:
               _LOGGER.error("wireless client {0} was disabled by user  ".format(self.c.name))
               return True
        valid = False
        for i in range(0,3):
            try:
                if self.c.login():
                    self.last_results = self.c.get_devices_response()
                    valid =True
                    self.c.logout(); 
                else:    
                    _LOGGER.error("wireless clients {0}: {1}".format(self.c.name,str(self.last_results)))
                break;
            except Exception as e:
                pass;

            if not valid:
                _LOGGER.error("ERROR wireless getting device macs from device: " + self.c.name)
            else:
                break    

        return valid



