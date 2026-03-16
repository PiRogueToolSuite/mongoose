.. index:: data models

Data models
===========

.. _data-models-overview:

Overview
--------

Mongoose collects, enriches, and stores two main types of network events:

- **Network DPI** — deep-packet inspection records produced by inspecting
  individual network flows in real time.
- **Network Alert** — security alerts raised by Suricata when a network
  packet or flow matches a detection rule.

Both event types share a common structure (identifiers, timestamps, IP
addresses and ports) and are later enriched with additional contextual
information such as geolocation, hostnames, and a risk score.

The sections below describe every field you will encounter when browsing,
filtering, or forwarding these events.

.. note::

   All timestamps are stored in `UTC
   <https://en.wikipedia.org/wiki/Coordinated_Universal_Time>`_. When
   Mongoose forwards events to an external system the ``time`` field follows
   the `ISO 8601 <https://en.wikipedia.org/wiki/ISO_8601>`_ format
   (e.g. ``2026-03-16T14:32:00``).

.. _data-models-network-dpi:

Network DPI
-----------

A **Network DPI** record represents a single observed network flow that has
been analysed with deep-packet inspection. It captures traffic statistics,
application identification, fingerprints, and is enriched with contextual
information such as geolocation and risk scoring.

.. _data-models-network-dpi-fields:

Fields
~~~~~~

Identifiers and timing
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``id``
     - Text
     - Unique identifier for this record. Generated automatically; you do not
       need to set it manually.
   * - ``time``
     - Date/time
     - The date and time at which Mongoose recorded this event.
   * - ``timestamp``
     - Number
     - The same point in time expressed as a Unix timestamp (number of seconds
       since 1 January 1970). Useful for sorting and range queries.
   * - ``community_id``
     - Text
     - A standardised identifier for the flow, computed from the source and
       destination addresses and ports using the `Community ID
       <https://github.com/corelight/community-id-spec>`_ specification. The
       same value is also stored in ``community_id_b64`` (Base64-encoded),
       which is convenient for use in URLs or systems that do not accept
       special characters. Use this field to correlate the same flow across
       different tools (Suricata, Zeek, Wireshark, etc.).

Network addresses and ports
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``ip_version``
     - Number
     - IP protocol version: ``4`` for IPv4 or ``6`` for IPv6.
   * - ``src_ip``
     - Text
     - IP address of the device that initiated the connection (source).
   * - ``src_mac``
     - Text
     - Hardware (MAC) address of the source network interface.
   * - ``src_port``
     - Number
     - Network port used by the source device.
   * - ``dst_ip``
     - Text
     - IP address of the device that received the connection (destination).
   * - ``dst_mac``
     - Text
     - Hardware (MAC) address of the destination network interface.
   * - ``dst_port``
     - Number
     - Network port used by the destination device. Well-known ports (80 for
       HTTP, 443 for HTTPS, etc.) help identify the type of service.

Protocol and application
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``protocol``
     - Text
     - Transport-layer protocol name (e.g. ``TCP``, ``UDP``).
   * - ``protocol_number``
     - Number
     - Numeric identifier for the transport protocol as defined by `IANA
       <https://www.iana.org/assignments/protocol-numbers/>`_ (e.g. ``6`` for
       TCP, ``17`` for UDP).
   * - ``application_name``
     - Text
     - Application identified by the deep-packet inspection engine (e.g.
       ``TLS``, ``HTTP``, ``DNS``). ``unknown`` when the traffic could not be
       classified.
   * - ``application_category_name``
     - Text
     - Broader category the identified application belongs to (e.g.
       ``Web``, ``Streaming``, ``VPN``). ``unknown`` when no category is
       available.
   * - ``requested_server_name``
     - Text
     - The server name requested by the client, extracted from TLS
       `SNI <https://en.wikipedia.org/wiki/Server_Name_Indication>`_ or
       similar negotiation. ``unknown`` when not available.
   * - ``client_fingerprint``
     - Text
     - A fingerprint of the client's TLS handshake, typically a `JA3
       <https://github.com/salesforce/ja3>`_ hash. Can be used to identify
       specific client software or detect anomalies. ``unknown`` when not
       available.
   * - ``server_fingerprint``
     - Text
     - A fingerprint of the server's TLS handshake (JA3S). Helps identify the
       server software or configuration. ``unknown`` when not available.

Traffic statistics
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``bidirectional_duration_ms``
     - Number
     - Total duration of the flow in milliseconds, counting both directions of
       traffic.
   * - ``bidirectional_bytes``
     - Number
     - Total number of bytes exchanged in both directions during the flow.
   * - ``bidirectional_packets``
     - Number
     - Total number of packets exchanged in both directions during the flow.
   * - ``src2dst_bytes``
     - Number
     - Number of bytes sent from the source to the destination.
   * - ``dst2src_bytes``
     - Number
     - Number of bytes sent from the destination back to the source.

Risk
^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``risk``
     - Number
     - Risk level assigned by the enrichment pipeline based on Suricata alert
       severity for this flow. Possible values:

       - ``0`` — normal traffic, no known threat.
       - ``1`` — suspicious traffic; worth investigating.
       - ``2`` — critical threat detected.

Enrichment and extra data
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``enrichment``
     - Object
     - A flexible container populated by Mongoose enrichers. See
       :ref:`data-models-enrichment` for the fields it may contain.
   * - ``extra``
     - Object
     - Additional raw data from the collector that does not fit into the
       standard fields above. The content depends on the collector
       configuration.

.. _data-models-network-dpi-example:

Example record
~~~~~~~~~~~~~~

A typical Network DPI record after enrichment looks like this::

    {
      "id": "a1b2c3d4e5f6...",
      "time": "2026-03-16T14:32:00",
      "timestamp": 1742131920.0,
      "community_id": "1:abc123==",
      "risk": 0,
      "bidirectional_duration_ms": 320,
      "bidirectional_bytes": 4096,
      "bidirectional_packets": 12,
      "protocol": "TCP",
      "protocol_number": 6,
      "ip_version": 4,
      "src_ip": "10.0.0.42",
      "src_mac": "aa:bb:cc:dd:ee:ff",
      "src_port": 54321,
      "dst_ip": "93.184.216.34",
      "dst_mac": "11:22:33:44:55:66",
      "dst_port": 443,
      "dst2src_bytes": 2048,
      "src2dst_bytes": 2048,
      "application_name": "TLS",
      "application_category_name": "Web",
      "requested_server_name": "example.com",
      "client_fingerprint": "e6573e91...",
      "server_fingerprint": "unknown",
      "enrichment": {
        "direction": "outbound",
        "src_hostname": "",
        "dst_hostname": "example.com",
        "geoip": {
          "country": "US",
          "country_name": "United States",
          "asn": 15133,
          "organization": "MCI Communications Services",
          "ip": "93.184.216.34"
        },
        "object_type": "network-dpi"
      },
      "extra": {}
    }

.. _data-models-network-alert:

Network Alert
-------------

A **Network Alert** record is created whenever Suricata matches a network
packet or flow against one of its detection rules. Every alert carries the
details of the matching rule (signature, category, severity) alongside the
network identifiers of the flow that triggered it.

.. _data-models-network-alert-fields:

Fields
~~~~~~

Identifiers and timing
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``id``
     - Text
     - Unique identifier for this alert record. Generated automatically.
   * - ``time``
     - Date/time
     - The date and time at which Mongoose received and recorded this alert.
   * - ``timestamp``
     - Number
     - The same point in time as a Unix timestamp.
   * - ``community_id``
     - Text
     - Community ID of the flow that triggered the alert. Use this to link
       the alert back to the corresponding Network DPI or Network Flow record.
   * - ``flow_id``
     - Number
     - Internal flow identifier assigned by Suricata. Can be used to
       cross-reference other Suricata log entries for the same flow.

Network addresses and ports
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``src_ip``
     - Text
     - IP address of the device that sent the offending traffic.
   * - ``src_port``
     - Number
     - Network port used by the source device.
   * - ``dst_ip``
     - Text
     - IP address of the device that received the offending traffic.
   * - ``dst_port``
     - Number
     - Network port used by the destination device.
   * - ``protocol``
     - Text
     - Transport-layer protocol of the flow (e.g. ``TCP``, ``UDP``).
   * - ``app_proto``
     - Text
     - Application protocol identified by Suricata for the flow (e.g.
       ``HTTP``, ``TLS``, ``DNS``). Empty when Suricata could not determine
       the application protocol.

Detection rule details
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``action``
     - Text
     - The action taken by Suricata when the rule matched. Common values are
       ``allowed`` (traffic was permitted but logged) and ``blocked`` (traffic
       was dropped).
   * - ``gid``
     - Number
     - Group identifier of the Suricata rule that fired. Usually ``1`` for
       community rules.
   * - ``signature_id``
     - Number
     - Unique numeric identifier of the detection rule (also called SID). You
       can look up the SID in threat intelligence databases such as
       `Emerging Threats <https://rules.emergingthreats.net/>`_ to read the
       full rule description.
   * - ``rev``
     - Number
     - Revision number of the rule. Higher revisions indicate that the rule
       has been updated since it was first published.
   * - ``signature``
     - Text
     - Human-readable name or description of the rule that matched, as written
       by the rule author. This is the most informative field for quickly
       understanding what threat was detected (e.g.
       ``ET MALWARE Suspicious User-Agent``).
   * - ``category``
     - Text
     - Threat category assigned by the rule author (e.g.
       ``Attempted Information Leak``, ``Trojan Activity``). Useful for
       grouping and filtering alerts by threat type.
   * - ``severity``
     - Number
     - Priority level set by the rule author. Lower numbers indicate higher
       severity (``1`` is the most critical, ``3`` is informational).
   * - ``rule``
     - Text
     - The full raw Suricata rule text. Intended for advanced users and
       analysts who want to inspect the exact detection logic.

Enrichment and extra data
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``enrichment``
     - Object
     - A flexible container populated by Mongoose enrichers. See
       :ref:`data-models-enrichment` for the fields it may contain.
   * - ``extra``
     - Object
     - Additional raw data from Suricata that does not fit into the standard
       fields above.

.. _data-models-network-alert-example:

Example record
~~~~~~~~~~~~~~

A typical Network Alert record after enrichment looks like this::

    {
      "id": "f7e8d9c0b1a2...",
      "time": "2026-03-16T14:33:10",
      "timestamp": 1742131990.0,
      "community_id": "1:xyz789==",
      "flow_id": 1234567890,
      "src_ip": "203.0.113.5",
      "src_port": 4444,
      "dst_ip": "10.0.0.42",
      "dst_port": 80,
      "protocol": "TCP",
      "app_proto": "HTTP",
      "action": "allowed",
      "gid": 1,
      "signature_id": 2008983,
      "rev": 6,
      "signature": "ET MALWARE Suspicious User-Agent (python-requests)",
      "category": "A Network Trojan was Detected",
      "severity": 1,
      "rule": "",
      "enrichment": {
        "direction": "inbound",
        "src_hostname": "",
        "dst_hostname": "",
        "geoip": {
          "country": "CN",
          "country_name": "China",
          "asn": 4134,
          "organization": "No.31,Jin-rong Street",
          "ip": "203.0.113.5"
        },
        "object_type": "network-alert"
      },
      "extra": {}
    }

.. _data-models-enrichment:

Enrichment fields
-----------------

Both Network DPI and Network Alert records carry an ``enrichment`` object that
is populated automatically by the Mongoose enrichment pipeline. The table
below lists all the fields you may find inside it.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``object_type``
     - Text
     - Identifies the kind of event: ``network-dpi``, ``network-alert``, or
       ``network-flow``.
   * - ``direction``
     - Text
     - Indicates the direction of the flow relative to the monitored network:
       ``inbound`` (traffic arriving from outside), ``outbound`` (traffic
       leaving the network), or ``local`` (traffic between two devices on the
       same network).
   * - ``src_hostname``
     - Text
     - Human-readable hostname for the source IP address, resolved via a
       reverse DNS lookup. Empty when no hostname could be found.
   * - ``dst_hostname``
     - Text
     - Human-readable hostname for the destination IP address. Empty when no
       hostname could be found.
   * - ``geoip``
     - Object
     - Geolocation and network ownership information for the public IP address
       in the flow (source if public, otherwise destination). See
       :ref:`data-models-enrichment-geoip` below.

.. _data-models-enrichment-geoip:

GeoIP fields
~~~~~~~~~~~~

When geolocation is enabled and a public IP address is present, the
``enrichment.geoip`` object will contain some or all of the following fields:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``ip``
     - Text
     - The IP address that was looked up.
   * - ``country``
     - Text
     - Two-letter country code (`ISO 3166-1 alpha-2
       <https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2>`_) of the IP
       address (e.g. ``US``, ``DE``, ``FR``).
   * - ``country_name``
     - Text
     - Full English name of the country (e.g. ``United States``,
       ``Germany``).
   * - ``continent``
     - Text
     - Two-letter continent code (e.g. ``EU``, ``NA``).
   * - ``continent_name``
     - Text
     - Full English name of the continent (e.g. ``Europe``,
       ``North America``).
   * - ``city``
     - Text
     - City associated with the IP address, when available.
   * - ``asn``
     - Number
     - `Autonomous System Number
       <https://en.wikipedia.org/wiki/Autonomous_system_(Internet)>`_ of the
       network that owns the IP address. Can help identify hosting providers,
       ISPs, or known malicious networks.
   * - ``organization``
     - Text
     - Name of the organisation that owns the Autonomous System (e.g.
       ``Amazon Technologies Inc.``, ``Deutsche Telekom AG``).
   * - ``latitude``
     - Number
     - Approximate latitude of the IP address location. Only present when a
       city-level database is configured.
   * - ``longitude``
     - Number
     - Approximate longitude of the IP address location. Only present when a
       city-level database is configured.
   * - ``timezone``
     - Text
     - IANA timezone name for the location (e.g. ``Europe/Berlin``). Only
       present when a city-level database is configured.
   * - ``accuracy_radius``
     - Number
     - Estimated accuracy radius (in kilometres) of the geolocation data.
       Only present when a city-level database is configured.

