from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, SecretStr, validator


class WebhookConfiguration(BaseModel):
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

    Attributes:
        url: The destination URL for the webhook (must be a valid HTTP/HTTPS URL).
        headers: Optional dictionary of additional HTTP headers to include in requests.
        auth_type: Type of authentication ('none', 'basic', 'bearer', 'header').
        auth_token: Credentials (API key, token, or 'user:pass' for basic auth).
        auth_header_name: Name of the header if auth_type is 'header' (default: X-API-Key).
        verify_ssl: Whether to verify SSL certificates. Defaults to True.
        retry_count: Number of retries for failed requests. Defaults to 3.
        retry_delay: Delay between retries in seconds. Defaults to 5.0.
        timeout: Request timeout in seconds. Defaults to 10.0.
        topics: List of topics to forward. Defaults to ["network-dpi", "network-alert"].
    """
    url: Union[HttpUrl, str]
    headers: Dict[str, str] = Field(default_factory=dict)
    auth_type: str = "none"  # none, basic, bearer, header
    auth_token: Optional[SecretStr] = None
    auth_header_name: str = "X-API-Key"
    verify_ssl: bool = True
    retry_count: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=5.0, ge=0)
    timeout: float = Field(default=10.0, gt=0)
    topics: List[str] = Field(default_factory=lambda: ["network-dpi", "network-alert"])

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

    Attributes:
        output_dir: The directory where the files will be created.
        topics: List of topics to forward (e.g., ["network-dpi", "network-alert"]).
        prefix: Optional prefix for the filenames (e.g., "mongoose-").
    """
    output_dir: str = "output"
    topics: List[str] = Field(default_factory=lambda: ["network-dpi", "network-alert", "network-flow"])
    prefix: str = ""


class NFStreamConfiguration(BaseModel):
    active_timeout: int = 2 * 60
    interface: str
    max_nflows: int = 0


class SuricataEveConfiguration(BaseModel):
    socket_path: str = "/run/suricata.socket"
