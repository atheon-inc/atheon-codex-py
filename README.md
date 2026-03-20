# Codex: Python SDK for Atheon
 
The Atheon Codex Python library provides convenient access to the Atheon Gateway from any Python 3.11+ application. It includes type definitions for all request params and response fields, and offers both synchronous and asynchronous clients powered by [httpx](https://github.com/encode/httpx).
 
## Installation
 
```sh
pip install atheon-codex
```
 
## Quick Start
 
```python
import os
import atheon
 
# Initialise once at application startup
atheon.init(os.environ["ATHEON_API_KEY"])
 
# Track a completed interaction — non-blocking, enqueues in the background
interaction_id = atheon.track(
    provider="openai",
    model_name="gpt-4o",
    input="How can I write blogs for my website?",
    output="Start by identifying your target audience...",
    tokens_input=18,
    tokens_output=120,
    finish_reason="stop",
)
 
# Pass interaction_id to your frontend: <atheon-container interaction-id="...">
print(interaction_id)
 
# Flush and stop the background queue before process exit
atheon.shutdown()
```
 
> **Note:** Get your API key from the [Atheon Gateway Dashboard](https://gateway.atheon.ad) under Project Settings. We recommend storing it in a `.env` file using [python-dotenv](https://pypi.org/project/python-dotenv/) rather than hardcoding it in source.
 
---
 
## Usage
 
### Initialisation
 
Call `atheon.init()` **once** at application startup. All subsequent calls share the global client automatically.
 
```python
atheon.init(
    api_key=os.environ["ATHEON_API_KEY"],
    upload_size=10,        # events per HTTP batch (default 10)
    upload_interval=1.0,   # seconds between background flushes (default 1.0)
    max_queue_size=10_000, # max in-memory queue depth (default 10 000)
)
```
 
### Streaming & Multi-Turn: `begin()` / `finish()`
 
Use `begin()` / `finish()` when the response spans time. Wall-clock latency is measured automatically.
 
```python
interaction = atheon.begin(
    provider="anthropic",
    model_name="claude-sonnet-4-5",
    input="Summarise our Q3 report",
    properties={"agent": "rag-pipeline", "environment": "production"},
)
 
# ... stream response, call tools, run sub-agents ...
 
interaction.set_property("user_tier", "pro")  # enrich mid-flight
 
interaction_id = interaction.finish(
    output=final_text,
    tokens_input=80,
    tokens_output=220,
    finish_reason="stop",
)
```
 
### Tool Tracking: `@atheon.tool`
 
Decorate any function (sync or async) to record its name, latency, and errors into the active interaction automatically — no explicit passing required.
 
```python
@atheon.tool("vector-search")
def search(query: str) -> list[str]:
    return db.search(query)
 
@atheon.tool("reranker")
async def rerank(docs: list[str]) -> list[str]:
    return await model.rerank(docs)
```
 
> `@atheon.tool` is a no-op if called outside an active `begin()` context — safe to use unconditionally.
 
### Sub-Agent Tracking: `@atheon.agent`
 
Decorate LLM-backed sub-agent functions to nest their tool calls and token usage inside the root interaction. Everything ships in a single payload on `finish()`.
 
```python
@atheon.agent(
    "rag-pipeline",
    provider="anthropic",
    model_name="claude-haiku-4-5",
)
def rag_agent(query: str) -> str:
    chunks = search(query)
    response = llm.messages.create(...)
    atheon.set_result(
        tokens_input=response.usage.input_tokens,
        tokens_output=response.usage.output_tokens,
        finish_reason=response.stop_reason,
    )
    return response.content[0].text
```
 
### Async Support
 
For async frameworks (FastAPI, Django async views, etc.), use the async API. `async_track()` and `async_begin()` are synchronous enqueues — call without `await`.
 
```python
# FastAPI example
from contextlib import asynccontextmanager
from fastapi import FastAPI
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    atheon.async_init(os.environ["ATHEON_API_KEY"])
    yield
    await atheon.async_shutdown()
 
app = FastAPI(lifespan=lifespan)
 
@app.post("/chat")
async def chat(req: ChatRequest):
    final_text = await llm.complete(req.message)
    interaction_id = atheon.async_track(   # no await
        provider="openai",
        model_name="gpt-4o",
        input=req.message,
        output=final_text,
        finish_reason="stop",
    )
    return {"reply": final_text, "interaction_id": str(interaction_id)}
```
 
> Use either `atheon.init()` or `atheon.async_init()` — not both in the same process.
 
### Direct Client Instantiation
 
The module-level helpers are recommended for most applications. For multiple isolated clients in the same process, instantiate directly:
 
```python
from atheon import AtheonCodexClient, AsyncAtheonCodexClient
 
# Sync
with AtheonCodexClient(api_key=os.environ["ATHEON_API_KEY"]) as client:
    client.track(provider="openai", model_name="gpt-4o", input="...", output="...")
 
# Async
async with AsyncAtheonCodexClient(api_key=os.environ["ATHEON_API_KEY"]) as client:
    client.track(provider="openai", model_name="gpt-4o", input="...", output="...")
```
 
---

 
## Links
 
- [Atheon Documentation](https://docs.atheon.ad)
- [Gateway Dashboard](https://gateway.atheon.ad)
- [PyPI](https://pypi.org/project/atheon-codex/)
 
