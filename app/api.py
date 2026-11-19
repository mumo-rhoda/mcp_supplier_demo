from contextlib import asynccontextmanager
import sqlite3
import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from app import store
from app.policy import country as normalise

@asynccontextmanager
async def lifespan(app):
    store.init()
    yield
app=FastAPI(title='Supplier Integration API v4', lifespan=lifespan)
class Supplier(BaseModel):
    model_config=ConfigDict(extra='forbid', strict=True)
    name:str
    country:str
    tax_id:str
@app.middleware('http')
async def trace(request:Request, call_next):
    request.state.trace_id=request.headers.get('x-trace-id',str(uuid.uuid4()))[:64]
    try:
        response=await call_next(request)
    except Exception:
        response=JSONResponse(status_code=503,content={'detail':'Supplier service unavailable.'})
    response.headers['x-trace-id']=request.state.trace_id
    return response
@app.get('/health')
def health():
    with store.connect() as c: c.execute('SELECT 1')
    return {'ok':True}
@app.get('/suppliers')
def suppliers(country:str|None=None,status:str|None=None):
    if country and not normalise(country): raise HTTPException(400,'Unsupported country')
    if status and status not in ('active','inactive'): raise HTTPException(400,'Invalid status')
    return {'suppliers':store.rows(normalise(country),status)}
@app.get('/suppliers/search')
def search(name:str):
    if not name.strip(): raise HTTPException(400,'Name required')
    return {'suppliers':store.rows(name=name)}
@app.get('/suppliers/{supplier_id}')
def supplier_status(supplier_id:str):
    result=store.rows(supplier_id=supplier_id)
    return {'supplier':result[0] if result else None}
@app.post('/suppliers/validate')
def validate(d:Supplier): return store.validate(d.model_dump())
@app.post('/suppliers')
def create(d:Supplier): return store.create(d.model_dump())
