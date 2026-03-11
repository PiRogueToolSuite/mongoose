# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Union

from mongoose.core.cache import SeverityCache
from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert


class FlowRiskEnrichment:
    def __init__(self):
        self.severity_cache = SeverityCache()

    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "community_id") or not hasattr(event, "risk"):
            return

        # Determine the level of risk (flow severity)
        try:
            event.risk = self.severity_cache.get_severity(event.community_id) or 0
        except (Exception,):
            event.risk = 0
