"""Integrate with DuckDNS IPV4 and IPV6."""
from asyncio import iscoroutinefunction
from datetime import timedelta
import logging

import aiodns
from aiodns.error import DNSError
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_TXT = "txt"

DOMAIN = "duckdns_ipv4_ipv6"

INTERVAL = timedelta(minutes=5)

SERVICE_SET_TXT = "set_txt"

CONF_HOSTNAME = "hostname"
CONF_IPV4_MODE = "ipv4_mode"
CONF_IPV6_MODE = "ipv6_mode"
CONF_IPV4_RESOLVER = "ipv4_resolver"
CONF_IPV6_RESOLVER = "ipv6_resolver"

UPDATE_URL = "https://www.duckdns.org/update"
DEFAULT_HOSTNAME = "myip.opendns.com"
DEFAULT_IPV4_MODE = False
DEFAULT_IPV6_MODE = False
DEFAULT_IPV4_RESOLVER = "208.67.222.222"
DEFAULT_IPV6_RESOLVER = "2620:0:ccc::2"

CONF_OBJS = "objects"

_OBJ_SCHEMA = vol.All(
    vol.Schema({
            vol.Required(CONF_DOMAIN): cv.string,
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Optional(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
            vol.Optional(CONF_IPV4_MODE, default=DEFAULT_IPV4_MODE): vol.Any(
                False, "duckdns", "nameserver"
            ),
            vol.Optional(CONF_IPV6_MODE, default=DEFAULT_IPV6_MODE): vol.Any(
                False, "nameserver"
            ),
            vol.Optional(
                CONF_IPV4_RESOLVER, default=DEFAULT_IPV4_RESOLVER
            ): cv.string,
            vol.Optional(
                CONF_IPV6_RESOLVER, default=DEFAULT_IPV6_RESOLVER
            ): cv.string,
    }), 
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_OBJS): vol.All(
                    cv.ensure_list, [_OBJ_SCHEMA]),

            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_TXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TXT): vol.Any(None, cv.string),
    }
)


async def async_setup(hass, config):
    """Initialize the DuckDNS component."""
    cfg = config.get(DOMAIN)

    session = async_get_clientsession(hass)

    async def update_domain_interval(_now, dev):
        """Update the DuckDNS entry."""

        domain = dev[CONF_DOMAIN]
        token = dev[CONF_ACCESS_TOKEN]
        hostname = dev[CONF_HOSTNAME]
        ipv4_mode = dev[CONF_IPV4_MODE]
        ipv6_mode = dev[CONF_IPV6_MODE]
        ipv4_resolver = dev[CONF_IPV4_RESOLVER]
        ipv6_resolver = dev[CONF_IPV6_RESOLVER]

        return await _prepare_update(
            session,
            domain,
            token,
            hostname,
            ipv4_resolver,
            ipv6_resolver,
            ipv4_mode,
            ipv6_mode,
        )

    intervals = (
        timedelta(minutes=1),
        timedelta(minutes=5)
    )
    for dev in cfg.get(CONF_OBJS):
        async_track_time_interval_backoff(hass, update_domain_interval, intervals, dev)


    async def update_domain_service(call):
        """Update the DuckDNS entry."""
        await _update_duckdns(session, domain, token, txt=call.data[ATTR_TXT])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TXT, update_domain_service, schema=SERVICE_TXT_SCHEMA
    )

    return True


_SENTINEL = object()


async def _update_duckdns(
    session,
    domain,
    token,
    *,
    ipv4_addr=None,
    ipv6_addr=None,
    txt=_SENTINEL,
    clear=False,
):
    """Update DuckDNS."""
    params = {"domains": domain, "token": token}

    if txt is not _SENTINEL:
        if txt is None:
            # Pass in empty txt value to indicate it's clearing txt record
            params["txt"] = ""
            clear = True
        else:
            params["txt"] = txt

    if clear:
        params["clear"] = "true"

    if ipv4_addr:
        _LOGGER.debug(f"Got IPV4: {ipv4_addr}")
        params["ip"] = ipv4_addr

    if ipv6_addr:
        _LOGGER.debug(f"Got IPV6: {ipv6_addr}")
        params["ipv6"] = ipv6_addr

    try:
        resp = await session.get(UPDATE_URL, params=params)
        body = await resp.text()
    except:
        _LOGGER.warning(f"Unable to connect to DuckDNS to update '{domain}' domain")
        return False

    if body != "OK":
        _LOGGER.warning(f"Updating '{domain}' domain failed.")
        return False
    else:
        _LOGGER.info(f"Updating '{domain}' domain succeeded.")
        return True


async def _get_ip_address(hostname, resolver_addr, query_type):
    """Get IP address"""

    try:
        resolver = aiodns.DNSResolver()
        resolver.nameservers = [resolver_addr]
        response = await resolver.query(hostname, query_type)

    except:
        _LOGGER.warning(f"Unable to setup resolver: {hostname} - {resolver_addr}")
        return None

    if response:
        _LOGGER.debug(f"Got IP: {response[0].host}")
        return response[0].host
    else:
        _LOGGER.warning(f"Didn't get an IP from: {hostname} - {resolver_addr}")
        return None


async def _prepare_update(
    session,
    domain,
    token,
    hostname,
    ipv4_resolver,
    ipv6_resolver,
    ipv4_mode,
    ipv6_mode,
):
    ipv4_addr = None
    ipv6_addr = None
    success = True

    if ipv4_mode == "duckdns":
        _LOGGER.debug(f"Updating IPV4 with 'duckdns' mode")
        if not await _update_duckdns(session, domain, token):
            success = False

    elif ipv4_mode == "nameserver":
        _LOGGER.debug(f"Getting IPV4 address")
        ipv4_addr = await _get_ip_address(hostname, ipv4_resolver, "A")

    if ipv6_mode == "nameserver":
        _LOGGER.debug(f"Getting IPV6 address")
        ipv6_addr = await _get_ip_address(hostname, ipv6_resolver, "AAAA")

    if ipv4_addr or ipv6_addr:
        _LOGGER.debug(f"Updating IPV4 and/or IPV6 in nameserver mode")
        if not await _update_duckdns(
            session, domain, token, ipv4_addr=ipv4_addr, ipv6_addr=ipv6_addr
        ):
            success = False

    return success


@callback
@bind_hass
def async_track_time_interval_backoff(hass, action, intervals, dev) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively at every timedelta interval."""
    if not iscoroutinefunction:
        _LOGGER.error("Action needs to be a coroutine and return True/False")
        return

    if not isinstance(intervals, (list, tuple)):
        intervals = (intervals,)
    remove = None
    failed = 0

    async def interval_listener(now):
        """Handle elapsed intervals with backoff."""
        nonlocal failed, remove
        try:
            failed += 1
            if await action(now, dev):
                failed = 0
        finally:
            delay = intervals[failed] if failed < len(intervals) else intervals[-1]
            remove = async_call_later(hass, delay.total_seconds(), interval_listener)

    #hass.async_run_job(interval_listener, dt_util.utcnow())
    hass.async_create_task(interval_listener(dt_util.utcnow()))

    def remove_listener():
        """Remove interval listener."""
        if remove:
            remove()  # pylint: disable=not-callable

    return remove_listener
