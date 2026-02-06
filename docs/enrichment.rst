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

- The enrichment worker is implemented by the class :class:`~mongoose.enrich.base.Enrich`.
- When started it subscribes to the processing queue topics for incoming
  network events::

    ProcessingTopic.NETWORK_DPI
    ProcessingTopic.NETWORK_ALERT
    ProcessingTopic.NETWORK_FLOW

- For each event the worker applies a set of automatic enrichers and, if
  configured, the GeoIP enricher. After enrichment the worker republishes the
  event on the corresponding "enriched" topic::

    ProcessingTopic.ENRICHED_NETWORK_DPI
    ProcessingTopic.ENRICHED_NETWORK_ALERT
    ProcessingTopic.ENRICHED_NETWORK_FLOW

- The automatic enrichers are created in ``Enrich.__init__``; GeoIP is
  created only when enrichment.geoip is present and enabled in the
  configuration.

Where enrichment runs
---------------------

The main loop is in ``mongoose/enrich/base.py``. It:

1. Subscribes to the input topics.
2. Deep-copies each received event so downstream processors don't see
   concurrent mutation.
3. Runs each enrichment implementation.
4. Publishes the enriched object on the appropriate topic.

Available enrichers
-------------------

The project ships a small set of focused enrichers. Each enricher receives a
network event object (one of :class:`~mongoose.models.network_dpi.NetworkDPI`, :class:`~mongoose.models.network_alert.NetworkAlert` or
:class:`~mongoose.models.network_flow.NetworkFlow`) and mutates the object in place by setting attributes or
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
  provide human-friendly names.
- Behavior: uses ``socket.gethostbyaddr`` with a short timeout.
- Notes: DNS failures are caught and do not stop enrichment.
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

Configuration
-------------

Enrichment configuration lives under the top-level ``enrichment`` key in the
application configuration model (:class:`~mongoose.models.configuration.EnrichmentConfiguration`).
The only supported sub-configuration at the time of writing is ``geoip``.

Example::

    enrichment:
      geoip:
        remote_service_url: "http://localhost:8080/geoip"
        enable: true

- ``remote_service_url``: URL of the GeoIP HTTP service. The enricher will
  append the IP address to this URL when making requests.
- ``enable``: whether to create the GeoIP enricher. If false or missing the
  GeoIP enrichment step is skipped.

How enrichment works
--------------------------------------------------------------------------------

- ``mongoose/enrich/base.py`` constructs the automatic enrichers in
  ``self.automatic_enrichment`` and conditionally instantiates ``GeoIP`` if
  the configuration exists and is enabled.
- The worker subscribes to the input topics, deep-copies the event to avoid
  accidental shared-state mutation, runs each enricher's
  ``enrich_network_event`` and then republishes using the processing queue.

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
