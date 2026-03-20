from __future__ import annotations

import time
import uuid
from contextvars import ContextVar, Token
from decimal import Decimal
from typing import Any, Self

from ._queue import _EventQueue
from .models import AgentRecord, AtheonTrackPayload, ToolRecord

current_interaction_var: ContextVar[Interaction | ChildInteraction | None] = ContextVar(
    "current_interaction", default=None
)


class _BaseInteraction:
    def __init__(
        self, provider: str, model_name: str, properties: dict[str, Any] | None = None
    ) -> None:
        self.interaction_id = uuid.uuid4()
        self.provider = provider
        self.model_name = model_name

        self.properties: dict[str, Any] = properties.copy() if properties else {}

        self.tools_used: list[ToolRecord | AgentRecord] = []
        self._finished = False
        self._start_time = time.perf_counter()

        self._context_token: Token | None = None

    @property
    def id(self) -> str:
        return self.interaction_id

    def add_tool_execution(self, record: ToolRecord) -> None:
        self.tools_used.append(record)

    def add_agent_execution(self, record: AgentRecord) -> None:
        self.tools_used.append(record)

    def set_property(self, key: str, value: Any) -> None:
        self.properties[key] = value

    def _cleanup_context(self) -> None:
        if self._context_token is not None:
            current_interaction_var.reset(self._context_token)
            self._context_token = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._cleanup_context()


class Interaction(_BaseInteraction):
    """The root interaction representing the top-level LLM call.

    Acts as the main context manager. Nested `@atheon.tool` and `@atheon.agent`
    calls automatically attach their telemetry to this instance. A single payload
    containing the full execution trace is enqueued upon calling `finish()`.
    """

    def __init__(
        self,
        provider: str,
        model_name: str,
        input: str | None,
        conversation_id: uuid.UUID | None,
        properties: dict[str, Any] | None,
        queue: _EventQueue,
    ) -> None:
        super().__init__(provider, model_name, properties)
        self.input = input
        self.conversation_id = conversation_id

        self._queue = queue

        self._context_token = current_interaction_var.set(self)

    @property
    def is_child_interaction(self) -> bool:
        return False

    def finish(
        self,
        output: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        finish_reason: str | None = None,
    ) -> uuid.UUID:
        """Complete the root interaction and enqueue the full payload.

        Calculates total latency and aggregates all tool/agent records.

        Args:
            output (str | None, optional): Final LLM response text.
            tokens_input (int | None, optional): Prompt token count.
            tokens_output (int | None, optional): Completion token count.
            finish_reason (str | None, optional): LLM stop reason.

        Returns:
            uuid.UUID: The interaction ID assigned to this event.
        """
        if self._finished:
            # TODO: Change this to logging
            print(
                "[Atheon] finish() called more than once on interaction %s",
                self.interaction_id,
            )
            return self.interaction_id

        self._finished = True
        latency_ms = (time.perf_counter() - self._start_time) * 1000

        self._cleanup_context()

        payload = AtheonTrackPayload(
            interaction_id=self.interaction_id,
            provider=self.provider,
            model_name=self.model_name,
            input=self.input,
            output=output,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            finish_reason=finish_reason,
            latency_ms=Decimal(f"{latency_ms:.2f}"),
            tools_used=self.tools_used,
            conversation_id=self.conversation_id,
            properties=self.properties,
        )

        self._queue.enqueue(payload.model_dump(mode="json", exclude_none=True))

        return self.interaction_id


class ChildInteraction(_BaseInteraction):
    """A sub-agent interaction context. Created automatically by `@atheon.agent`.

    Temporarily becomes the active context for nested tools. When finished, it
    writes an `AgentRecord` to its parent's `tools_used` list.
    """

    def __init__(
        self,
        agent_name: str,
        parent: Interaction | ChildInteraction,
        provider: str,
        model_name: str,
        properties: dict[str, Any] | None,
    ) -> None:
        super().__init__(provider, model_name, properties)
        self.agent_name = agent_name
        self.parent = parent

        # Set by atheon.set_result() mid-function
        self._tokens_input: int | None = None
        self._tokens_output: int | None = None
        self._finish_reason: str | None = None

        self._context_token = current_interaction_var.set(self)

    @property
    def is_child_interaction(self) -> bool:
        return True

    def _finish(self, error: str | None = None) -> None:
        if self._finished:
            return

        self._finished = True
        latency_ms = (time.perf_counter() - self._start_time) * 1000

        self._cleanup_context()

        record = AgentRecord(
            name=self.agent_name,
            provider=self.provider,
            model_name=self.model_name,
            tokens_input=self._tokens_input,
            tokens_output=self._tokens_output,
            finish_reason=self._finish_reason,
            latency_ms=Decimal(f"{latency_ms:.2f}"),
            tools_used=self.tools_used,
            error=error,
            properties=self.properties,
        )

        self.parent.add_agent_execution(record)
