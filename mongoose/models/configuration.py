# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field, HttpUrl, SecretStr, validator


class BasicFilter(BaseModel):
    """A filter that matches objects based on attribute values.

    This filter checks if an object has a specific attribute and whether
    the attribute's value is in a predefined list of allowed values.

    Attributes:
        attribute: The name of the attribute to check on the target object.
        values: List of acceptable values for the attribute.
    """

    attribute: str
    values: List[str]

    def matches(self, obj: Any) -> bool:
        """Check if the given object matches this filter.

        The object matches if it has the specified attribute and the
        attribute's value is in the list of allowed values.

        Args:
            obj: The object to check against this filter.

        Returns:
            True if the object has the attribute and its value is in the
            allowed values list, False otherwise.
        """
        if not hasattr(obj, self.attribute):
            return False
        value = getattr(obj, self.attribute)
        return value in self.values


class ForwarderConfiguration(BaseModel):
    enable: bool = Field(default=False)
    """Enable the forwarder. Defaults to False."""

    topics: List[str] = Field(default_factory=lambda: ["enriched-network-dpi", "enriched-network-alert"])
    """List of topics to forward. Defaults to ["enriched-network-dpi", "enriched-network-alert"]."""

    configuration_file: Path = None
    """Configuration file path, only set when loaded from a drop-in configuration."""

    filters: List[BasicFilter] = []
    """List of filters. Defaults to []."""


class WebhookForwarderConfiguration(ForwarderConfiguration):
    """Configuration for the Webhook Forwarder.

    This class defines the destination, authentication, and reliability settings
    for forwarding network events via webhooks.

    Security considerations:
        - **auth_token**: Stored as a `SecretStr` to ensure it is masked when the
          model is printed or logged. Always use `get_secret_value()` to access it.
        - **verify_ssl**: Defaults to `True`. Disabling this is a security risk as
          it allows man-in-the-middle attacks. Only disable it for testing with
          self-signed certificates in controlled environments.
        - **URL**: Ensure the `url` uses `https://` for encrypted transport of
          potentially sensitive network data.
    """

    url: Union[HttpUrl, str]
    """The destination URL for the webhook (must be a valid HTTP/HTTPS URL)."""

    headers: Dict[str, str] = Field(default_factory=dict)
    """Optional dictionary of additional HTTP headers to include in requests."""

    auth_type: str = Field(default="none")  # none, basic, bearer, header
    """Type of authentication ('none', 'basic', 'bearer', 'header')."""

    auth_token: Optional[SecretStr] = None
    """Credentials such as API key or token."""

    auth_header_name: str = Field(default="X-API-Key")
    """Name of the header if `auth_type` is 'header'."""

    verify_ssl: bool = Field(default=True)
    """Whether to verify SSL certificates. Defaults to True."""

    retry_count: int = Field(default=3, ge=0)
    """Number of retries for failed requests. Defaults to 3."""

    retry_delay: float = Field(default=5.0, ge=0)
    """Delay between retries in seconds. Defaults to 5.0."""

    timeout: float = Field(default=10.0, gt=0)
    """Request timeout in seconds. Defaults to 10.0."""

    # Forwarding modes
    mode: str = Field(default="immediate")  # immediate, bulk, periodic
    """Forwarding mode ('immediate', 'bulk', 'periodic'). Defaults to 'immediate'."""

    bulk_size: int = Field(default=10, ge=1)
    """Maximum number of items to batch in 'bulk' mode. Defaults to 10."""

    periodic_interval: float = Field(default=5.0, ge=0.1)
    """Time interval in seconds between sends in 'periodic' mode. Defaults to 5.0."""

    periodic_rate: int = Field(default=10, ge=1)
    """Maximum number of items to send per interval in 'periodic' mode. Defaults to 10."""

    @validator("mode")
    def validate_mode(cls, v):
        allowed = ["immediate", "bulk", "periodic"]
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        return v

    @validator("auth_type")
    def validate_auth_type(cls, v):
        allowed = ["none", "basic", "bearer", "header"]
        if v not in allowed:
            raise ValueError(f"auth_type must be one of {allowed}")
        return v

    @validator("auth_token", always=True)
    def validate_auth_token(cls, v, values):
        auth_type = values.get("auth_type")
        if auth_type and auth_type != "none" and not v:
            raise ValueError(f"auth_token is required when auth_type is '{auth_type}'")
        if auth_type == "basic" and v:
            if ":" not in v.get_secret_value():
                raise ValueError("auth_token must be in 'user:pass' format for basic auth")
        return v


class FileForwarderConfiguration(ForwarderConfiguration):
    """Configuration for the File Forwarder."""

    output_dir: str = "output"
    """The directory where the files will be created."""

    topics: List[str] = Field(
        default_factory=lambda: ["enriched-network-dpi", "enriched-network-alert", "enriched-network-flow"]
    )
    """List of topics to forward (e.g., ["enriched-network-dpi", "enriched-network-alert"])."""

    prefix: str = ""
    """Optional prefix for the filenames (e.g., "mongoose-")."""

    enable: bool = Field(default=False)
    """Enable the forwarder. Defaults to False."""


class NFStreamConfiguration(BaseModel):
    """Configuration for the NFStream collector."""

    active_timeout: int = Field(default=2 * 60, gt=0)
    """Time in seconds before an active flow is considered expired. Defaults to 120 (2 minutes)."""

    interface: str
    """Network interface to capture from (required)."""

    max_nflows: int = Field(default=0)
    """Maximum number of flows to be captured. Defaults to 0 (unlimited)."""

    enable: bool = Field(default=True)
    """Enable the NFStream collector. Defaults to True."""


class SuricataEveConfiguration(BaseModel):
    """A configuration for the Suricata EVE collector."""

    socket_path: Path = Path("/run/suricata.socket")
    """Specifies whether the Suricata EVE collector is disabled. Defaults to False."""

    collect_alerts: bool = Field(default=True)
    """Enable the alerts collector. Defaults to True."""

    collect_netflow: bool = Field(default=False)
    """Enable the netflow collector. Defaults to False."""

    enable: bool = Field(default=True)
    """Enable the Suricata EVE collector. Defaults to True."""


class GeoIPConfiguration(BaseModel):
    maxmind_db_path: Path = Path("/var/lib/GeoIP")
    """The path to the GeoIP databases."""

    maxmind_db: List[str] = ["GeoLite2-ASN.mmdb", "GeoLite2-City.mmdb", "GeoLite2-Country.mmdb"]
    """The list of GeoIP databases to use."""

    source: str = "ip66"  # maxmind or ip66
    """The source to use, either MaxMind or IP66. Defaults to IP66."""

    enable: bool = Field(default=False)
    """Enable the GeoIP enrichment. Defaults to False."""


class EnrichmentConfiguration(BaseModel):
    geoip: Optional[GeoIPConfiguration] = None


class DiscordForwarderConfiguration(WebhookForwarderConfiguration):
    """Discord-specific forwarder configuration.

    Inherits the generic webhook configuration and adds fields that are
    specific to Discord webhooks: `username`, `avatar_url`, and
    `allowed_mentions` to control mentions and avoid mass pings.
    """

    username: Optional[str] = None
    """Override the displayed username for the webhook message."""

    avatar_url: Optional[str] = None
    """URL for the avatar to be shown with the webhook message."""

    allowed_mentions: Dict[str, List[Union[str, int]]] = Field(default_factory=lambda: {"parse": []})
    """Control which mentions are allowed by the webhook (see Discord docs).

    Defaults to no parsing for safety (no @everyone/@here or role/user parsing).
    """

    @validator("allowed_mentions", pre=True, always=True)
    def validate_allowed_mentions(cls, v):
        # Ensure structure is at least a dict with a 'parse' list
        if v is None:
            return {"parse": []}
        if not isinstance(v, dict):
            raise ValueError("allowed_mentions must be a dict")
        v.setdefault("parse", [])
        return v


class ForwarderConfiguration(BaseModel):
    file: Optional[FileForwarderConfiguration] = None
    webhooks: Optional[List[WebhookForwarderConfiguration]] = []
    discord: Optional[List[DiscordForwarderConfiguration]] = []


class CollectorConfiguration(BaseModel):
    suricata: Optional[SuricataEveConfiguration] = None
    nf_stream: Optional[NFStreamConfiguration] = None


class HistoryConfiguration(BaseModel):
    """Configuration for history limiting in the database."""

    max_records: Optional[int] = Field(default=None, ge=1)
    """Maximum number of records to keep in each table."""

    max_duration_days: int = Field(default=2 * 7, ge=1)
    """Maximum duration to keep records in days."""

    enable: bool = Field(default=True)
    """Enable history limiting. Defaults to True."""


class CacheSeverityConfiguration(BaseModel):
    """Configuration for the severity cache used for Suricata alerts."""

    enable: bool = Field(default=True)
    """Enable caching of severity values. Defaults to True."""

    max_size: int = Field(default=1024, ge=1)
    """Maximum number of entries to retain in the severity cache."""

    ttl_seconds: Optional[float] = Field(default=None, gt=0)
    """Optional TTL in seconds for severity entries. If omitted, entries do not expire by time."""


class CacheConfiguration(BaseModel):
    severity: Optional[CacheSeverityConfiguration] = Field(default_factory=CacheSeverityConfiguration)
    """Top-level cache configuration. Currently only severity cache is supported."""


class Configuration(BaseModel):
    """Configuration for the Mongoose application."""

    collector: CollectorConfiguration
    enrichment: EnrichmentConfiguration
    forwarder: ForwarderConfiguration
    database_path: Path = Path("mongoose.db")
    history: Optional[HistoryConfiguration] = Field(default_factory=HistoryConfiguration)
    extra_configuration_dir: Path = Path("/var/lib/mongoose/")
    cache: Optional[CacheConfiguration] = Field(default_factory=CacheConfiguration)
