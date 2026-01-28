from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, SecretStr, validator


class WebhookForwarderConfiguration(BaseModel):
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

    verify_ssl: bool = True
    """Whether to verify SSL certificates. Defaults to True."""

    retry_count: int = Field(default=3, ge=0)
    """Number of retries for failed requests. Defaults to 3."""

    retry_delay: float = Field(default=5.0, ge=0)
    """Delay between retries in seconds. Defaults to 5.0."""

    timeout: float = Field(default=10.0, gt=0)
    """Request timeout in seconds. Defaults to 10.0."""

    topics: List[str] = Field(default_factory=lambda: ["network-dpi", "network-alert"])
    """List of topics to forward. Defaults to ["network-dpi", "network-alert"]."""

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


class FileForwarderConfiguration(BaseModel):
    """Configuration for the File Forwarder.

    This class defines the output directory and topics for dumping network
    events into files. Each topic will have its own file in the specified
    directory.
    """

    output_dir: str = "output"
    """The directory where the files will be created."""
    topics: List[str] = Field(default_factory=lambda: ["network-dpi", "network-alert", "network-flow"])
    """List of topics to forward (e.g., ["network-dpi", "network-alert"])."""
    prefix: str = ""
    """Optional prefix for the filenames (e.g., "mongoose-")."""


class NFStreamConfiguration(BaseModel):
    active_timeout: int = 2 * 60
    interface: str
    max_nflows: int = 0


class SuricataEveConfiguration(BaseModel):
    socket_path: str = "/run/suricata.socket"
