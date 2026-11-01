from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import streamlit as st
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "http://127.0.0.1:8002/mcp"

st.set_page_config(page_title="Enterprise Supplier Agent", page_icon="🔌", layout="wide")


@dataclass
class SupplierDraft:
    name: str
    country: str
    tax_id: str


async def _mcp_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    async with streamable_http_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            if getattr(result, "structuredContent", None):
                return result.structuredContent
            for block in result.content:
                if getattr(block, "type", None) == "text":
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        return block.text
            return {"raw": str(result)}


def mcp_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    result = asyncio.run(_mcp_call(tool_name, arguments))
    st.session_state.trace.append({"tool": tool_name, "arguments": arguments, "result": result})
    return result


def parse_onboard_command(text: str) -> SupplierDraft | None:
    # Demo grammar:
    # onboard Nova Energy GmbH in Germany with tax id DE123456789
    match = re.search(
        r"(?:onboard|create|add)\s+(.+?)\s+in\s+(.+?)\s+with\s+tax\s*(?:id|number)?\s+([A-Za-z0-9-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return SupplierDraft(
        name=match.group(1).strip(),
        country=match.group(2).strip(),
        tax_id=match.group(3).strip(),
    )


def parse_search_command(text: str) -> str | None:
    match = re.search(r"(?:find|search|check)\s+(?:supplier\s+)?(.+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def parse_status_command(text: str) -> str | None:
    match = re.search(r"status\s+(?:of\s+)?(SUP[-A-Za-z0-9]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


if "messages" not in st.session_state:
    st.session_state.messages = []
if "trace" not in st.session_state:
    st.session_state.trace = []
if "pending_supplier" not in st.session_state:
    st.session_state.pending_supplier = None

st.title("Enterprise Supplier Agent")
st.caption("Vendor-neutral MCP demo: business capabilities above enterprise-system complexity")

left, right = st.columns([2, 1])

with left:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.pending_supplier:
        draft = st.session_state.pending_supplier
        st.warning(
            "**Approval required** before calling `create_supplier`.\n\n"
            f"**Supplier:** {draft['name']}  \n"
            f"**Country:** {draft['country']}  \n"
            f"**Tax ID:** {draft['tax_id']}"
        )
        approve_col, cancel_col = st.columns(2)
        with approve_col:
            if st.button("✅ Approve create_supplier", use_container_width=True, type="primary"):
                try:
                    result = mcp_call("create_supplier", draft)
                    message = (
                        f"Created **{result['name']}** as `{result['id']}`. "
                        f"Current status: **{result['status']}**."
                    )
                except Exception as exc:
                    message = f"Create failed: `{exc}`"
                st.session_state.messages.append({"role": "assistant", "content": message})
                st.session_state.pending_supplier = None
                st.rerun()
        with cancel_col:
            if st.button("Cancel", use_container_width=True):
                st.session_state.messages.append(
                    {"role": "assistant", "content": "Creation cancelled. No write tool was called."}
                )
                st.session_state.pending_supplier = None
                st.rerun()

    prompt = st.chat_input("Try: Onboard Nova Energy GmbH in Germany with tax id DE123456789")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        try:
            draft = parse_onboard_command(prompt)
            status_id = parse_status_command(prompt)
            search_name = parse_search_command(prompt) if not draft and not status_id else None

            if draft:
                search = mcp_call("search_supplier", {"name": draft.name})
                if search.get("count", 0) > 0:
                    names = ", ".join(s["name"] for s in search["suppliers"])
                    response = f"I found possible existing supplier(s): **{names}**. I won't create a duplicate."
                else:
                    validation = mcp_call(
                        "validate_supplier",
                        {"name": draft.name, "country": draft.country, "tax_id": draft.tax_id},
                    )
                    if validation.get("valid"):
                        st.session_state.pending_supplier = draft.__dict__
                        response = (
                            "Supplier was not found and validation passed. "
                            "A human must approve before I call the write capability `create_supplier`."
                        )
                    else:
                        response = "Validation failed: " + "; ".join(validation.get("errors", []))
            elif status_id:
                supplier = mcp_call("get_supplier_status", {"supplier_id": status_id})
                response = f"**{supplier['name']}** is currently **{supplier['status']}**."
            elif search_name:
                result = mcp_call("search_supplier", {"name": search_name})
                if result.get("count", 0):
                    response = "Found:\n" + "\n".join(
                        f"- `{s['id']}` — **{s['name']}** ({s['country']}) — {s['status']}"
                        for s in result["suppliers"]
                    )
                else:
                    response = "No matching supplier found."
            else:
                response = (
                    "I understand three demo intents:\n\n"
                    "- `Find Siemens`\n"
                    "- `Status SUP001`\n"
                    "- `Onboard Nova Energy GmbH in Germany with tax id DE123456789`"
                )
        except Exception as exc:
            response = (
                "I couldn't reach the MCP capability layer. Make sure the FastAPI and MCP server are running. "
                f"Details: `{exc}`"
            )

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

with right:
    st.subheader("Architecture trace")
    st.caption("This makes the agent boundary visible during the talk.")
    if not st.session_state.trace:
        st.info("MCP tool calls will appear here.")
    for i, event in enumerate(reversed(st.session_state.trace), start=1):
        with st.expander(f"{event['tool']} · call {len(st.session_state.trace) - i + 1}", expanded=(i == 1)):
            st.code(json.dumps(event, indent=2), language="json")

    if st.button("Clear trace"):
        st.session_state.trace = []
        st.rerun()

    st.divider()
    st.markdown(
        """
**Boundary shown in this demo**

`User → UI/intent → MCP → Enterprise API → SQLite`

The UI never writes directly to the database. Even the approved write goes through the MCP business capability.
"""
    )
