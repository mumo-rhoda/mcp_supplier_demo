from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("SUPPLIER_API_BASE", "http://127.0.0.1:8001")

mcp = FastMCP(
    "enterprise-supplier-capabilities",
    host="127.0.0.1",
    port=8002,
    stateless_http=True,
)


def api_request(method: str, path: str, **kwargs):
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()


@mcp.tool()
def search_supplier(name: str) -> dict:
    """Find suppliers by business name. Safe, read-only capability."""
    matches = api_request("GET", "/suppliers/search", params={"name": name})
    return {"count": len(matches), "suppliers": matches}


@mcp.tool()
def validate_supplier(name: str, country: str, tax_id: str) -> dict:
    """Validate supplier data and check for duplicates before onboarding."""
    return api_request(
        "POST",
        "/suppliers/validate",
        json={"name": name, "country": country, "tax_id": tax_id},
    )


@mcp.tool()
def create_supplier(name: str, country: str, tax_id: str) -> dict:
    """Create a supplier. The client must require human approval before calling this write tool."""
    return api_request(
        "POST",
        "/suppliers",
        json={"name": name, "country": country, "tax_id": tax_id},
    )


@mcp.tool()
def get_supplier_status(supplier_id: str) -> dict:
    """Get the current onboarding status for a supplier."""
    return api_request("GET", f"/suppliers/{supplier_id}")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
