"""Real MCP → HTTP → SQLite smoke test; no model or key needed."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from app.gateway import Gateway
from app.agent import SupplierAgent
from app.language import Extraction, Intent

def main():
    processes=[]
    def free_port():
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); return s.getsockname()[1]
    api_port,mcp_port=free_port(),free_port()
    with tempfile.TemporaryDirectory() as folder:
        env={**os.environ,'DATABASE_PATH':str(Path(folder)/'smoke.db'),'API_URL':f'http://127.0.0.1:{api_port}','MCP_PORT':str(mcp_port)}
        try:
            for module,args,port in [('uvicorn',['app.api:app','--host','127.0.0.1','--port',str(api_port)],api_port),('app.mcp_server',[],mcp_port)]:
                with socket.socket() as s:
                    if s.connect_ex(('127.0.0.1',port))==0: raise RuntimeError(f'Port {port} already in use; stop local services first.')
                processes.append(subprocess.Popen([sys.executable,'-m',module,*args],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
                for _ in range(100):
                    if processes[-1].poll() is not None: raise RuntimeError('Service startup failed')
                    with socket.socket() as s:
                        if s.connect_ex(('127.0.0.1',port))==0: break
                    time.sleep(.1)
                else: raise RuntimeError('Startup timeout')
            os.environ['MCP_URL']=f'http://127.0.0.1:{mcp_port}/mcp'
            g=Gateway()
            assert len(g.call('list_suppliers',{},'smoke-list')['suppliers'])==3
            assert len(g.call('list_suppliers',{'country':'Uganda','status':'active'},'smoke-filter')['suppliers'])==1
            assert g.call('search_supplier',{'name':'Leny'},'smoke-search')['suppliers']
            assert g.call('get_supplier_status',{'id':'KE001'},'smoke-status')['supplier']
            d={'name':'Smoke Supplier','country':'Kenya','tax_id':'SMOKE123'}
            assert g.call('validate_supplier',d,'smoke-validate')['valid']
            assert g.call('create_supplier',d,'smoke-create')['ok']
            assert not g.call('validate_supplier',d,'smoke-duplicate')['valid']
            print('PASS: five real MCP tools, filters, validation, create and duplicate checks')
        finally:
            for proc in processes: proc.terminate()
            for proc in processes:
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill()
if __name__=='__main__': main()
