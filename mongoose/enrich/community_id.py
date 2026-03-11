# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Union
import logging
import communityid

from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert

logger = logging.getLogger("communityid")
logger.setLevel(logging.ERROR)


class CommunityIDEnrichment:
    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "src_port") or not hasattr(event, "dst_port"):
            return

        if event.community_id:
            return

        cid = communityid.CommunityID()
        if hasattr(event, "protocol_number"):
            protocol = event.protocol_number
        else:
            protocol = communityid.get_proto(event.protocol)

        tpl = communityid.FlowTuple(protocol, event.src_ip, event.dst_ip, event.src_port, event.dst_port)
        event.community_id = cid.calc(tpl)
