from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "suppliers.db"

app = FastAPI(title="Mock Supplier Enterprise API", version="1.0.0")


class SupplierIn(BaseModel):
    name: str = Field(min_length=2)
    country: str = Field(min_length=2)
    tax_id: str = Field(min_length=3)


class Supplier(SupplierIn):
    id: str
    status: str


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                country TEXT NOT NULL,
                tax_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO suppliers (id, name, country, tax_id, status) VALUES (?, ?, ?, ?, ?)",
                [
                    ("SUP001", "Siemens AG", "Germany", "DE129274202", "ACTIVE"),
                    ("SUP002", "Acme Kenya Ltd", "Kenya", "P051234567A", "ACTIVE"),
                    ("SUP003", "TechNova GmbH", "Germany", "DE998877665", "BLOCKED"),
                ],
            )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/suppliers/search", response_model=list[Supplier])
def search_suppliers(name: str) -> list[Supplier]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM suppliers WHERE lower(name) LIKE lower(?) ORDER BY name",
            (f"%{name}%",),
        ).fetchall()
    return [Supplier(**dict(row)) for row in rows]


@app.post("/suppliers/validate")
def validate_supplier(supplier: SupplierIn) -> dict:
    errors: list[str] = []
    if len(supplier.name.strip()) < 3:
        errors.append("Supplier name must have at least 3 characters.")
    if len(supplier.tax_id.replace(" ", "")) < 6:
        errors.append("Tax ID looks too short.")

    with connect() as conn:
        duplicate = conn.execute(
            "SELECT id, name FROM suppliers WHERE lower(name)=lower(?) OR tax_id=?",
            (supplier.name.strip(), supplier.tax_id.strip()),
        ).fetchone()

    if duplicate:
        errors.append(f"Potential duplicate: {duplicate['name']} ({duplicate['id']}).")

    return {"valid": not errors, "errors": errors}


@app.post("/suppliers", response_model=Supplier, status_code=201)
def create_supplier(supplier: SupplierIn) -> Supplier:
    validation = validate_supplier(supplier)
    if not validation["valid"]:
        raise HTTPException(status_code=409, detail=validation["errors"])

    supplier_id = f"SUP-{uuid4().hex[:8].upper()}"
    created = Supplier(
        id=supplier_id,
        name=supplier.name.strip(),
        country=supplier.country.strip(),
        tax_id=supplier.tax_id.strip(),
        status="PENDING_REVIEW",
    )
    with connect() as conn:
        conn.execute(
            "INSERT INTO suppliers (id, name, country, tax_id, status) VALUES (?, ?, ?, ?, ?)",
            (created.id, created.name, created.country, created.tax_id, created.status),
        )
    return created


@app.get("/suppliers/{supplier_id}", response_model=Supplier)
def get_supplier(supplier_id: str) -> Supplier:
    with connect() as conn:
        row = conn.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return Supplier(**dict(row))
