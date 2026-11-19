# Supplier Agent v4

A local supplier onboarding demo with deterministic Python policy and workflow control.

**Architecture:** Streamlit → GPT through LiteLLM (structured language extraction only) → Python state machine / policy → MCP v1 FastMCP → FastAPI → SQLite.

## Quick start

Requires Python **3.12**. From the extracted project directory:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your own OPENAI_API_KEY.
python start.py
```

Open http://127.0.0.1:8501. Ctrl+C stops the child services. The launcher checks ports 8001, 8002 and 8501 and refuses to attach to an unrelated service. Service logs are in `logs/`. Missing keys and service startup failures are reported outside the chat UI. `.env` and databases are excluded from version control.

The example selects `openai/gpt-4.1-mini`; change LLM_MODEL to an OpenAI GPT model available to your account that supports strict JSON schema output. No key is bundled. The UI keeps working for deterministic Approve/Cancel/refusal controls when the model is unavailable; language requests receive a clean failure message and retain their draft. There is no second language model or silent heuristic onboarding fallback.

For individual services (run each from the project root after activating the environment):

```sh
python -m uvicorn app.api:app --host 127.0.0.1 --port 8001
python -m app.mcp_server
python -m streamlit run app/ui.py --server.address 127.0.0.1
```

API_URL and MCP_URL configure the inter-service connections. MCP_PORT optionally changes the standalone MCP listener. The bundled launcher uses the default ports; run individual components to customize ports. DATABASE_PATH is relative to the current directory unless absolute. Seed data is inserted idempotently on API startup; existing data is preserved.

## Try it

- `list all suppliers`, `show active suppliers in Uganda`
- `find Leny Enterprises`, `status KE001`
- `onboard Acme Technology in Kenya, tax ID ACME123`
- Or `onboard Acme Technology` → `Kenya` → `tax ID ACME123`
- `actually Uganda`, `company name is Acme Systems`, `use tax ID ACME456 instead`
- `why do you need approval?`, `show me the details`, then `Approve` or `Cancel`
- `onboard Techbord in Germany`, `South Africa`, `none of the above`
- `delete KE001`, `deactivate KE001`, `block KE001`, `change status KE001`
- During onboarding, `list suppliers in Kenya`, then continue providing fields.

## Workflow and policy

States: IDLE, COLLECTING_NAME, COLLECTING_COUNTRY, COLLECTING_TAX_ID, CHECKING_DUPLICATE, VALIDATING, AWAITING_APPROVAL, COMPLETED, CANCELLED.

Intents: LIST, SEARCH, STATUS, START_ONBOARDING, PROVIDE_NAME, PROVIDE_COUNTRY, PROVIDE_TAX_ID, CORRECT_FIELD, ASK_ABOUT_PENDING, APPROVE, CANCEL, UNSUPPORTED_ACTION, GENERAL_QUESTION.

A start request resets the draft. Python applies explicitly supplied fields, checks country boundaries before any onboarding MCP call, asks for missing fields and validates field syntax. Unsupported countries cancel and clear onboarding. Company names must be 2–120 characters without control characters; tax IDs use 3–32 letters/digits/hyphens. These are demo format checks, not government tax-registration verification.

Complete drafts pass exact normalized-name duplicate checks through search, then name/tax-ID duplicate validation through the API. Only successful validation creates an immutable pending snapshot. A correction invalidates that snapshot and repeats checks. Approval questions and reads preserve it. Read filters support active/inactive and the three supported countries. Reads never change a draft, including on failure.

Only an exact application approval command (`Approve`, `I approve`, `yes, approve`) or the card button can create. A model-produced APPROVE intent alone cannot write. Unsupported operations are refused with no substitute tool. Explicit high-risk operation keywords and standard cancellation/approval commands are handled before GPT; all other language uses structured extraction and application validation. Unknown/invalid model output fails closed without a tool call. Ambiguous requests ask for clarification.

Cancellation/start over clear state. `instead onboard another supplier...` starts a fresh draft. During an uncertain create, edits/restarts are blocked until the user reconciles with Approve or clears the draft with Cancel. Cancellation cannot undo a committed record.

Creation rechecks policy and uniqueness inside a SQLite transaction. Unique normalized company-name and tax-ID keys prevent concurrent duplicates. An exact replay returns the existing supplier, resolving a lost create response without inserting another record. A timeout during create is reported as **unconfirmed**, never as proof that no write occurred. Explicit approval is required again to reconcile. Drafts and approvals live in the Streamlit session; refreshing/disconnecting may lose them. Durable supplier records remain in SQLite.

## MCP contract

Exactly these five tools are exposed (the SDK injects Context; it is not a public tool argument):

```text
list_suppliers(country optional, status optional)
search_supplier(name)
get_supplier_status(id)
validate_supplier(name, country, tax_id)
create_supplier(name, country, tax_id)
```

GPT receives neither these tools nor credentials for the database/API. Python chooses every tool. The API repeats country, syntax and uniqueness checks. A per-message UUID appears in the compact trace panel and is forwarded in MCP request metadata (`trace_id`) and the API `x-trace-id` header. The panel records state transitions, tool names and successful integration responses without model reasoning or secrets.

## Tests

```sh
python -m compileall -q app tests start.py
python -m pytest -q
python -m tests.smoke_stack
```

Unit/API/UI tests require no model key and cover onboarding, correction, task switching, boundaries/no calls, approval, duplicate name/tax, malformed extraction/input, failed reads, uncertain writes, API errors and approval-card cancellation. The stack smoke test starts isolated temporary API/MCP processes on unused loopback ports with a disposable database, exercises all five real tools and cleans up.

`requirements.txt` preserves LiteLLM **1.105.0** and **mcp>=1.28,<2**. `requirements-tested.txt` captures the complete environment used for verification on Python 3.12/macOS ARM64; the main requirements file is the portable install entry point.

No live paid GPT call is included in automated tests. Natural-language examples depend on the configured model extracting the intended fields; policy execution is deterministic after extraction. Run the listed phrases with your own key before a live presentation.

## Scope

This is a local presentation demo. Services bind to loopback and do not implement authentication, multi-user authorization, durable workflow storage, rate limits or a production audit ledger. Approval is enforced by this workflow; the raw local create API/MCP capability is available to other local clients. Do not expose those listeners as an enterprise authorization boundary without adding authenticated service access and server-side approval enforcement.

## Implementation references

- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): strict schema extraction, followed by application validation.
- [MCP Python SDK v1](https://py.sdk.modelcontextprotocol.io/v1/): FastMCP and Streamable HTTP; v2 deliberately excluded.
