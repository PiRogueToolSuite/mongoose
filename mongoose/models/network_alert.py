import time
from base64 import b64encode
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, Field, validator

from mongoose.models.base import Base


class NetworkAlert(BaseModel):
    class Config:
        from_attributes = True

    id: str = Field(default_factory=lambda: uuid4().hex, frozen=True)
    time: datetime = Field(default_factory=datetime.now)
    timestamp: float = Field(default_factory=lambda: int(time.time()))
    community_id: str = ""
    flow_id: int
    src_ip: str
    src_port: int
    dst_ip: str = Field(validation_alias="dest_ip")
    dst_port: int = Field(validation_alias="dest_port")
    protocol: str = Field(validation_alias="proto")
    app_proto: str = ""
    rule: str = ""
    action: str
    gid: int
    signature_id: int
    rev: int
    signature: str
    category: str
    severity: int
    enrichment: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)

    @property
    def community_id_b64(self) -> str:
        return b64encode(bytes(self.community_id, "utf-8")).decode("utf-8")

    @validator("timestamp", pre=True)
    def timestamp_validator(cls, v):
        return datetime.fromisoformat(v).timestamp()

    @validator("app_proto", pre=True)
    def app_proto_validator(cls, v):
        if v and v != "failed":
            return v.upper()
        return v


class NetworkAlertTable(Base):
    __tablename__ = "network_alert"

    id = sa.Column(sa.String, primary_key=True)
    time = sa.Column(sa.DateTime)
    timestamp = sa.Column(sa.Float)
    community_id = sa.Column(sa.String, index=True)
    community_id_b64 = sa.Column(sa.String)
    flow_id = sa.Column(sa.Integer)
    src_ip = sa.Column(sa.String, index=True)
    src_port = sa.Column(sa.Integer)
    dst_ip = sa.Column(sa.String, index=True)
    dst_port = sa.Column(sa.Integer)
    protocol = sa.Column(sa.String)
    app_proto = sa.Column(sa.String)
    rule = sa.Column(sa.String)
    action = sa.Column(sa.String)
    gid = sa.Column(sa.Integer)
    signature_id = sa.Column(sa.Integer)
    rev = sa.Column(sa.Integer)
    signature = sa.Column(sa.String)
    category = sa.Column(sa.String)
    severity = sa.Column(sa.Integer)
    enrichment = sa.Column(sa.JSON)
    extra = sa.Column(sa.JSON)
