from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class CheckpointRecord(BaseModel):
    checkpoint_id: int = Field(alias="id")
    date_created: datetime = Field(alias="dateCreated")
    date_saved: datetime | None = Field(None, alias="dateSaved")
    status: str

    model_config = {"populate_by_name": True}

    @property
    def is_complete(self) -> bool:
        return self.date_saved is not None

    @property
    def runtime_hours(self) -> float | None:
        if self.date_saved is None:
            return None
        delta = self.date_saved - self.date_created
        return delta.total_seconds() / 3600


class StudioRecord(BaseModel):
    session_id: str = Field(alias="sessionId")
    name: str
    user_name: str = "unknown"
    cpu: int = 0
    compute_env_id: str = Field("", alias="computeEnv")
    status: str = ""
    date_created: datetime = Field(alias="dateCreated")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _flatten(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            data["user_name"] = (data.get("user") or {}).get("userName", "unknown") or "unknown"
            config = data.get("configuration") or {}
            data["cpu"] = config.get("cpu", 0)
            ce = data.get("computeEnv") or {}
            data["computeEnv"] = ce.get("id", "") if isinstance(ce, dict) else ""
            status_info = data.get("statusInfo") or {}
            data["status"] = status_info.get("status", "")
        return data

    @property
    def cpu_unresolved(self) -> bool:
        return self.cpu == 0
