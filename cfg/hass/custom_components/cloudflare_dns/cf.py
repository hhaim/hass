"""
Cloudflare DNS Manager - A class for managing IPv4 DNS records via Cloudflare API
Requires: pip install cloudflare
"""

import cloudflare
from typing import Optional, Dict, Any, List


class CloudflareDNSManager:
    """
    A class to manage Cloudflare DNS records using the official Cloudflare Python library.
    
    This class provides methods to get and update IPv4 DNS A records.
    """
    
    def __init__(self, api_token: str):
        """
        Initialize the CloudflareDNSManager with API token.
        
        Args:
            api_token (str): Cloudflare API token with DNS edit permissions
        """
        self.api_token = api_token
        self.cf = cloudflare.Cloudflare(api_token=api_token)
    
    def _get_zone_id(self, domain: str) -> str:
        """
        Get the zone ID for a given domain.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            
        Returns:
            str: Zone ID
            
        Raises:
            Exception: If zone is not found or API call fails
        """
        try:
            zones = self.cf.zones.list(name=domain)
            if not zones.result:
                raise Exception(f"Zone not found for domain: {domain}")
            return zones.result[0].id
        except Exception as e:
            raise Exception(f"Failed to get zone ID for {domain}: {str(e)}")
    
    def _get_dns_record(self, zone_id: str, name: str, record_type: str = 'A') -> Optional[Dict[str, Any]]:
        """
        Get DNS record by name and type.
        
        Args:
            zone_id (str): Cloudflare zone ID
            name (str): DNS record name
            record_type (str): DNS record type (default: 'A')
            
        Returns:
            Optional[Dict[str, Any]]: DNS record data or None if not found
        """
        try:
            records = self.cf.dns.records.list(zone_id=zone_id, name=name, type=record_type)
            if records.result:
                return {
                    'id': records.result[0].id,
                    'name': records.result[0].name,
                    'content': records.result[0].content,
                    'type': records.result[0].type,
                    'ttl': records.result[0].ttl
                }
            return None
        except Exception as e:
            raise Exception(f"Failed to get DNS record {name}: {str(e)}")
    
    def get_ipv4_record(self, domain: str, name: str) -> Optional[str]:
        """
        Get the IPv4 address for a DNS A record.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            name (str): The DNS record name (e.g., 'subdomain.example.com' or '@' for root)
            
        Returns:
            Optional[str]: The IPv4 address or None if not found
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            record = self._get_dns_record(zone_id, name, 'A')
            return record['content'] if record else None
        except Exception as e:
            raise Exception(f"Failed to get IPv4 record for {name}: {str(e)}")
    
    def update_ipv4_record(self, domain: str, name: str, new_ipv4: str) -> bool:
        """
        Update an IPv4 DNS A record.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            name (str): The DNS record name (e.g., 'subdomain.example.com' or '@' for root)
            new_ipv4 (str): The new IPv4 address
            
        Returns:
            bool: True if update was successful, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            record = self._get_dns_record(zone_id, name, 'A')
            
            if not record:
                raise Exception(f"DNS A record not found for {name}")
            
            # Update the record
            self.cf.dns.records.update(
                dns_record_id=record['id'],
                zone_id=zone_id,
                type='A',
                name=name,
                content=new_ipv4,
                ttl=record.get('ttl', 300)
            )
            return True
            
        except Exception as e:
            raise Exception(f"Failed to update IPv4 record for {name}: {str(e)}")
    
    def create_ipv4_record(self, domain: str, name: str, ipv4: str, ttl: int = 300) -> bool:
        """
        Create a new IPv4 DNS A record.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            name (str): The DNS record name (e.g., 'subdomain.example.com' or '@' for root)
            ipv4 (str): The IPv4 address
            ttl (int): Time to live in seconds (default: 300)
            
        Returns:
            bool: True if creation was successful, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            
            self.cf.dns.records.create(
                zone_id=zone_id,
                type='A',
                name=name,
                content=ipv4,
                ttl=ttl
            )
            return True
            
        except Exception as e:
            raise Exception(f"Failed to create IPv4 record for {name}: {str(e)}")
    
    def list_dns_records(self, domain: str, record_type: str = 'A') -> List[Dict[str, Any]]:
        """
        List all DNS records of a specific type for a domain.
        
        Args:
            domain (str): The domain name
            record_type (str): DNS record type (default: 'A')
            
        Returns:
            List[Dict[str, Any]]: List of DNS records
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            records = self.cf.dns.records.list(zone_id=zone_id, type=record_type)
            
            result = []
            for record in records.result:
                result.append({
                    'id': record.id,
                    'name': record.name,
                    'content': record.content,
                    'type': record.type,
                    'ttl': record.ttl
                })
            return result
        except Exception as e:
            raise Exception(f"Failed to list DNS records for {domain}: {str(e)}")

    def get_ipv6_record(self, domain: str, name: str) -> Optional[str]:
        """
        Get the IPv6 address for a DNS AAAA record.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            name (str): The DNS record name (e.g., 'subdomain.example.com' or '@' for root)
            
        Returns:
            Optional[str]: The IPv6 address or None if not found
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            record = self._get_dns_record(zone_id, name, 'AAAA')
            return record['content'] if record else None
        except Exception as e:
            raise Exception(f"Failed to get IPv6 record for {name}: {str(e)}")
    
    
    def update_ipv6_record(self, domain: str, name: str, new_ipv6: str) -> bool:
        """
        Update an IPv6 DNS AAAA record.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            name (str): The DNS record name (e.g., 'subdomain.example.com' or '@' for root)
            new_ipv6 (str): The new IPv6 address
            
        Returns:
            bool: True if update was successful, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            record = self._get_dns_record(zone_id, name, 'AAAA')
            
            if not record:
                raise Exception(f"DNS AAAA record not found for {name}")
            
            # Update the record
            self.cf.dns.records.update(
                dns_record_id=record['id'],
                zone_id=zone_id,
                type='AAAA',
                name=name,
                content=new_ipv6,
                ttl=record.get('ttl', 300)
            )
            return True
            
        except Exception as e:
            raise Exception(f"Failed to update IPv6 record for {name}: {str(e)}")
    
    
    def create_ipv6_record(self, domain: str, name: str, ipv6: str, ttl: int = 300) -> bool:
        """
        Create a new IPv6 DNS AAAA record.
        
        Args:
            domain (str): The domain name (e.g., 'example.com')
            name (str): The DNS record name (e.g., 'subdomain.example.com' or '@' for root)
            ipv6 (str): The IPv6 address
            ttl (int): Time to live in seconds (default: 300)
            
        Returns:
            bool: True if creation was successful, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        try:
            zone_id = self._get_zone_id(domain)
            
            self.cf.dns.records.create(
                zone_id=zone_id,
                type='AAAA',
                name=name,
                content=ipv6,
                ttl=ttl
            )
            return True
            
        except Exception as e:
            raise Exception(f"Failed to create IPv6 record for {name}: {str(e)}")

