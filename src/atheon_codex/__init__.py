import uuid
from typing import Any

from .async_client import AsyncAtheonCodexClient
from .client import AtheonCodexClient
from .decorators import agent, tool
from .interactions import Interaction
from .models import AgentRecord, AtheonTrackPayload, ToolRecord

__version__ = "1.0.0"
__all__ = [
    "__version__",
    # Decorators
    "tool",
    "agent",
    "set_result",
    # Module-level sync API
    "init",
    "track",
    "begin",
    "flush",
    "shutdown",
    # Module-level async API
    "async_init",
    "async_track",
    "async_begin",
    "async_flush",
    "async_shutdown",
    # Clients
    "AtheonCodexClient",
    "AsyncAtheonCodexClient",
    # Models
    "AtheonTrackPayload",
    "ToolRecord",
    "AgentRecord",
    "Interaction",
]

_client: AtheonCodexClient | None = None
_async_client: AsyncAtheonCodexClient | None = None


def init(
    api_key: str,
    *,
    base_url: str = "https://api.atheon.ad/v1",
    upload_size: int = 10,
    upload_interval: float = 1.0,
    max_queue_size: int = 10_000,
) -> AtheonCodexClient:
    """Initialize the global synchronous Atheon client. Call once at startup.

    The API key is project-scoped. All interactions are automatically attributed
    to your project without extra configuration.

    Args:
        api_key (str): Your Atheon project API key.
        base_url (str, optional): Overrides the default Gateway endpoint. Defaults to "https://api.atheon.ad/v1".
        upload_size (int, optional): Events per HTTP batch. Defaults to 10.
        upload_interval (float, optional): Seconds between background flushes. Defaults to 1.0.
        max_queue_size (int, optional): Max in-memory queue depth. Defaults to 10,000.

    Returns:
        AtheonCodexClient: The initialized client instance.

    Raises:
        RuntimeError: If the async client is already initialized.
    """
    global _client, _async_client

    if _client is not None:
        # TODO: Change this to logging
        print("[Atheon] init() called multiple times. Returning existing sync client.")
        return _client

    if _async_client is not None:
        raise RuntimeError(
            "[Atheon] Cannot initialise the sync client because the async client is already active. Use either atheon.init() or atheon.async_init(), but not both."
        )

    _client = AtheonCodexClient(
        api_key=api_key,
        base_url=base_url,
        upload_size=upload_size,
        upload_interval=upload_interval,
        max_queue_size=max_queue_size,
    )

    return _client


def _get_client() -> AtheonCodexClient:
    if _client is None:
        raise RuntimeError(
            "Atheon has not been initialised. Call atheon.init(api_key) before using track() or begin()."
        )
    return _client


def track(
    provider: str,
    model_name: str,
    input: str | None = None,
    output: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    finish_reason: str | None = None,
    latency_ms: float | None = None,
    tools_used: list[dict[str, Any]] | None = None,
    conversation_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Track a complete single-turn interaction (fire-and-forget).

    Use `begin()` and `finish()` instead when you need streaming, `@atheon.tool`
    tracking, or mid-flight property updates.

    Args:
        provider (str): LLM provider (e.g., "openai", "anthropic").
        model_name (str): Specific model (e.g., "gpt-4o").
        input (str | None, optional): User query. Either input or output must be provided.
        output (str | None, optional): LLM response. Either input or output must be provided.
        tokens_input (int | None, optional): Prompt token count.
        tokens_output (int | None, optional): Completion token count.
        finish_reason (str | None, optional): LLM stop reason (e.g., "stop", "length").
        latency_ms (float | None, optional): End-to-end latency in milliseconds.
        tools_used (list[dict[str, Any]] | None, optional): Tool records. Usually auto-populated.
        conversation_id (str | None, optional): Conversation ID for multi-turn grouping.
        properties (dict[str, Any] | None, optional): Arbitrary metadata (e.g., {"agent": "support-bot"}).

    Returns:
        uuid.UUID: The assigned interaction ID.
    """
    return _get_client().track(
        provider=provider,
        model_name=model_name,
        input=input,
        output=output,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
        tools_used=tools_used,
        conversation_id=conversation_id,
        properties=properties,
    )


def begin(
    provider: str,
    model_name: str,
    input: str | None = None,
    conversation_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> Interaction:
    """Begin a streaming or multi-turn interaction.

    Starts a wall-clock timer and registers the interaction as the active context
    so `@atheon.tool` decorators hook in automatically. No HTTP call is made until `finish()`.

    Args:
        provider (str): LLM provider (e.g., "openai").
        model_name (str): Specific model (e.g., "gpt-4o").
        input (str | None, optional): The user's query.
        conversation_id (str | None, optional): Conversation ID for multi-turn grouping.
        properties (dict[str, Any] | None, optional): Initial metadata.

    Returns:
        Interaction: The active interaction context. Call `.finish()` when done.

    Example:
        ```python
        interaction = atheon.begin(provider="openai", model_name="gpt-4o", input="Summarize Q3")
        result = search("Q3 revenue") # @atheon.tool hooks silently
        interaction.finish(output=result, tokens_input=80, tokens_output=220, finish_reason="stop")
        ```
    """
    return _get_client().begin(
        provider=provider,
        model_name=model_name,
        input=input,
        conversation_id=conversation_id,
        properties=properties,
    )


def flush() -> None:
    _get_client().flush()


def shutdown() -> None:
    if _client is not None:
        _client.shutdown()


def set_result(
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    finish_reason: str | None = None,
) -> None:
    """Set LLM telemetry on the currently active child-agent.

    Call this inside any function decorated with `@atheon.agent` to capture token
    counts and finish reasons. For root interactions, pass these directly to `interaction.finish()`.

    Args:
        tokens_input (int | None, optional): Prompt token count.
        tokens_output (int | None, optional): Completion token count.
        finish_reason (str | None, optional): LLM stop reason (e.g., "stop").
    """
    from .interactions import current_interaction_var

    active = current_interaction_var.get()

    if active is None or not active.is_child_interaction:
        # TODO: Change this to logging
        print(
            "[Atheon] set_result() called outside of a child interaction. Ignoring. "
            "Use this only inside functions decorated with @atheon.agent. For root interactions, pass metrics directly to interaction.finish()."
        )
        return

    if tokens_input is not None:
        active._tokens_input = tokens_input
    if tokens_output is not None:
        active._tokens_output = tokens_output
    if finish_reason is not None:
        active._finish_reason = finish_reason


def async_init(
    api_key: str,
    *,
    base_url: str = "https://api.atheon.ad/v1",
    upload_size: int = 10,
    upload_interval: float = 1.0,
    max_queue_size: int = 10_000,
) -> AsyncAtheonCodexClient:
    """Initialize the global asynchronous Atheon client. Call once at startup.

    The API key is project-scoped. All interactions are automatically attributed
    to your project without extra configuration.

    Args:
        api_key (str): Your Atheon project API key.
        base_url (str, optional): Overrides the default Gateway endpoint. Defaults to "https://api.atheon.ad/v1".
        upload_size (int, optional): Events per HTTP batch. Defaults to 10.
        upload_interval (float, optional): Seconds between background flushes. Defaults to 1.0.
        max_queue_size (int, optional): Max in-memory queue depth. Defaults to 10,000.

    Returns:
        AsyncAtheonCodexClient: The initialized async client instance.

    Raises:
        RuntimeError: If the async client is already initialized.
    """
    global _async_client, _client

    if _async_client is not None:
        # TODO: Change this to logging
        print(
            "[Atheon] async_init() called multiple times. Returning existing async client."
        )
        return _client

    if _client is not None:
        raise RuntimeError(
            "[Atheon] Cannot initialise the async client because the sync client is already active. Use either atheon.init() or atheon.async_init(), but not both."
        )

    _async_client = AsyncAtheonCodexClient(
        api_key=api_key,
        base_url=base_url,
        upload_size=upload_size,
        upload_interval=upload_interval,
        max_queue_size=max_queue_size,
    )

    return _async_client


def _get_async_client() -> AsyncAtheonCodexClient:
    if _async_client is None:
        raise RuntimeError(
            "Atheon async client has not been initialised. Call atheon.async_init(api_key) before using async_track() or async_begin()."
        )
    return _async_client


def async_track(
    provider: str,
    model_name: str,
    input: str | None = None,
    output: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    finish_reason: str | None = None,
    latency_ms: float | None = None,
    tools_used: list[dict[str, Any]] | None = None,
    conversation_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Track a complete single-turn interaction (fire-and-forget).

    Use `async_begin()` and `finish()` instead when you need streaming, `@atheon.tool`
    tracking, or mid-flight property updates.

    Args:
        provider (str): LLM provider (e.g., "openai", "anthropic").
        model_name (str): Specific model (e.g., "gpt-4o").
        input (str | None, optional): User query. Either input or output must be provided.
        output (str | None, optional): LLM response. Either input or output must be provided.
        tokens_input (int | None, optional): Prompt token count.
        tokens_output (int | None, optional): Completion token count.
        finish_reason (str | None, optional): LLM stop reason (e.g., "stop", "length").
        latency_ms (float | None, optional): End-to-end latency in milliseconds.
        tools_used (list[dict[str, Any]] | None, optional): Tool records. Usually auto-populated.
        conversation_id (str | None, optional): Conversation ID for multi-turn grouping.
        properties (dict[str, Any] | None, optional): Arbitrary metadata (e.g., {"agent": "support-bot"}).

    Returns:
        uuid.UUID: The assigned interaction ID.
    """
    return _get_async_client().track(
        provider=provider,
        model_name=model_name,
        input=input,
        output=output,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
        tools_used=tools_used,
        conversation_id=conversation_id,
        properties=properties,
    )


def async_begin(
    provider: str,
    model_name: str,
    input: str | None = None,
    conversation_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> Interaction:
    """Begin a streaming or multi-turn interaction.

    Starts a wall-clock timer and registers the interaction as the active context
    so `@atheon.tool` decorators hook in automatically. No HTTP call is made until `finish()`.

    Args:
        provider (str): LLM provider (e.g., "openai").
        model_name (str): Specific model (e.g., "gpt-4o").
        input (str | None, optional): The user's query.
        conversation_id (str | None, optional): Conversation ID for multi-turn grouping.
        properties (dict[str, Any] | None, optional): Initial metadata.

    Returns:
        Interaction: The active interaction context. Call `.finish()` when done.

    Example:
        ```python
        interaction = atheon.async_begin(provider="openai", model_name="gpt-4o", input="Summarize Q3")
        result = search("Q3 revenue") # @atheon.tool hooks silently
        interaction.finish(output=result, tokens_input=80, tokens_output=220, finish_reason="stop")
        ```
    """
    return _get_async_client().begin(
        provider=provider,
        model_name=model_name,
        input=input,
        conversation_id=conversation_id,
        properties=properties,
    )


async def async_flush() -> None:
    await _get_async_client().flush()


async def async_shutdown() -> None:
    if _async_client is not None:
        await _async_client.shutdown()
