from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class ToolRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[uuid.UUID, Field(default_factory=uuid.uuid4)]
    type: Annotated[Literal["tool"], Field(default="tool")]
    name: str
    latency_ms: Decimal
    error: Annotated[str | None, Field(default=None)]


class AgentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[uuid.UUID, Field(default_factory=uuid.uuid4)]
    type: Annotated[Literal["agent"], Field(default="agent")]

    name: str
    provider: str
    model_name: str

    tokens_input: Annotated[int | None, Field(default=None)]
    tokens_output: Annotated[int | None, Field(default=None)]
    finish_reason: Annotated[str | None, Field(default=None, max_length=64)]
    status_code: Annotated[int | None, Field(default=None, ge=100, le=599)]
    latency_ms: Annotated[Decimal | None, Field(default=None)]

    tools_used: Annotated[list[ToolRecord | AgentRecord], Field(default_factory=list)]

    error: Annotated[str | None, Field(default=None)]
    properties: Annotated[dict[str, Any], Field(default_factory=dict)]


class AtheonTrackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_id: Annotated[uuid.UUID, Field(default_factory=uuid.uuid4)]
    created_at: datetime

    provider: str
    model_name: str

    input: Annotated[str | None, Field(default=None)]
    output: Annotated[str | None, Field(default=None)]
    prompt_hash: Annotated[str | None, Field(default=None)]

    tokens_input: Annotated[int | None, Field(default=None)]
    tokens_output: Annotated[int | None, Field(default=None)]
    finish_reason: Annotated[str | None, Field(default=None, max_length=64)]
    status_code: Annotated[int | None, Field(default=None, ge=100, le=599)]
    latency_ms: Annotated[Decimal | None, Field(default=None)]

    tools_used: Annotated[list[ToolRecord | AgentRecord], Field(default_factory=list)]

    conversation_id: Annotated[str | None, Field(default=None)]
    properties: Annotated[dict[str, Any], Field(default_factory=dict)]

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at(cls, value: Any, _info: Any) -> Any:
        if value is None:
            return datetime.now(UTC)
        if isinstance(value, datetime):
            return value.astimezone(UTC)

        return value

    @field_serializer("created_at")
    def serialize_created_at(self, created_at: datetime, _info: Any) -> str:
        return created_at.isoformat()

    @model_validator(mode="after")
    def check_input_or_output(self) -> Self:
        if not self.input and not self.output:
            raise ValueError('Either "input" or "output" must be provided.')
        return self
