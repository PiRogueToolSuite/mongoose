import time
from base64 import b64encode
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, Field, validator

from mongoose.models.base import Base


class NetworkFlow(BaseModel):
    class Config:
        from_attributes = True

    id: str = Field(default_factory=lambda: uuid4().hex, frozen=True)
    time: datetime = Field(default_factory=datetime.now)
    timestamp: float = Field(default_factory=lambda: int(time.time()))
    community_id: str = ""
    risk: int = 0  # 0: normal, 1: suspicious, 2: critical
    flow_id: int
    src_ip: str
    dst_ip: str = Field(validation_alias="dest_ip")
    protocol: str = Field(validation_alias="proto")
    app_proto: str = ""
    packets: int = Field(validation_alias="pkts")
    bytes: int
    start: datetime
    end: datetime
    age: int
    enrichment: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)

    @property
    def community_id_b64(self) -> str:
        return b64encode(bytes(self.community_id, "utf-8")).decode("utf-8")

    @validator("timestamp", pre=True)
    def timestamp_validator(cls, v):
        return datetime.fromisoformat(v).timestamp()

    @validator("start", pre=True)
    def start_validator(cls, v):
        return datetime.fromisoformat(v).timestamp()

    @validator("end", pre=True)
    def end_validator(cls, v):
        return datetime.fromisoformat(v).timestamp()

    @validator("app_proto", pre=True)
    def app_proto_validator(cls, v):
        if v and v != "failed":
            return v.upper()
        return v


class NetworkFlowTable(Base):
    __tablename__ = "network_flow"

    id = sa.Column(sa.String, primary_key=True)
    time = sa.Column(sa.DateTime)
    timestamp = sa.Column(sa.Float)
    community_id = sa.Column(sa.String, index=True)
    community_id_b64 = sa.Column(sa.String)
    risk = sa.Column(sa.Integer)
    flow_id = sa.Column(sa.Integer)
    src_ip = sa.Column(sa.String, index=True)
    dst_ip = sa.Column(sa.String, index=True)
    protocol = sa.Column(sa.String)
    app_proto = sa.Column(sa.String)
    packets = sa.Column(sa.Integer)
    bytes = sa.Column(sa.Integer)
    start = sa.Column(sa.DateTime)
    end = sa.Column(sa.DateTime)
    age = sa.Column(sa.Integer)
    enrichment = sa.Column(sa.JSON)
    extra = sa.Column(sa.JSON)
