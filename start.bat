@echo off
cd /d "%~dp0"
echo Starting Saathi AI (Unified FastAPI Server)...
start "" http://127.0.0.1:8000
python -m uvicorn main:app --host 127.0.0.1 --port 8000
if %ERRORLEVEL% NEQ 0 (
    echo Python not found on standard PATH, attempting local Python...
    "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
)
pause
