# MCP + Enterprise Integration: Supplier Demo

A minimal, vendor-neutral presentation demo showing where the **agent boundary** can live.

## Architecture

```text
User
  ↓
Streamlit UI + tiny intent parser
  ↓
MCP capability layer
  ↓
FastAPI enterprise API
  ↓
SQLite mock supplier database
```

The intent parser is deliberately model-agnostic. Replace it later with any LLM/agent framework without changing the MCP or enterprise API layers.

## What the demo proves

- Read capabilities (`search_supplier`, `get_supplier_status`) can execute immediately.
- Validation stays behind a business capability (`validate_supplier`).
- A write capability (`create_supplier`) is **never called until a human clicks Approve**.
- The architecture trace visibly shows each MCP tool call.

## 1. Create and activate a virtual environment

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS/Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start the mock enterprise API

From the project root:

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

Optional health check: http://127.0.0.1:8001/health

## 3. Start the MCP server

In a second terminal:

```bash
python mcp_server/server.py
```

MCP endpoint: `http://127.0.0.1:8002/mcp`

## 4. Start Streamlit

In a third terminal:

```bash
streamlit run app/streamlit_app.py
```

Open: http://localhost:8501

## Demo script

### Read-only

```text
Find Siemens
```

### Check status

```text
Status SUP001
```

### Controlled write

```text
Onboard Nova Energy in Kenya with tax id DE123456789
```

The app first calls `search_supplier`, then `validate_supplier`, and then stops. It displays an approval card. Only after clicking **Approve create_supplier** does it call the MCP write tool.

## Presentation line

> The agent can reason independently without being authorized to act independently.

Then point to the trace and show that `create_supplier` does not appear until after approval.

## Reset the database

Delete:

```text
data/suppliers.db
```

Restart the FastAPI process; the seed records will be recreated automatically.

## Why this is vendor-neutral

Nothing in the enterprise boundary depends on a particular LLM vendor. You can replace the simple intent parser with OpenAI, Claude, Gemini, Ollama, LangGraph, Semantic Kernel, or another agent runtime. The MCP tools and FastAPI business layer stay the same.
