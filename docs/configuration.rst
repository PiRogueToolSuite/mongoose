.. index:: configuration

Configuration
=============

.. _configuration-overview:
Overview
--------

This document describes the configuration used by Mongoose and the most
important configuration keys that control collectors, enrichment, forwarders,
storage, and runtime behaviour. Use the shipped
``configuration_example.yaml`` in the project root as the canonical, full
example; this page summarizes the most commonly used options and shows a
small minimal example to get started.

.. _configuration-file-layout:
File layout
----------------------------------------

Mongoose reads configuration from a YAML file. The usual places to keep
configuration are:

- the repository example: ``configuration_example.yaml`` (recommended for reference),
- an application-specific file in ``/etc`` or under ``/var/lib`` when run as a system service, or
- a path passed to the application via the ``--config`` CLI option or an environment variable if supported by your deployment wrapper.

When the application starts it resolves configuration from a single YAML file that is validated against the application configuration model
``mongoose.models.configuration.Configuration``. Some components (notably forwarders that implement a plugin-style loader) can be configured via
drop-in directories. See the "Forwarders" section for details on ``/var/lib/mongoose/webhook.d/``.

.. _configuration-core-model:
Global settings
------------------------------

The validated top-level configuration model is defined in ``mongoose/models/configuration.py``. The core top-level keys in the model
are:

- ``collector`` : per-collector configuration (``suricata`` and ``nf_stream``).
- ``enrichment`` : enrichment configuration (for example ``geoip``).
- ``forwarder`` : forwarder/sink configuration (``file``, ``webhooks``, ``discord``).
- ``database_path`` : path to the application's SQLite database file.
- ``history`` : optional history retention configuration.
- ``extra_configuration_dir`` : directory used for drop-in configuration files (default ``/var/lib/mongoose/``).
- ``cache`` : cache configuration.


.. _configuration-collector:
Collectors
----------

Collectors are responsible for ingesting network events or flow records.
The configuration model exposes a single top-level ``collector`` key with
sub-keys matching the collector implementations. The two collectors modelled
in the configuration file are ``suricata`` and ``nf_stream``.

Example collector configuration::

    collector:
      suricata:
        socket_path: /run/suricata.socket
        collect_alerts: true
        collect_netflow: false
        enable: true
      nf_stream:
        interface: eth0
        active_timeout: 120
        max_nflows: 0
        enable: true

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

collector.suricata
  - ``socket_path`` (Path): Path to Suricata's socket file. Used to connect to Suricata for event ingestion.
  - ``collect_alerts`` (bool): Enable alerts ingestion.
  - ``collect_netflow`` (bool): Enable netflow collection if supported.
  - ``enable`` (bool): Toggle the Suricata collector on or off.

collector.nf_stream
  - ``interface`` (str) [required]: Network interface to capture from.
  - ``active_timeout`` (int): Seconds before an active flow is considered expired.
  - ``max_nflows`` (int): Limit on number of flows to capture (0 = unlimited).
  - ``enable`` (bool): Toggle NFStream collector on or off.

.. _configuration-enrichment:
Enrichment
----------

Enrichment runs between collection and forwarding to add derived fields and
context (for example, GeoIP lookups). The model exposes an ``enrichment``
top-level object with optional sub-objects such as ``geoip``.

GeoIP
~~~~~

Configuration of the GeoIP enricher::

    enrichment:
      geoip:
        remote_service_url: https://geoip.example/api/lookup
        enable: true

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``remote_service_url`` (str): Endpoint to perform GeoIP lookups. The application will call this service to resolve IP addresses to location/ASN.
- ``enable`` (bool): Toggle the GeoIP enricher.

.. _configuration-forwarders:
Forwarders
----------

Forwarders (also called sinks) deliver processed events to external systems. The validated model uses the top-level ``forwarder`` key. The available
sub-keys are ``file`` (a single file forwarder configuration) and two lists of webhook-style forwarders: ``webhooks`` and ``discord``.

File forwarder
~~~~~~~~~~~~~~

Configuration for the file forwarder::

    forwarder:
      file:
        output_dir: /var/log/mongoose
        topics: ["enriched-network-dpi", "enriched-network-alert"]
        prefix: mongoose-
        enable: true

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``output_dir`` (str): Directory where output files are written.
- ``topics`` (List[str]): Topics to write to files (controls filtering).
- ``prefix`` (str): Filename prefix applied to generated files.
- ``enable`` (bool): Enable or disable the file forwarder.

Webhook forwarder
~~~~~~~~~~~~~~~~~

Webhook forwarders are modelled as a list under ``forwarder.webhooks``.
Each webhook entry must conform to ``WebhookForwarderConfiguration``. The
model fields include ``url``, authentication options, retry settings and
timeouts.

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

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``url`` (HttpUrl | str) [required]: Destination URL for the webhook.
- ``headers`` (Dict[str,str]): Extra HTTP headers to include in each request.
- ``auth_type`` (str): Authentication mode, allowed values: ``none``, ``basic``, ``bearer``, ``header``.
- ``auth_token`` (SecretStr, optional): Token or credential. Required when auth_type != "none".
  - For ``basic``, the token must be "user:pass".
- ``auth_header_name`` (str): Header name to use when ``auth_type`` is ``header``.
- ``verify_ssl`` (bool): Whether to verify TLS/SSL certificates.
- ``retry_count`` (int): Number of retries on failure.
- ``retry_delay`` (float): Delay between retries in seconds.
- ``timeout`` (float): Request timeout in seconds.
- ``enable`` (bool): Enable or disable this webhook entry.
- ``topics`` (List[str]): Topics to forward to this endpoint.
- ``mode`` (str): Forwarding mode; allowed values: ``immediate``, ``bulk``, ``periodic``.
- ``bulk_size`` (int): When ``mode`` is ``bulk``, maximum items per batch.
- ``periodic_interval`` (float): When ``mode`` is ``periodic``, seconds between sends.
- ``periodic_rate`` (int): When ``mode`` is ``periodic``, max items per interval.

Role of forwarding modes
~~~~~~~~~~~~~~~~~~~~~~~~

- ``immediate``: Each event is delivered individually as it is processed.
  Use when low latency is required and the endpoint can handle the load.
- ``bulk``: Events are batched until ``bulk_size`` is reached and then sent
  as a group. Use to reduce per-request overhead.
- ``periodic``: Events are sent periodically according to
  ``periodic_interval`` and limited by ``periodic_rate``. Use when you want
  regular heartbeat-like deliveries or to rate-limit traffic.

Multiple webhook configurations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Mongoose supports loading drop-in configuration fragments from a
filesystem directory controlled by ``extra_configuration_dir`` (default
``/var/lib/mongoose/``). A conventional place for webhook snippets is
``/var/lib/mongoose/webhook.d/``. Each file should contain a YAML fragment
that matches parts of the validated model. Files are loaded in
lexicographic order and merged into the effective configuration.

Example drop-in file::

    # /var/lib/mongoose/webhook.d/10-internal.yaml
    forwarder:
      webhooks:
        - url: https://internal.example.local/hook
          headers:
            X-Internal-Token: s3cr3t
          auth_type: header
          auth_token: s3cr3t
          auth_header_name: X-Internal-Token
          retry_count: 5
          retry_delay: 2.0
          timeout: 8.0
          enable: true

Filename conventions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Files are loaded in lexicographic order; prefix files with numbers to
  control load order (``10-internal.yaml``, ``20-external.yaml``).
- When a file contains lists (for example ``forwarder.webhooks``) the
  entries are appended in load order. If a file contains scalar values for
  the same key as another file, the later file will override earlier
  values.

Discord forwarder
~~~~~~~~~~~~~~~~~

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

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- All properties from ``WebhookForwarderConfiguration`` (see above).
- ``username`` (str): Override the displayed username for webhook messages.
- ``avatar_url`` (str): Avatar image URL for the webhook message.
- ``allowed_mentions`` (Dict): Control which mentions are allowed; default is ``{"parse": []}`` to avoid mass pings.

.. _configuration-store:
Storage
----------------

The configuration model exposes a single path for storing the application's
database: ``database_path``. The repository historically included a
separate ``store.sqlite`` object in the docs; the current validated model
expects a single ``database_path`` value which points to the SQLite file.

Example::

    database_path: /var/lib/mongoose/mongoose.db

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``database_path`` (Path): Filesystem path to the SQLite database file used by Mongoose.
- ``history`` (HistoryConfiguration): Optional object to tune retention.
  - ``history.max_records`` (int, optional): Maximum records to retain in history tables.
  - ``history.max_duration_days`` (int, optional): Maximum number of days to retain records.
  - ``history.enable`` (bool): Toggle history retention logic.
- ``extra_configuration_dir`` (Path): Directory used to load drop-in YAML fragments (e.g. webhook.d).

.. _configuration-cache:
Cache & Processing
------------------

Caching is used for deduplication and speeding repeated lookups. The model
provides a ``cache`` object and a nested ``severity`` cache configuration.

Example::

    cache:
      severity:
        enable: true
        max_size: 1024
        ttl_seconds: 3600

Supported parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``enable`` (bool): Enable severity caching.
- ``max_size`` (int): Maximum number of severity entries to retain.
- ``ttl_seconds`` (float, optional): Optional TTL after which entries expire.

.. _configuration-example:
Example configuration
--------------------------

A small, end-to-end example that matches the models in
``mongoose.models.configuration``. This example wires Suricata → GeoIP →
file forwarder and a webhook entry via the core ``Configuration`` model::

    collector:
      suricata:
        socket_path: /run/suricata.socket
        collect_alerts: true
        collect_netflow: false
        enable: true
    enrichment:
      geoip:
        remote_service_url: https://geoip.example/api/lookup
        enable: true
    forwarder:
      file:
        output_dir: /var/log/mongoose
        topics: ["enriched-network-dpi"]
        prefix: mongoose-
        enable: true
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
    database_path: /var/lib/mongoose/mongoose.db
    extra_configuration_dir: /var/lib/mongoose/
    cache:
      severity:
        enable: true
        max_size: 1024

This example is intentionally minimal. See ``configuration_example.yaml``
for the fuller, repository-maintained schema.

.. _configuration-troubleshooting:
Tips and troubleshooting
------------------------

- Permission denied for files or directories: ensure the process user has
  read/write access to configured paths (logs, DB files, webhook.d).
- Missing GeoIP configuration: if ``enrichment.geoip`` is not configured the
  enricher will remain disabled; configure ``remote_service_url`` to enable
  it.
- Webhook 4xx errors: verify endpoint URL and headers; 4xx usually means a
  client configuration problem.
- Webhook 5xx or timeouts: increase webhook timeout and enable retries.
- Enable more verbose logging in your runtime wrapper when debugging
  pipeline issues.

.. _configuration-references:
References
----------

- Full example configuration: ``configuration_example.yaml`` in the project
  root.
- The validated configuration model: :mod:`mongoose.models.configuration`.
- Collector implementations: :mod:`mongoose.collect.nfstream_collector`,
  :mod:`mongoose.collect.suricata_eve_collector`.
- Enrichment modules: :mod:`mongoose.enrich.geoip`.
- Forwarders: :mod:`mongoose.forward.webhook`, :mod:`mongoose.forward.file`.
