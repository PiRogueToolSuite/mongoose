import time
from base64 import b64encode
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, Field, ConfigDict, validator

from mongoose.models.base import Base


class NetworkFlow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    packets: int = Field(validation_alias="pkts")
    bytes: int
    start: datetime
    end: datetime
    age: int
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
    community_id = sa.Column(sa.String)
    community_id_b64 = sa.Column(sa.String)
    flow_id = sa.Column(sa.Integer)
    src_ip = sa.Column(sa.String)
    src_port = sa.Column(sa.Integer)
    dst_ip = sa.Column(sa.String)
    dst_port = sa.Column(sa.Integer)
    protocol = sa.Column(sa.String)
    app_proto = sa.Column(sa.String)
    packets = sa.Column(sa.Integer)
    bytes = sa.Column(sa.Integer)
    start = sa.Column(sa.DateTime)
    end = sa.Column(sa.DateTime)
    age = sa.Column(sa.Integer)
    extra = sa.Column(sa.JSON)
