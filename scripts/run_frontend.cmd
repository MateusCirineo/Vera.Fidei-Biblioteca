@echo off
setlocal

cd /d "%~dp0..\vera_fidei_starter\frontend"

echo Starting Vera Fidei frontend on http://127.0.0.1:3000
echo Working directory: %CD%
echo.

npm run dev -- --hostname 127.0.0.1 --port 3000

echo.
echo Frontend stopped with exit code %ERRORLEVEL%.
pause
