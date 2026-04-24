@echo off
REM agentchattr - starts server (if not running) + 3 Copilot instances + 1 Codex instance
REM Team preset for continuous iteration: 3 Copilot strategists on GPT-5.4, 1 Codex implementer.
cd /d "%~dp0.."

REM Auto-create venv and install deps on first run
if not exist ".venv" (
    python -m venv .venv
    .venv\Scripts\pip install -q -r requirements.txt >nul 2>nul
)
call .venv\Scripts\activate.bat

REM Pre-flight: check required CLIs
where copilot >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Error: "copilot" was not found on PATH.
    echo   Install with: npm install -g @github/copilot
    echo.
    pause
    exit /b 1
)

where codex >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Error: "codex" was not found on PATH.
    echo   Install it first, then try again.
    echo.
    pause
    exit /b 1
)

REM Start server if not already running, then wait for it
netstat -ano | findstr :8300 | findstr LISTENING >nul 2>&1
if %errorlevel% neq 0 (
    start "agentchattr server" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && python run.py"
)
:wait_server
netstat -ano | findstr :8300 | findstr LISTENING >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 1 /nobreak >nul
    goto :wait_server
)

start "copilot-analyst" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && python wrapper_copilot.py copilot --model gpt-5.4"
start "copilot-reviewer" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && python wrapper_copilot.py copilot --label reviewer --model gpt-5.4"
start "copilot-challenger" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && python wrapper_copilot.py copilot --label challenger --model gpt-5.4"
start "codex-implementer" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && python wrapper.py codex --label implementer"

echo.
echo   Team launch requested: 3 Copilot instances + 1 Codex instance.
echo   Open http://127.0.0.1:8300 and wait for the status pills to appear.
echo.