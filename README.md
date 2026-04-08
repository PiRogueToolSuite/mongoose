<!--
SPDX-FileCopyrightText: 2026 Defensive Lab Agency
SPDX-FileContributor: u039b <git@0x39b.fr>

SPDX-License-Identifier: GPL-3.0-or-later
-->

<div align="center">
<img width="60px" src="https://pts-project.org/android-chrome-512x512.png" alt="PTS logo">
<h1>Mongoose</h1>
<p>Collect, enrich, store and forward Suricata alerts and network flows.</p>
<p>
<img src="https://img.shields.io/badge/License-GPL_v3-8A2BE2" alt="License: GPL v3">
</p>
<p>
<a href="https://pts-project.org">Website</a> |
<a href="https://pts-project.org/mongoose/">Documentation</a> |
<a href="https://github.com/PiRogueToolSuite/mongoose">GitHub</a> |
<a href="https://discord.gg/qGX73GYNdp">Support</a>
</p>
</div>

![](https://github.com/PiRogueToolSuite/mongoose/raw/main/docs/_static/diagram.png)

Mongoose is a Python daemon and library for collecting, enriching, storing and
forwarding network events from Suricata and NFStream.

It runs a thread-safe pub-sub pipeline (`ProcessingQueue`) where collectors
publish raw events to topics and subscribers — enricher, SQLite store,
forwarders — consume them concurrently.

### Key features

- **Modular collectors**: Suricata EVE (alerts and netflow via Unix socket),
  NFStream (live packet capture from a network interface).
- **Automatic enrichment**: traffic direction (inbound / outbound / local),
  Community ID calculation, reverse DNS hostname lookup, event type
  classification, and flow risk scoring via a configurable severity cache.
- **GeoIP enrichment**: MaxMind (GeoLite2-ASN, GeoLite2-City,
  GeoLite2-Country) and IP66 databases, with daily automatic database updates.
- **Pluggable forwarders**: local file output, HTTP(S) webhooks (immediate,
  bulk or periodic modes with retry logic and multiple authentication methods),
  and Discord (rich embed formatting).
- **Topic filtering**: forwarders can be scoped to specific topics and filtered
  by event attributes.
- **Drop-in webhook configuration**: new webhook forwarders can be added at
  runtime by dropping a YAML file into a watched directory — no restart
  required.
- **SQLite storage**: enriched events are persisted with configurable history
  pruning by record count or age.
- **Sharded LRU cache**: thread-safe severity cache with optional TTL used for
  flow risk scoring.
- **Singleton engine**: a single `Engine` instance manages the full component
  lifecycle (start, stop, reload).
- **Systemd and PiRogue integration**: the CLI daemon supports `sd_notify` and
  reads the isolated interface from `pirogue-admin-client` when available.

### Pipeline topics

Events flow through the following pub-sub topics:

| Topic | Description |
|---|---|
| `network-dpi` | Raw DPI flows from NFStream |
| `network-alert` | Raw Suricata alerts |
| `network-flow` | Raw Suricata netflow records |
| `enriched-network-dpi` | Enriched DPI flows |
| `enriched-network-alert` | Enriched Suricata alerts |
| `enriched-network-flow` | Enriched netflow records |

### Installation

Install in a virtual environment and editable mode for development:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### CLI usage

The package installs a `mongoosed` daemon entry-point:

```bash
# show top-level help
mongoosed --help

# run with a configuration file
mongoosed --config /etc/mongoose/mongoose.yaml

# override the network interface used by NFStream
mongoosed --config mongoose.yaml --interface eth0

# set logging verbosity
mongoosed --config mongoose.yaml --logging-level DEBUG
```

### Python library usage

```python
import time
from mongoose.core.engine import Engine

engine = Engine("config.yaml")
engine.start()
time.sleep(6)
engine.stop()
```

### Configuration

Configured via a YAML file. All keys live under a top-level `configuration` key.

```yaml
configuration:
  collector:
    suricata:
      socket_path: "/run/suricata.socket"  # Suricata Unix socket
      collect_alerts: true                 # collect Suricata alerts
      collect_netflow: false               # collect Suricata netflow records
      enable: true

    nf_stream:
      interface: "eth0"          # network interface for live capture
      active_timeout: 120        # seconds before an active flow expires
      enable: false

  enrichment:
    geoip:
      source: "ip66"             # "ip66" (default) or "maxmind"
      enable: true

  forwarder:
    webhooks:
      - url: "https://hooks.example.com/ingest"
        auth_type: "bearer"      # none | basic | bearer | header
        auth_token: "${WEBHOOK_AUTH_TOKEN}"
        verify_ssl: true
        retry_count: 3
        retry_delay: 5.0
        timeout: 10.0
        mode: "immediate"        # immediate | bulk | periodic
        bulk_size: 10
        periodic_interval: 5.0
        periodic_rate: 10
        topics:
          - "enriched-network-dpi"
          - "enriched-network-alert"
        enable: true

  database_path: "mongoose.db"

  history:
    max_duration_days: 14  # keep records for at most 14 days
    max_records: null      # optional hard cap on row count per table
    enable: true

  cache:
    severity:
      max_size: 1024       # maximum entries in the severity LRU cache
      ttl_seconds: null    # optional TTL; null means entries never expire
      enable: true

  extra_configuration_dir: "/var/lib/mongoose"
```

#### Drop-in webhook configuration

Place a YAML file matching the `WebhookForwarderConfiguration` schema inside
`<extra_configuration_dir>/webhook.d/`. The engine watches this directory and
activates new forwarders when a file is created, and deactivates them when it
is deleted.

### Development

This project uses [UV](https://docs.astral.sh/uv/) and [Hatching](https://github.com/pypa/hatch)
has build tools. 

Once checked out, set up the project development environment with the following command:
```
uv sync --all-groups
```
