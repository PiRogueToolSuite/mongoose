Enrichment
==========

Purpose
-------

Enrichment augments raw network events with additional derived information that
is useful for display, filtering, correlation and forwarding. Enrichers run
inside the enrichment worker and add fields like direction, hostnames, GeoIP
information, community IDs and a flow risk score.

High-level architecture
-----------------------

When Mongoose enrichment worker is started it subscribes to the processing queue topics for incoming
network events::

    ProcessingTopic.NETWORK_DPI = "network-dpi"
    ProcessingTopic.NETWORK_ALERT = "network-alert"
    ProcessingTopic.NETWORK_FLOW = "network-flow"


For each event the worker applies a set of automatic enrichers and, if
configured, the GeoIP enricher. After enrichment the worker republishes the
event on the corresponding "enriched" topic::

    ProcessingTopic.ENRICHED_NETWORK_DPI = "enriched-network-dpi"
    ProcessingTopic.ENRICHED_NETWORK_ALERT = "enriched-network-alert"
    ProcessingTopic.ENRICHED_NETWORK_FLOW = "enriched-network-flow"



Available enrichers
-------------------

The project ships a small set of focused enrichers. Each enricher receives a
network event and mutates the object in place by setting attributes or
adding entries to the ``event.enrichment`` dictionary.

Flow direction
~~~~~~~~~~~~~~~~~~~

- Documentation: :class:`~mongoose.enrich.direction.DirectionEnrichment`
- Purpose: classifies whether a flow is "inbound", "outbound" or "local".
- When it runs: always part of the automatic enrichers.

Community ID
~~~~~~~~~~~~~~~~~~~~~

- Documentation: :class:`~mongoose.enrich.community_id.CommunityIDEnrichment`
- Purpose: computes the Community ID for a flow to help with cross-system correlation.
- When it runs: always part of the automatic enrichers.

Hostname
~~~~~~~~~~~~~~~~~~

- Documentation: :class:`~mongoose.enrich.hostname.HostnameEnrichment`
- Purpose: attempts reverse DNS lookups for source/destination addresses to
  provide human-friendly names. It uses ``socket.gethostbyaddr`` with a short timeout.
- When it runs: always part of the automatic enrichers.

Flow risk
~~~~~~~~~~~~~~~~~~

- Documentation: :class:`~mongoose.enrich.risk.FlowRiskEnrichment`
- Purpose: attach a numeric risk/severity value to a flow based on severity information
  (0: normal, 1: suspicious, 2: critical) from Suricata alerts.
- When it runs: always part of the automatic enrichers.

Geo IP
~~~~~

- Documentation: :class:`~mongoose.enrich.geoip.GeoIP`
- Purpose: call an external GeoIP service for the public endpoint of the flow and attach the returned location metadata.
- When it runs: only when enabled.

Minimal event example
--------------------------------------------------------------------------------

Minimal input (synthetic) event::

    {
      "src_ip": "8.8.8.8",
      "dst_ip": "10.0.0.1",
      "src_port": 443,
      "dst_port": 52345,
      "protocol": "tcp",
      "enrichment": {}
    }

Possible enriched result after running all enrichers::

    {
      "src_ip": "8.8.8.8",
      "dst_ip": "10.0.0.1",
      "src_port": 443,
      "dst_port": 52345,
      "protocol": "tcp",
      "community_id": "1:abcd...",
      "risk": 2,
      "enrichment": {
        "direction": "inbound",
        "src_hostname": "dns.google",
        "dst_hostname": "",
        "geoip": {
          "country": "US",
          "city": "Mountain View",
          "ip": "8.8.8.8"
        },
        "object_type": "network-flow"
      }
    }
