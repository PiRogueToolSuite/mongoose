import ipaddress
from typing import Union

from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert


class DirectionEnrichment:
    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "src_ip") or not hasattr(event, "dst_ip"):
            return

        src_ip = ipaddress.ip_address(event.src_ip)
        dst_ip = ipaddress.ip_address(event.dst_ip)

        event.enrichment["direction"] = "local"
        if src_ip.is_global:
            event.enrichment["direction"] = "inbound"
        elif dst_ip.is_global:
            event.enrichment["direction"] = "outbound"
