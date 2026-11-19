import asyncio
import json
import os
from datetime import timedelta
from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client

class Gateway:
    def call(self,tool,args,trace_id):
        return asyncio.run(self._call(tool,args,trace_id))
    async def _call(self,tool,args,trace_id):
        async with asyncio.timeout(25):
            async with streamablehttp_client(os.getenv('MCP_URL','http://127.0.0.1:8002/mcp'),timeout=timedelta(seconds=15)) as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    result=await session.call_tool(tool,args,meta={'trace_id':trace_id})
                    if result.isError: raise RuntimeError('MCP tool failed')
                    if result.structuredContent is not None: return result.structuredContent
                    return json.loads(''.join(c.text for c in result.content if isinstance(c,types.TextContent)))
