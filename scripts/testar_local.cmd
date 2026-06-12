@echo off
setlocal
cls

echo ============================================================
echo   Vera.Fidei — Inicializando ambiente de teste local
echo ============================================================
echo.

:: Raiz do projeto (pasta acima de scripts\)
set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\vera_fidei_starter\backend"
set "FRONTEND=%ROOT%\vera_fidei_starter\frontend"
set "VENV=%ROOT%\.venv\Scripts"

:: Verificar se venv existe
if not exist "%VENV%\python.exe" (
    echo [ERRO] Venv nao encontrado em: %VENV%
    echo Crie o venv primeiro: python -m venv .venv
    pause
    exit /b 1
)

:: Verificar se node_modules existe
if not exist "%FRONTEND%\node_modules" (
    echo [AVISO] node_modules nao encontrado. Instalando dependencias do frontend...
    cd /d "%FRONTEND%"
    call npm install
    echo.
)

:: Verificar dependencias Python (silencioso se ja instaladas)
echo [1/3] Verificando dependencias Python...
"%VENV%\pip.exe" install --quiet -r "%BACKEND%\requirements.txt"
echo       OK
echo.

:: Abrir backend em nova janela
echo [2/3] Iniciando backend (porta 8000)...
start "Vera.Fidei Backend" cmd /k "cd /d "%BACKEND%" && "%VENV%\uvicorn.exe" main:app --host 127.0.0.1 --port 8000 --reload"

:: Aguardar backend subir
echo       Aguardando backend iniciar...
timeout /t 5 /nobreak >nul

:: Abrir frontend em nova janela
echo [3/3] Iniciando frontend (porta 3000)...
start "Vera.Fidei Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

:: Aguardar frontend subir
timeout /t 6 /nobreak >nul

:: Abrir no navegador
echo.
echo Abrindo navegador...
start "" "http://localhost:3000"

echo.
echo ============================================================
echo   Tudo iniciado!
echo     Backend  ^> http://localhost:8000
echo     Swagger  ^> http://localhost:8000/docs
echo     Frontend ^> http://localhost:3000
echo.
echo   Fluxo de teste:
echo     1. http://localhost:3000/cadastro  ^> criar conta
echo     2. http://localhost:3000/verificador ^> verificar citacao logado
echo     3. http://localhost:3000/historico ^> ver o historico salvo
echo ============================================================
echo.
echo   Feche as janelas "Backend" e "Frontend" para parar.
echo.
pause
