import ipaddress
import logging
from functools import lru_cache
from typing import Union, Any, Dict, Optional

import requests

from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert
from mongoose.models.configuration import GeoIPConfiguration
from mongoose.utils.exceptions import IgnoreCacheException

logger = logging.getLogger("urllib3.connectionpool")
logger.setLevel(logging.ERROR)


class GeoIP:
    def __init__(self, geoip_configuration: GeoIPConfiguration):
        self.geoip_configuration = geoip_configuration

    @lru_cache(maxsize=512)
    def request_geoip(self, ip_address: str) -> Optional[Dict[Any, Any]]:
        try:
            response = requests.get(self.geoip_configuration.remote_service_url + "/" + ip_address, timeout=1)
            if response.status_code == 200:
                return response.json()
        except (Exception,):
            pass
        raise IgnoreCacheException()  # prevents caching

    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "src_ip") or not hasattr(event, "dst_ip"):
            return

        src_ip = ipaddress.ip_address(event.src_ip)
        dst_ip = ipaddress.ip_address(event.dst_ip)
        if src_ip.is_global:
            try:
                event.enrichment["geoip"] = self.request_geoip(event.src_ip)
                event.enrichment["geoip"]["ip"] = event.src_ip
            except (Exception,):
                pass
        elif dst_ip.is_global:
            try:
                event.enrichment["geoip"] = self.request_geoip(event.dst_ip)
                event.enrichment["geoip"]["ip"] = event.dst_ip
            except (Exception,):
                pass
