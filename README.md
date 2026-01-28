<div align="center">
<img width="60px" src="https://pts-project.org/android-chrome-512x512.png">
<h1>Mongoose</h1>
<p>
Helpers to collect, enrich and store Suricata events and network flows.
</p>
<p>
<img src="https://img.shields.io/badge/License-GPL_v3-8A2BE2">
</p>
<p>
<a href="https://pts-project.org">Website</a> |
<a href="https://pts-project.org/mongoose/">Documentation</a> |
<a href="https://github.com/PiRogueToolSuite/mongoose">GitHub</a> |
<a href="https://discord.gg/qGX73GYNdp">Support</a>
</p>
</div>

> ⚠️ *This project is currently under active development and is not suitable for production use. Breaking changes may occur without notice. A stable release will be published to PyPI once development stabilizes.*

### Overview

**Mongoose** is a versatile Python-based framework designed for the collection, enrichment, and distribution of network security events and traffic flows. It acts as a central hub for processing data from various network monitoring tools, providing a modular and scalable pipeline for security analysts and researchers.

At its core, Mongoose utilizes a thread-safe **pub-sub engine** that allows for concurrent processing of different data streams. Data is collected from sources like Suricata EVE logs and NFStream, published to specific topics, and then consumed by various modules for enrichment (e.g., GeoIP, Community ID), persistent storage (SQLite), or forwarding to external endpoints via webhooks or local files.

The project is built with extensibility in mind, making it easy to integrate new data sources and processing logic to adapt to different network monitoring needs.

### Key features

- **Multi-source collection**: Collect events and network flows from multiple sources, including Suricata EVE logs and NFStream.
- **Real-time processing**: A thread-safe pub-sub engine for high-performance, concurrent processing of network data.
- **Data enrichment**: Automatically enrich network events with metadata like GeoIP information and Community ID.
- **Flexible storage**: Persistent storage of enriched events and flows in SQLite databases.
- **Extensible forwarding**: Forward processed data to external systems via Webhooks or save to local files in various formats.
- **Modular architecture**: Easily extendable with new collectors, enrichers, storers, and forwarders.
