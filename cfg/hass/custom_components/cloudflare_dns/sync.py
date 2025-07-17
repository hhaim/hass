from abc import ABC, abstractmethod
from typing import Optional
import socket
import ipaddress

import logging

_LOGGER = logging.getLogger(__name__)


from .cf import CloudflareDNSManager
from .openwrt import Ubus

class IPInterface(ABC):
    """Abstract interface for IP address operations"""
    
    @abstractmethod
    def get_local(self) -> Optional[str]:
        """Get local IP address (IPv4 or IPv6)"""
        pass
    
    @abstractmethod
    def get_remote(self) -> Optional[str]:
        """Get remote IP address (IPv4 or IPv6)"""
        pass
    
    @abstractmethod
    def set_remote(self, ip: str) -> None:
        """Set remote IP address"""
        pass


class IPSynchronizer:
    """Synchronizes local and remote IP addresses"""
    
    def __init__(self, interface: IPInterface):
        self.interface = interface
        self._local_cache = None
        self._backoff_counter = 0
    
    def force_sync(self) -> bool:
        """
        Force sync: read local IP and set it on remote
        Returns True if sync was successful, False otherwise
        """
        local_ip = self.interface.get_local()
        if local_ip is None:
            _LOGGER.error("can't get local ip ")
            return False
        

        self.interface.set_remote(local_ip)
        self._local_cache = local_ip
        self._backoff_counter = 0  # Reset backoff on success
        return True
    
    def try_to_sync(self) -> bool:

        if self._local_cache is None:
            self.force_sync() # first time 
            return True 
        
        local_ip = self.interface.get_local()

        if local_ip is None:
            _LOGGER.error("can't get local addr ")
            return False
        
        # Update local cache if it's different
        if local_ip != self._local_cache:
            _LOGGER.info(" set addr {} {} ".format( local_ip,self._local_cache))
            self._local_cache = local_ip
            
            # Update remote and remote cache
            self.interface.set_remote(local_ip)
            return True
        
        # No change needed
        return False
            
    def do_backoff(self):
        self._backoff_counter += 1
        if self._backoff_counter > 8:
            self._backoff_counter = 8

    def do_sync(self) -> bool:
        """
        Perform sync with exponential backoff on errors.
        Uses try_to_sync() and backs off by factor 2 up to 64 on failures.
        Returns True if sync was successful, False if should skip this attempt due to backoff.
        """
        # Calculate current backoff threshold (2^counter, max 64)
        backoff_threshold = min(2 ** self._backoff_counter, 64)
        
        # If we're in backoff and haven't reached the threshold, skip this attempt
        if self._backoff_counter > 0 and backoff_threshold > 1:
            # Decrement the backoff counter for next call
            self._backoff_counter -= 1
            return False
        
        # Try to sync
        if self.try_to_sync():
            # Success - reset backoff counter
            self._backoff_counter = 0 # no exception 
            return True
    
    def get_cached_local_ip(self) -> Optional[str]:
        """Get the currently cached local IP address"""
        return self._local_cache
    
    
    def get_backoff_counter(self) -> int:
        """Get the current backoff counter value"""
        return self._backoff_counter
    
    def clear_cache(self) -> None:
        """Clear both internal caches and reset backoff counter"""
        self._local_cache = None
        self._backoff_counter = 0



# sync ipv4
class IPInterfaceV4(IPInterface):
    """Example implementation for testing"""
    
    def __init__(self,host, username, password,
                token, domain,ipv4domain):
        self._ubus= Ubus(host, username, password)
        self._cm = None 
        self._cm_token = token
        self._domain = domain
        self._ipv4domain =ipv4domain
    
    def get_local(self) -> Optional[str]:
        self._ubus.login()
        local_ipv4 = self._ubus.get_active_public_ipv4()
        self._ubus.logout()    
        return local_ipv4

    def init_blocking_cm(self):
        if self._cm == None:
            self._cm = CloudflareDNSManager(self._cm_token)

    def get_remote(self) -> Optional[str]:
        self.init_blocking_cm()
        return  self._cm.get_ipv4_record(self._domain, self._ipv4domain)
    
    def set_remote(self, ip: str) -> None:
        self.init_blocking_cm()
        self._cm.update_ipv4_record(self._domain, self._ipv4domain,ip)


def get_local_host_public_ipv6():
    """
    Get public IPv6 address by parsing network interfaces directly.
    Works better in Docker host mode.
    """
    try:
        # Method 1: Parse /proc/net/if_inet6 (Linux specific)
        with open('/proc/net/if_inet6', 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    # Convert hex representation to IPv6 address
                    hex_addr = parts[0]
                    # Insert colons every 4 characters
                    ipv6_hex = ':'.join([hex_addr[i:i+4] for i in range(0, len(hex_addr), 4)])
                    
                    try:
                        ip_obj = ipaddress.IPv6Address(ipv6_hex)
                        if ip_obj.is_global:
                            return str(ip_obj)
                    except ipaddress.AddressValueError:
                        continue
                        
    except (FileNotFoundError, PermissionError):
        pass
    
    return None

# sync ipv6
class IPInterfaceV6(IPInterface):
    """Example implementation for testing"""
    
    def __init__(self,
                token, domain,ipv6domain):
        self._cm = None 
        self._cm_token = token
        self._domain = domain
        self._ipv6domain =ipv6domain
    
    def init_blocking_cm(self):
        if self._cm == None:
            self._cm = CloudflareDNSManager(self._cm_token)

    def get_local(self) -> Optional[str]:
        return get_local_host_public_ipv6()
    
    def get_remote(self) -> Optional[str]:
        self.init_blocking_cm()
        return  self._cm.get_ipv6_record(self._domain, self._ipv6domain)
    
    def set_remote(self, ip: str) -> None:
        self.init_blocking_cm()
        self._cm.update_ipv6_record(self._domain, self._ipv6domain,ip)





          

