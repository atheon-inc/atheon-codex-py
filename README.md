## Legacy Notice – February 2026

This snapshot (`legacy-archive-1`) preserves the original **Ads in LLM** codebase prior to our strategic refocus in February 2026.

### The Strategic Pivot

After a year in the market, we successfully validated our core technology and saw promising early traction. However, **we** realized that widespread user readiness for ad-integrated AI experiences is still evolving. During this period, we observed that our users were primarily utilizing **Atheon** as an analytics suite to understand AI traffic patterns.

To meet this immediate market demand, we have shifted our primary focus to **Analytics for AI Traffic**. This allows us to provide high-value tooling for developers today, while maintaining the underlying architecture to re-enable **the** ad-tech as the ecosystem matures.

### What This Means

* **Status:** This is a permanent, read-only snapshot of the codebase as of February 2026.
* **Purpose:** Preserved for historical reference, audit trails, and future retrieval of ad-serving logic.
* **Active Development:** All current work on the Atheon Analytics platform is located on the `main` branch.

*We are incredibly proud of the groundwork established here; it remains the technical foundation for everything we are building next.*

---

# Codex: Python SDK for Atheon

The Atheon Codex Python library provides convenient access to the Atheon Gateway Ad Service from any Python 3.10+ applications. The library includes type definitions for all request params and response fields, and offers both synchronous and asynchronous clients powered by [httpx](https://github.com/encode/httpx).

## Installation

```sh
# install from PyPI
pip install atheon-codex
```

## Usage

```python
import os
from atheon_codex import AtheonCodexClient, AtheonUnitFetchAndIntegrateModel

client = AtheonCodexClient(
    api_key=os.environ.get("ATHEON_CODEX_API_KEY"),
)

fetch_and_integrate_payload = AtheonUnitFetchAndIntegrateModel(
    query="How can I write blogs for my website?",
    base_content="insert the llm response generated from your application as the base content",
    # use_user_intent_as_filter=True,
)
result = client.fetch_and_integrate_atheon_unit(fetch_and_integrate_payload)

print(result)
```

>> **Note:** _You can enable monetization through [Atheon Gateway Dashboard](https://gateway.atheon.ad) under project settings._


While you can provide an `api_key` keyword argument, we recommend using [python-dotenv](https://pypi.org/project/python-dotenv/) (or something similar) to add `ATHEON_CODEX_API_KEY="My Eon API Key"` to your `.env` file so that your API Key is not stored in source control.
