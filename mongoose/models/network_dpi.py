import time
from base64 import b64encode
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, Field

from mongoose.models.base import Base


class NetworkDPI(BaseModel):
    class Config:
        from_attributes = True

    id: str = Field(default_factory=lambda: uuid4().hex, frozen=True)
    time: datetime = Field(default_factory=datetime.now)
    timestamp: float = Field(default_factory=lambda: int(time.time()))
    community_id: str = ""
    risk: int = 0  # 0: normal, 1: suspicious, 2: critical
    bidirectional_duration_ms: int = 0
    bidirectional_bytes: int = 0
    bidirectional_packets: int = 0
    protocol: str = "unknown"
    protocol_number: int = 0
    ip_version: int
    src_ip: str
    src_mac: str
    src_port: int
    dst_ip: str
    dst_mac: str
    dst_port: int
    dst2src_bytes: int
    src2dst_bytes: int
    application_name: str = "unknown"
    application_category_name: str = "unknown"
    requested_server_name: str = "unknown"
    client_fingerprint: str = "unknown"
    server_fingerprint: str = "unknown"
    enrichment: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)

    @property
    def community_id_b64(self) -> str:
        return b64encode(bytes(self.community_id, "utf-8")).decode("utf-8")


class NetworkDPITable(Base):
    __tablename__ = "network_dpi"

    id = sa.Column(sa.String, primary_key=True)
    time = sa.Column(sa.DateTime)
    timestamp = sa.Column(sa.Float)
    community_id = sa.Column(sa.String, index=True)
    community_id_b64 = sa.Column(sa.String)
    risk = sa.Column(sa.Integer)
    bidirectional_duration_ms = sa.Column(sa.Integer)
    bidirectional_bytes = sa.Column(sa.Integer)
    bidirectional_packets = sa.Column(sa.Integer)
    protocol = sa.Column(sa.String)
    protocol_number = sa.Column(sa.Integer)
    ip_version = sa.Column(sa.Integer)
    src_ip = sa.Column(sa.String, index=True)
    src_mac = sa.Column(sa.String)
    src_port = sa.Column(sa.Integer)
    dst_ip = sa.Column(sa.String, index=True)
    dst_mac = sa.Column(sa.String)
    dst_port = sa.Column(sa.Integer)
    dst2src_bytes = sa.Column(sa.Integer)
    src2dst_bytes = sa.Column(sa.Integer)
    application_name = sa.Column(sa.String)
    application_category_name = sa.Column(sa.String)
    requested_server_name = sa.Column(sa.String)
    client_fingerprint = sa.Column(sa.String)
    server_fingerprint = sa.Column(sa.String)
    enrichment = sa.Column(sa.JSON)
    extra = sa.Column(sa.JSON)
