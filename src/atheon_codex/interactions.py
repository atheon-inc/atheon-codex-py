from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar, Token
from decimal import Decimal
from typing import Any, Self

from ._queue import _EventQueue
from ._utils import _generate_hash
from .models import AgentRecord, AtheonTrackPayload, ToolRecord

logger = logging.getLogger(__name__)

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
    def id(self) -> uuid.UUID:
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
        sign_fn: Callable,
    ) -> None:
        super().__init__(provider, model_name, properties)
        self.input = input
        self.conversation_id = conversation_id

        self._sign_fn = sign_fn

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
    ) -> tuple[uuid.UUID, str, str | None]:
        """Complete the root interaction and enqueue the full payload.

        Calculates total latency and aggregates all tool/agent records.

        Args:
            output (str | None, optional): Final LLM response text.
            tokens_input (int | None, optional): Prompt token count.
            tokens_output (int | None, optional): Completion token count.
            finish_reason (str | None, optional): LLM stop reason.

        Returns:
            uuid.UUID: The interaction ID assigned to this event.
            str: SHA-256 hash of the prompt for this event's input.
            str | None: A cryptographic fingerprint for frontend event validation, if the backend handshake succeeded; otherwise None.
        """
        if self._finished:
            logger.warning(
                "finish() called more than once on interaction %s.", self.interaction_id
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
            prompt_hash=_generate_hash(self.input),
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            finish_reason=finish_reason,
            latency_ms=Decimal(f"{latency_ms:.2f}"),
            tools_used=self.tools_used,
            conversation_id=self.conversation_id,
            properties=self.properties,
        )

        self._queue.enqueue(payload.model_dump(mode="json"))

        return (
            payload.interaction_id,
            payload.prompt_hash,
            self._sign_fn(payload.interaction_id) if self._sign_fn else None,
        )


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
