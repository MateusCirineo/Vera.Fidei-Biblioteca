@echo off
setlocal

cd /d "%~dp0vera_fidei_starter\backend"
set "VERA_EMBEDDING_DEVICE=cuda"
set "ANONYMIZED_TELEMETRY=False"

echo Starting Vera Fidei backend on http://127.0.0.1:8000
echo Working directory: %CD%
echo.

".\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info

echo.
echo Backend stopped with exit code %ERRORLEVEL%.
pause
