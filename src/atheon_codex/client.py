import uuid
from decimal import Decimal
from typing import Any

import httpx

from ._internals import _handle_response
from ._queue import _EventQueue
from ._utils import Err
from .interactions import Interaction
from .models import AtheonTrackPayload


class AtheonCodexClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.atheon.ad/v1",
        headers: dict[str, str] | None = None,
        upload_size: int = 10,
        upload_interval: float = 1.0,
        max_queue_size: int = 10_000,
        request_timeout: float = 45.0,
        **kwargs,
    ):
        if headers is None:
            headers = {}

        self.base_url = base_url

        self._http_client = httpx.Client(
            base_url=self.base_url,
            headers={
                "x-atheon-api-key": api_key,
                "Content-Type": "application/json",
                **headers,
            },
            timeout=httpx.Timeout(timeout=request_timeout),
            **kwargs,
        )

        self._queue = _EventQueue(
            send_fn=self._send_batch,
            upload_size=upload_size,
            upload_interval=upload_interval,
            max_queue_size=max_queue_size,
        )

    def __enter__(self) -> "AtheonCodexClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()

    def flush(self) -> None:
        self._queue.flush()

    def shutdown(self) -> None:
        self._queue.shutdown()
        self._http_client.close()

    def track(
        self,
        provider: str,
        model_name: str,
        input: str | None = None,
        output: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        finish_reason: str | None = None,
        latency_ms: float | None = None,
        tools_used: list[dict[str, Any]] | None = None,
        conversation_id: uuid.UUID | None = None,
        properties: dict[str, Any] | None = None,
    ) -> uuid.UUID:
        payload = AtheonTrackPayload(
            provider=provider,
            model_name=model_name,
            input=input,
            output=output,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            finish_reason=finish_reason,
            latency_ms=Decimal(f"{latency_ms:.2f}")
            if latency_ms is not None
            else latency_ms,
            tools_used=tools_used or [],
            conversation_id=conversation_id,
            properties=properties or {},
        )

        self._queue.enqueue(payload.model_dump(mode="json", exclude_none=True))

        return payload.interaction_id

    def begin(
        self,
        provider: str,
        model_name: str,
        input: str | None = None,
        conversation_id: uuid.UUID | None = None,
        properties: dict[str, Any] | None = None,
    ) -> Interaction:
        return Interaction(
            provider=provider,
            model_name=model_name,
            input=input,
            conversation_id=conversation_id,
            properties=properties,
            queue=self._queue,
        )

    def _send_batch(self, batch: list[dict]) -> None:
        response = self._http_client.post("/track-ai-events/", json={"events": batch})
        result = _handle_response(response)

        if isinstance(result, Err):
            raise result.error
