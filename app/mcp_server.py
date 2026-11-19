import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
load_dotenv()
mcp=FastMCP('Supplier capabilities v4',host='127.0.0.1',port=int(os.getenv('MCP_PORT','8002')),stateless_http=True,json_response=True)
async def request(method,path,ctx,**kwargs):
    trace=''
    if ctx.request_context.meta:
        trace=getattr(ctx.request_context.meta,'trace_id','')
    async with httpx.AsyncClient(timeout=15) as client:
        r=await client.request(method,os.getenv('API_URL','http://127.0.0.1:8001')+path,headers={'x-trace-id':str(trace)},**kwargs)
        r.raise_for_status()
        return r.json()
@mcp.tool()
async def list_suppliers(ctx:Context,country:str|None=None,status:str|None=None)->dict:
    return await request('GET','/suppliers',ctx,params={k:v for k,v in {'country':country,'status':status}.items() if v})
@mcp.tool()
async def search_supplier(name:str,ctx:Context)->dict:
    return await request('GET','/suppliers/search',ctx,params={'name':name})
@mcp.tool()
async def get_supplier_status(id:str,ctx:Context)->dict:
    return await request('GET',f'/suppliers/{id}',ctx)
@mcp.tool()
async def validate_supplier(name:str,country:str,tax_id:str,ctx:Context)->dict:
    return await request('POST','/suppliers/validate',ctx,json={'name':name,'country':country,'tax_id':tax_id})
@mcp.tool()
async def create_supplier(name:str,country:str,tax_id:str,ctx:Context)->dict:
    return await request('POST','/suppliers',ctx,json={'name':name,'country':country,'tax_id':tax_id})
if __name__=='__main__': mcp.run(transport='streamable-http')
