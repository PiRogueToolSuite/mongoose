.. index:: suricata integration

Suricata integration
====================

.. _suricata-integration-overview:

Overview
--------

`Suricata <https://suricata.io>`_ is an open-source network threat detection
engine. It inspects live traffic against a library of detection rules and
emits structured events in its **EVE JSON** format.

Mongoose consumes two of those event types:

- **alert** — raised each time a rule matches. Mongoose stores these as
  :ref:`data-models-network-alert` records and uses the alert's severity to
  compute the :ref:`risk score <correlation-risk>` on the matching flow.
- **netflow** — a per-flow summary emitted when a connection closes. Mongoose
  stores these as ``NetworkFlow`` records.

Communication between Suricata and Mongoose happens over a **Unix datagram
socket**. Suricata writes EVE JSON lines to the socket; Mongoose binds to
that socket and reads them in real time.

.. _suricata-integration-how-it-works:

How it works
------------

Suricata writes one JSON object per line to the socket as soon as an event
occurs. The :class:`~mongoose.collect.suricata_eve_collector.SuricataEveCollector`
reads each line, parses it, and publishes the result onto the internal
processing queue for enrichment and forwarding.

.. note::

   Mongoose **binds** the socket file — it creates and owns the file at
   ``socket_path``. Suricata is configured to write to that path.
   The socket type is ``AF_UNIX SOCK_DGRAM`` (Unix datagram), so no TCP/IP
   stack is involved and no network port is opened.

.. _suricata-integration-suricata-config:

Configuring Suricata
--------------------

The key section in ``suricata.yaml`` is the ``eve-log`` output. Mongoose
requires the following settings:

.. code-block:: yaml

   outputs:
     - eve-log:
       enabled: yes
       filetype: unix_dgram            # must be unix_dgram
       filename: /run/suricata.socket  # must match socket_path in Mongoose
       community-id: true              # required for flow correlation
       community-id-seed: 0            # keep at 0 to match Mongoose's default
       types:
         - alert:
           metadata:
             app-layer: true
             flow: true
             rule:
               metadata: true
               raw: true               # enables the full rule text in alerts
         - netflow                     # optional – only needed when collect_netflow: true

.. list-table:: Critical EVE-log settings
   :header-rows: 1
   :widths: 30 70

   * - Setting
     - Why it matters
   * - ``filetype: unix_dgram``
     - Tells Suricata to write to a Unix datagram socket instead of a
       regular log file. This is the only transport Mongoose supports.
   * - ``filename``
     - Path of the socket file. Must be identical to ``socket_path`` in
       the Mongoose collector configuration (default:
       ``/run/suricata.socket``).
   * - ``community-id: true``
     - Instructs Suricata to compute and include the Community ID in every
       event. Without this, :ref:`flow correlation <correlation-community-id>`
       will not work.
   * - ``community-id-seed: 0``
     - The seed used when computing the Community ID hash. Must be ``0``
       to match the value used by Mongoose's own Community ID enricher so
       that IDs produced by both tools are identical.
   * - ``alert`` under ``types``
     - Enables the alert event stream. Required when
       ``collect_alerts: true`` in Mongoose.
   * - ``rule.raw: true``
     - Includes the full Suricata rule text in the alert payload. This
       populates the ``rule`` field of :ref:`data-models-network-alert`.
   * - ``netflow`` under ``types``
     - Enables the netflow event stream. Only needed when
       ``collect_netflow: true`` in Mongoose.

.. _suricata-integration-home-net:

Suricata uses the ``HOME_NET`` variable to classify traffic as inbound or
outbound. It must be set to the IP range of the **isolated network** that
Mongoose monitors (the same network as the capture interface):

.. code-block:: yaml

   vars:
     address-groups:
       HOME_NET: "192.168.1.0/24"   # replace with your network range
       EXTERNAL_NET: "!$HOME_NET"

Mongoose's :ref:`direction enricher <enrichment>` uses the same concept: it
marks a flow as ``inbound``, ``outbound``, or ``local`` based on which side
of the connection falls inside the monitored network. Keeping both values
consistent avoids mismatches in the ``enrichment.direction`` field.

.. _suricata-integration-mongoose-config:

Configuring Mongoose
--------------------

On the Mongoose side, the Suricata collector is configured under
``collector.suricata``:

.. code-block:: yaml

   collector:
     suricata:
       socket_path: /run/suricata.socket   # must match Suricata's filename
       collect_alerts: true
       collect_netflow: false              # set to true to also ingest netflow
       enable: true

.. list-table:: Mongoose collector settings
   :header-rows: 1
   :widths: 30 15 55

   * - Setting
     - Default
     - Description
   * - ``socket_path``
     - ``/run/suricata.socket``
     - Filesystem path where Mongoose will create the Unix datagram socket.
       Suricata's EVE ``filename`` must point to the same path.
   * - ``collect_alerts``
     - ``true``
     - When enabled, Mongoose ingests Suricata ``alert`` events and stores
       them as :ref:`Network Alert <data-models-network-alert>` records.
   * - ``collect_netflow``
     - ``false``
     - When enabled, Mongoose ingests Suricata ``netflow`` events and stores
       them as ``NetworkFlow`` records. Suricata must also have ``netflow``
       listed under ``eve-log.types``.
   * - ``enable``
     - ``true``
     - Master switch for the whole Suricata collector.

.. _suricata-integration-startup-order:

Startup order
-------------

Because Mongoose **creates** the socket file, it must be started before
Suricata attempts to open the socket for writing. The recommended order is:

1. Start Mongoose (or the ``pirogue-mongoose`` service).
2. Start (or restart) Suricata so it opens the socket that Mongoose has
   already created.

If Suricata starts first and cannot find the socket, it will log a warning
and discard events until the socket appears. Mongoose tolerates a brief gap:
events emitted before the socket is bound will be lost, but the collector
will continue processing all subsequent events normally.

When using ``systemd``, the service unit already declares the correct
dependency order. If you manage both services manually, the same rule
applies: Mongoose first, then Suricata.

.. _suricata-integration-rules:

Detection rules
---------------

Mongoose does not manage Suricata rules directly. Rules are configured
in ``suricata.yaml`` under ``default-rule-path`` and ``rule-files``:

.. code-block:: yaml

   default-rule-path: /var/lib/suricata/rules
   rule-files:
     - suricata.rules

The ``signature``, ``category``, and ``severity`` fields that appear in
:ref:`data-models-network-alert` records come directly from these rules.
To customise which threats Suricata reports, update the rule files and reload
Suricata (e.g. ``suricatasc -c reload-rules``).

.. seealso::

   - :ref:`data-models-network-alert` — structure of the alert records
     produced from Suricata events.
   - :ref:`correlation-risk` — how alert severity becomes the ``risk`` field
     on Network DPI records.
   - :ref:`correlation-community-id` — how the Community ID links alerts to
     their corresponding DPI flows.
   - :ref:`configuration-collector` — full Mongoose collector configuration
     reference.

