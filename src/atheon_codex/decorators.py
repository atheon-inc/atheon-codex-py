import functools
import inspect
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from .interactions import ChildInteraction, current_interaction_var
from .models import ToolRecord


def tool(name: str) -> Callable:
    """Instrument a tool function for Atheon tracking.

    Automatically hooks into the nearest active `Interaction` or `ChildInteraction`
    via ContextVar. Functions normally (no-op) if called outside `atheon.begin()`.

    Args:
        name (str): The tool name. No Gateway registration required.

    Returns:
        Callable: The decorated sync or async function.

    Example:
        ```python
        @atheon.tool("vector-search")
        def search(query: str) -> list[str]:
            return db.search(query)
        ```
    """

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _run_tool_async(func, name, *args, **kwargs)

            return async_wrapper

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _run_tool_sync(func, name, *args, **kwargs)

            return sync_wrapper

    return decorator


def _run_tool_sync(func: Callable, name: str, *args: Any, **kwargs: Any) -> Any:
    active = current_interaction_var.get()
    start_time = time.perf_counter()
    error_msg: str | None = None

    try:
        result = func(*args, **kwargs)
        return result
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        if active is not None:
            active.add_tool_execution(
                ToolRecord(
                    name=name,
                    latency_ms=Decimal(f"{latency_ms:.2f}"),
                    error=error_msg,
                )
            )


async def _run_tool_async(func: Callable, name: str, *args: Any, **kwargs: Any) -> Any:
    active = current_interaction_var.get()
    start_time = time.perf_counter()
    error_msg: str | None = None

    try:
        result = await func(*args, **kwargs)
        return result
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        if active is not None:
            active.add_tool_execution(
                ToolRecord(
                    name=name,
                    latency_ms=Decimal(f"{latency_ms:.2f}"),
                    error=error_msg,
                )
            )


def agent(
    name: str,
    provider: str,
    model_name: str,
) -> Callable:
    """Instrument an LLM-backed sub-agent function for Atheon tracking.

    Creates a `ChildInteraction` context so nested `@atheon.tool` calls hook to
    this sub-agent instead of the root. On completion, it attaches its execution
    record to the parent interaction.

    Args:
        name (str): Sub-agent name. Must be registered in your Gateway dashboard.
        provider (str): LLM provider used by the sub-agent.
        model_name (str): Model used by the sub-agent.

    Returns:
        Callable: The decorated sync or async function.

    Example:
        ```python
        @atheon.agent("rag-pipeline", provider="anthropic", model_name="claude-haiku-4-5")
        def rag_agent(query: str) -> str:
            response = llm.messages.create(...)
            atheon.set_result(tokens_input=10, tokens_output=20, finish_reason="stop")
            return response.content[0].text
        ```
    """

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _run_agent_async(
                    func, name, provider, model_name, *args, **kwargs
                )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _run_agent_sync(
                    func, name, provider, model_name, *args, **kwargs
                )

            return sync_wrapper

    return decorator


def _run_agent_sync(
    func: Callable,
    name: str,
    provider: str,
    model_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    parent = current_interaction_var.get()
    if parent is None:
        print(
            "[Atheon] @atheon.agent('%s') called with no active root interaction — call atheon.begin() first. Child-agent will not be tracked.",
            name,
        )
        return func(*args, **kwargs)

    child_interaction = ChildInteraction(
        agent_name=name,
        parent=parent,
        provider=provider,
        model_name=model_name,
        properties=None,
    )

    error_msg: str | None = None

    with child_interaction:
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            child_interaction._finish(error=error_msg)


async def _run_agent_async(
    func: Callable,
    name: str,
    provider: str,
    model_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    parent = current_interaction_var.get()
    if parent is None:
        print(
            "[Atheon] @atheon.agent('%s') called with no active root interaction — call atheon.begin() first. Child-agent will not be tracked.",
            name,
        )
        return await func(*args, **kwargs)

    child_interaction = ChildInteraction(
        agent_name=name,
        parent=parent,
        provider=provider,
        model_name=model_name,
        properties=None,
    )

    error_msg: str | None = None

    with child_interaction:
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            child_interaction._finish(error=error_msg)
