"""Local process supervisor. Run with Python 3.12 from any directory."""
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
import time
import urllib.request
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
load_dotenv()
children=[]
def stop(*_):
    for p in reversed(children):
        if p.poll() is None: p.terminate()
    for p in children:
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill()
def main():
    if sys.version_info[:2]!=(3,12): raise SystemExit('Please use Python 3.12.')
    if not os.getenv('OPENAI_API_KEY'): raise SystemExit('Set OPENAI_API_KEY in .env before starting.')
    for port in (8001,8002,8501):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'Port {port} is in use. Stop that service or run the components individually on other ports.')
    Path('logs').mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    try:
        for name,args,url in [('api',['-m','uvicorn','app.api:app','--host','127.0.0.1','--port','8001'],'http://127.0.0.1:8001/health'),('mcp',['-m','app.mcp_server'],None),('ui',['-m','streamlit','run','app/ui.py','--server.address','127.0.0.1','--server.port','8501'],None)]:
            log=open(f'logs/{name}.log','a')
            children.append(subprocess.Popen([sys.executable,*args],stdout=log,stderr=log)); log.close()
            if url:
                for _ in range(50):
                    if children[-1].poll() is not None: raise RuntimeError('API failed; see logs/api.log')
                    try:
                        with urllib.request.urlopen(url,timeout=1): break
                    except Exception: time.sleep(.2)
                else: raise RuntimeError('API startup timeout')
            else: time.sleep(1)
        print('Supplier Services: http://127.0.0.1:8501 (Ctrl+C to stop)')
        while all(p.poll() is None for p in children): time.sleep(.5)
        raise RuntimeError('A service stopped. See logs/.')
    except KeyboardInterrupt: pass
    finally: stop()
if __name__=='__main__': main()
