# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import queue
import threading
from copy import deepcopy
from typing import Optional

from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.enrich.community_id import CommunityIDEnrichment
from mongoose.enrich.direction import DirectionEnrichment
from mongoose.enrich.geoip import MaxMindGeoIP, IP66GeoIP
from mongoose.enrich.hostname import HostnameEnrichment
from mongoose.enrich.risk import FlowRiskEnrichment
from mongoose.enrich.type import EventTypeEnrichment
from mongoose.models import NetworkDPI, NetworkAlert, NetworkFlow
from mongoose.models.configuration import EnrichmentConfiguration

logger = logging.getLogger(__name__)


class Enrich:
    def __init__(self, enrichment_configuration: EnrichmentConfiguration):
        self.pq = ProcessingQueue()
        self.queue = None
        self.enrichment_configuration = enrichment_configuration
        self.thread: Optional[threading.Thread] = None
        self.automatic_enrichment = [
            DirectionEnrichment(),
            CommunityIDEnrichment(),
            HostnameEnrichment(),
            EventTypeEnrichment(),
            FlowRiskEnrichment(),
        ]
        geoip_source = (
            enrichment_configuration.geoip.source or "ip66"
            if enrichment_configuration.geoip and enrichment_configuration.geoip.enable
            else None
        )
        if geoip_source and geoip_source.lower() == "maxmind":
            self.geoip_enrichment = MaxMindGeoIP(enrichment_configuration.geoip)
        elif geoip_source:
            self.geoip_enrichment = IP66GeoIP(enrichment_configuration.geoip)

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.queue = self.pq.subscribe(
            [ProcessingTopic.NETWORK_ALERT, ProcessingTopic.NETWORK_DPI, ProcessingTopic.NETWORK_FLOW], "enrichment"
        )

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"{self.__class__.__name__} started")

    def _run(self):
        while not self.pq.processing_stopped():
            try:
                data = self.queue.get(timeout=1.0)
                if data is None:
                    self.queue.task_done()
                    continue
                _data = deepcopy(data)
                self.queue.task_done()

                for enrichment in self.automatic_enrichment:
                    enrichment.enrich_network_event(_data)

                if self.geoip_enrichment:
                    self.geoip_enrichment.enrich_network_event(_data)

                if isinstance(_data, NetworkDPI):
                    self.pq.publish(ProcessingTopic.ENRICHED_NETWORK_DPI, _data)
                if isinstance(_data, NetworkAlert):
                    self.pq.publish(ProcessingTopic.ENRICHED_NETWORK_ALERT, _data)
                if isinstance(_data, NetworkFlow):
                    self.pq.publish(ProcessingTopic.ENRICHED_NETWORK_FLOW, _data)
            except queue.Empty:
                pass
            except (Exception,) as e:
                logger.error(e)
