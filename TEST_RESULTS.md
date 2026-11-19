# Verification results

Verified on Python 3.12.16 with LiteLLM 1.105.0 and MCP 1.30.0 (within the required v1 range).

- Syntax: all Python sources parse; compileall passed.
- Pytest: **21 passed**, including Streamlit approval-card cancellation, workflow policies and API/database integration.
- Real stack: **PASS**, all five MCP tools exercised over Streamable HTTP → FastAPI → temporary SQLite database; country/status filtering, validation, creation and duplicates verified.
- One upstream FastAPI/Starlette test-client deprecation warning was reported; no test failures remain.
- No live GPT request was made. Model extraction is schema validated in the application; natural-language accuracy must be checked with the configured OpenAI account before presenting.

See README for reproduction commands and local-demo scope.
