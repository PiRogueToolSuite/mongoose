.. index:: configuration

Configuration
=============

.. _configuration-overview:

Overview
--------

This document describes the configuration used by Mongoose and the most
important configuration keys that control collectors, enrichment, forwarders,
storage, and runtime behaviour.

Example::

    configuration:
      database_path: "/var/lib/mongoose/mongoose.db"
      extra_configuration_dir: "/var/lib/mongoose/"

      history:
        max_duration_days: 14

      collector:
        suricata:
          socket_path: "/run/suricata.socket"
          collect_alerts: true
          collect_netflow: false
          enable: true

        nf_stream:
          interface: "enp5s0"
          active_timeout: 2
          max_nflows: 0
          enable: true

      enrichment:
        geoip:
          enable: true

      forwarder:
        discord:
          - url: https://discord.com/api/webhooks/...
            username: mongoose-bot
            avatar_url: https://example.org/avatar.png
            allowed_mentions:
              parse: [ ]
            enable: false

        webhooks:
          - url: https://example.org/hook
            headers:
              X-API-Key: secret
            auth_type: header
            auth_token: s3cr3t
            auth_header_name: X-API-Key
            verify_ssl: true
            retry_count: 3
            retry_delay: 5.0
            timeout: 10.0
            topics: ["enriched-network-dpi", "enriched-network-alert"]
            enable: false


.. _configuration-file-layout:

File layout
----------------------------------------

Mongoose reads configuration from a YAML file. The usual places to keep
configuration are:

- an application-specific file in ``/etc`` or under ``/var/lib`` when run as a system service, or
- a path passed to the application via the ``--config`` CLI option or an environment variable if supported by your deployment wrapper.

When the application starts it resolves configuration from a single YAML file that is validated against the application configuration model.
Some components (notably forwarders that implement a plugin-style loader) can be configured via
drop-in directories.

.. _configuration-core-model:

Top-level settings
------------------------------

The top-level configuration settings are:

- ``collector``: per-collector configuration (``suricata`` and ``nf_stream``).
- ``enrichment``: enrichment configuration (for example ``geoip``).
- ``forwarder``: forwarder/sink configuration (``file``, ``webhooks``, ``discord``).
- ``database_path``: path to the application's SQLite database file.
- ``history``: optional history retention configuration.
- ``extra_configuration_dir``: directory used for drop-in configuration files.
- ``cache``: cache configuration.


.. _configuration-collector:

Collectors
----------

Collectors are responsible for ingesting network events or flow records.

Example::

    collector:
      suricata:
        socket_path: /run/suricata.socket
        collect_alerts: true
        collect_netflow: false
        enable: true
      nf_stream:
        interface: eth0
        active_timeout: 120
        enable: true

Supported settings
^^^^^^^^^^^^^^^^^^

collector.suricata
  - ``socket_path``: Path to Suricata's socket file. Used to communicate with Suricata for event ingestion.
  - ``collect_alerts``: Enable alerts ingestion.
  - ``collect_netflow``: Enable netflow collection if supported.
  - ``enable``: Toggle the Suricata collector on or off.

collector.nf_stream
  - ``interface``: Network interface to capture from.
  - ``active_timeout``: Seconds before an active flow is considered expired.
  - ``enable``: Toggle NFStream collector on or off.

.. _configuration-enrichment:

Enrichment
----------

Enrichment runs between collection and forwarding to add derived fields and
context (for example, GeoIP lookups).

GeoIP
ˆˆˆˆˆ

Configuration of the GeoIP enricher::

    enrichment:
      geoip:
        maxmind_db_path: "/var/lib/GeoIP"
        maxmind_db:
          "GeoLite2-ASN.mmdb"
          "GeoLite2-City.mmdb"
          "GeoLite2-Country.mmdb"
        enable: true

Supported settings
^^^^^^^^^^^^^^^^^^

- ``maxmind_db_path``: The path to the GeoIP databases.
- ``maxmind_db``: The list of GeoIP databases to use.
- ``enable``: Toggle the GeoIP enricher.

.. _configuration-forwarders:

Forwarders
----------

Forwarders (also called sinks) deliver processed events to external systems.

File forwarder
^^^^^^^^^^^^^^

Save processed events into files::

    forwarder:
      file:
        output_dir: /var/log/mongoose
        topics: ["enriched-network-dpi", "enriched-network-alert"]
        prefix: mongoose-
        enable: true

Supported settings
""""""""""""""""""

- ``output_dir``: Directory where output files are written.
- ``topics``: Topics to write to files (controls filtering).
- ``prefix``: Filename prefix applied to generated files.
- ``enable``: Enable or disable the file forwarder.

Webhook forwarder
^^^^^^^^^^^^^^^^^

Example::

    forwarder:
      webhooks:
        - url: https://example.org/hook
          headers:
            X-API-Key: secret
          auth_type: header
          auth_token: s3cr3t
          auth_header_name: X-API-Key
          verify_ssl: true
          retry_count: 3
          retry_delay: 5.0
          timeout: 10.0
          enable: true
          topics: ["enriched-network-dpi"]
          mode: immediate

Supported settings
""""""""""""""""""

- ``url``: Destination URL for the webhook.
- ``headers``: Extra HTTP headers to include in each request.
- ``auth_type``: Authentication mode, allowed values: ``none``, ``basic``, ``bearer``, ``header``.
- ``auth_token``: Token or credential. Required when auth_type != "none".

  - For ``basic``, the token must be "user:pass".

- ``auth_header_name``: Header name to use when ``auth_type`` is ``header``.
- ``verify_ssl``: Whether to verify TLS/SSL certificates.
- ``retry_count``: Number of retries on failure.
- ``retry_delay``: Delay between retries in seconds.
- ``timeout``: Request timeout in seconds.
- ``enable``: Enable or disable this webhook entry.
- ``topics``: Topics to forward to this endpoint.
- ``mode``: Forwarding mode; allowed values: ``immediate``, ``bulk``, ``periodic``.

  - ``immediate``: Each event is delivered individually as it is processed.
    Use when low latency is required and the endpoint can handle the load.
  - ``bulk``: Events are batched until ``bulk_size`` is reached and then sent
    as a group. Use to reduce per-request overhead.
  - ``periodic``: Events are sent periodically according to
    ``periodic_interval`` and limited by ``periodic_rate``. Use when you want
    regular heartbeat-like deliveries or to rate-limit traffic.

- ``bulk_size``: When ``mode`` is ``bulk``, maximum items per batch.
- ``periodic_interval``: When ``mode`` is ``periodic``, seconds between sends.
- ``periodic_rate``: When ``mode`` is ``periodic``, max items per interval.

Multiple webhook configurations
"""""""""""""""""""""""""""""""

Mongoose supports loading drop-in configuration fragments from a
filesystem directory controlled by ``extra_configuration_dir`` (default
``/var/lib/mongoose/``). A conventional place for webhook snippets is
``/var/lib/mongoose/webhook.d/``. Each file should contain a YAML fragment
that matches parts of the validated model. Files are loaded in
lexicographic order and merged into the effective configuration.

Example drop-in file::

    # /var/lib/mongoose/webhook.d/10-internal.yaml
    url: https://internal.example.local/hook
    auth_type: header
    auth_token: s3cr3t
    auth_header_name: X-Internal-Token
    retry_count: 5
    retry_delay: 2.0
    timeout: 8.0
    enable: true


**Filename conventions**

- Files are loaded in lexicographic order; prefix files with numbers to
  control load order (``10-internal.yaml``, ``20-external.yaml``).
- When a file contains lists (for example ``forwarder.webhooks``) the
  entries are appended in load order. If a file contains scalar values for
  the same key as another file, the later file will override earlier
  values.

Discord forwarder
^^^^^^^^^^^^^^^^^

Discord forwarders are represented as a list under ``forwarder.discord``.
They reuse the webhook model fields and extend with Discord-specific
options such as ``username``, ``avatar_url`` and ``allowed_mentions``.

Example::

    forwarder:
      discord:
        - url: https://discord.com/api/webhooks/...
          username: mongoose-bot
          avatar_url: https://example.org/avatar.png
          allowed_mentions:
            parse: []
          enable: true

Supported settings
""""""""""""""""""

- All settings of the webhook configuration.
- ``username``: Override the displayed username for webhook messages.
- ``avatar_url``: Avatar image URL for the webhook message.
- ``allowed_mentions``: Control which mentions are allowed; default is ``{"parse": []}`` to avoid mass pings.

.. _configuration-store:

Storage
----------------

Supported settings
^^^^^^^^^^^^^^^^^^

- ``database_path``: Filesystem path to the SQLite database file used by Mongoose.
- ``history``: Optional object to tune retention.

  - ``history.max_records``: Maximum records to retain in history tables.
  - ``history.max_duration_days``: Maximum number of days to retain records.
  - ``history.enable``: Toggle history retention logic.

- ``extra_configuration_dir``: Directory used to load drop-in YAML fragments (e.g. webhook.d).
