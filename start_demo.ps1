Write-Host "Open three PowerShell windows and run:" -ForegroundColor Cyan
Write-Host "1) uvicorn api.main:app --host 127.0.0.1 --port 8001"
Write-Host "2) python mcp_server/server.py"
Write-Host "3) streamlit run app/streamlit_app.py"
