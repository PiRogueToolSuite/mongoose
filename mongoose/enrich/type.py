from typing import Union

from mongoose.core.processing import ProcessingTopic
from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert


class EventTypeEnrichment:
    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if isinstance(event, NetworkDPI):
            event.enrichment["object_type"] = ProcessingTopic.NETWORK_DPI.value
        if isinstance(event, NetworkAlert):
            event.enrichment["object_type"] = ProcessingTopic.NETWORK_ALERT.value
        if isinstance(event, NetworkFlow):
            event.enrichment["object_type"] = ProcessingTopic.NETWORK_FLOW.value
