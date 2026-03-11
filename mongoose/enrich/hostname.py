# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import socket
from functools import lru_cache
from typing import Union

from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert
from mongoose.utils.exceptions import IgnoreCacheException


class HostnameEnrichment:
    @lru_cache(maxsize=256)
    def get_hostname(self, ip_address: str):
        socket.setdefaulttimeout(0.4)
        try:
            return socket.gethostbyaddr(ip_address)[0]
        except socket.error:
            raise IgnoreCacheException

    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "src_ip") or not hasattr(event, "dst_ip"):
            return

        event.enrichment["src_hostname"] = ""
        event.enrichment["dst_hostname"] = ""

        try:
            event.enrichment["src_hostname"] = self.get_hostname(event.src_ip)
        except (Exception,):
            pass
        try:
            event.enrichment["dst_hostname"] = self.get_hostname(event.dst_ip)
        except (Exception,):
            pass
