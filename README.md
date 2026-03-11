<!--
SPDX-FileCopyrightText: 2026 Defensive Lab Agency
SPDX-FileContributor: u039b <git@0x39b.fr>

SPDX-License-Identifier: GPL-3.0-or-later
-->

<div align="center">
<img width="60px" src="https://pts-project.org/android-chrome-512x512.png" alt="PTS logo">
<h1>Mongoose</h1>
<p>
Lightweight dead-simple Python library to collect, enrich, store and forward
network events such as Suricata alerts and network flows
</p>
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

Mongoose — a lightweight dead-simple Python library and daemon to collect, enrich, store and forward
network events such as Suricata alerts and Deep Packet Inspection flows.

### Purpose

Mongoose provides a modular pipeline to ingest network events and flows,
enrich them with metadata (for example GeoIP and Community ID), persist
short-term state in a SQLite database, and forward processed records to
files, webhooks or other sinks. It is designed to be simple to configure,
extend and integrate into other applications.

### Overview
**Mongoose** is a versatile Python-based framework designed for the collection,
enrichment, and distribution of network security events and traffic flows. It acts
as a central hub for processing data from various network monitoring tools, providing a
modular and scalable pipeline for security analysts and researchers.

At its core, Mongoose utilizes a thread-safe **pub-sub engine** that allows for
concurrent processing of different data streams. Data is collected from sources
like Suricata EVE logs and NFStream, published to specific topics, and then
consumed by various modules for enrichment (e.g., GeoIP, Community ID), persistent
storage (SQLite), or forwarding to external endpoints via webhooks or local files.

The project is built with extensibility in mind, making it easy to integrate new
data sources and processing logic to adapt to different network monitoring needs.

### Key features

- Modular collectors: Suricata EVE, nfstream, file-based replay.
- Enrichment: GeoIP lookup, Community ID calculation and custom enrichers.
- Pluggable forwarders: file, webhook, Discord (extensible to new sinks).
- Lightweight SQLite storage for short-term persistence.
- Thread-safe pub-sub engine and safe caches for concurrent ingestion.

### Installation
Install in a virtual environment and editable mode for development:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### CLI usage
```bash
# show top-level help
mongoose --help

# run mongoose with a configuration file
mongoose --config docs/example_config_test.yaml
```

### Python library usage
Use Mongoose as a library when you can use in your application. The snippet
below shows how to instanciate the engine with a config and run it.
Replace the config path with your own file.

```python
import time
from mongoose.core.engine import Engine

# Create an Engine from a configuration file and run a single cycle.
configuration_file = "config.yaml"
engine = Engine(configuration_file)
engine.start()
time.sleep(6)
engine.stop()
```
