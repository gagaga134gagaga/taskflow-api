from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    operation: Literal["word_count", "checksum"]
    text: str = Field(min_length=1, max_length=100_000)


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    attempts: int
    result: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    message: str
    created_at: datetime
