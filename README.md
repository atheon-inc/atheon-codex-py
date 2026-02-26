# Codex: Python SDK for Atheon

The Atheon Codex Python library provides convenient access to the Atheon Gateway Services from any Python 3.11+ applications. The library includes type definitions for all request params and response fields, and offers both synchronous and asynchronous clients powered by [httpx](https://github.com/encode/httpx).

## Installation

```sh
# install from PyPI
pip install atheon-codex
```

## Usage

```python
import os
from atheon_codex import AtheonCodexClient, AtheonUnitCreateModel

client = AtheonCodexClient(
    api_key=os.environ.get("ATHEON_CODEX_API_KEY"),
)

create_payload = AtheonUnitCreateModel(
    query="How can I write blogs for my website?",
    base_content="insert the llm response generated from your application as the base content",
)
result = client.create_atheon_unit(create_payload)

print(result)
```

> **Note:** _You can get your Codex API Key through [Atheon Gateway Dashboard](https://gateway.atheon.ad) under project settings._


While you can provide an `api_key` keyword argument, we recommend using [python-dotenv](https://pypi.org/project/python-dotenv/) (or something similar) to add `ATHEON_CODEX_API_KEY="My Eon API Key"` to your `.env` file so that your API Key is not stored in source control.
