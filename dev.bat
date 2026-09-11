@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ============================================================
echo   Telegram Memory Bot - Environment Verification (Dev)
echo ============================================================

:: 1. Verify .env file
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] .env file not found. Copying from .env.example...
        copy /y ".env.example" ".env" >nul
        echo [OK] .env created. Remember to update BOT_TOKEN and OPENAI_API_KEY.
    ) else (
        echo [WARN] Neither .env nor .env.example was found.
    )
) else (
    echo [OK] Configuration file .env found.
)

:: 2. Verify docker-compose.override.yml for local port bindings
if not exist "docker-compose.override.yml" (
    if exist "docker-compose.override.yml.example" (
        echo [INFO] Initializing docker-compose.override.yml for port bindings...
        copy /y "docker-compose.override.yml.example" "docker-compose.override.yml" >nul
        echo [OK] docker-compose.override.yml created.
    )
)

:: 3. Verify and setup Python environment (.venv)
set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    echo [OK] Python virtual environment .venv found.
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where uv >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        echo [INFO] Detected uv package manager. Initializing .venv...
        call uv sync --extra dev
    ) else (
        where python >nul 2>nul
        if !ERRORLEVEL! neq 0 (
            echo [ERROR] Python not found on system path. Please install Python 3.12+ or uv.
            pause
            exit /b 1
        )
        echo [INFO] Creating .venv via python -m venv...
        python -m venv .venv
        if not exist ".venv\Scripts\python.exe" (
            echo [ERROR] Failed to create virtual environment .venv.
            pause
            exit /b 1
        )
        echo [INFO] Installing project dependencies...
        call ".venv\Scripts\python.exe" -m pip install --upgrade pip
        call ".venv\Scripts\python.exe" -m pip install -e ".[dev]"
    )
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found in .venv.
    pause
    exit /b 1
)

:: 4. Verify frontend dependencies
if not exist "frontend\node_modules" (
    where npm >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        echo [INFO] Installing frontend dependencies with npm...
        pushd frontend
        call npm install
        popd
        echo [OK] Frontend dependencies installed.
    ) else (
        echo [WARN] npm not found on PATH.
    )
) else (
    echo [OK] Frontend dependencies found.
)

echo.
echo [OK] Dev environment verified and ready.
echo.

:menu
cls
echo ============================================================
echo           Telegram Memory Bot - Dev Console
echo ============================================================
echo   1. Start Databases in Docker (PostgreSQL, Redis, Neo4j)
echo   2. Start Control Panel (with Hot-Reload on :3000)
echo   3. Start Dev Chat Simulator (with Hot-Reload on :3000)
echo   4. Stop Docker Stack
echo   5. Run Tests and Linters (pytest + ruff)
echo   0. Exit
echo ============================================================
set "choice="
set /p choice="Select an option [0-5]: "
if not defined choice goto menu
set "choice=%choice: =%"

if "%choice%"=="1" goto start_docker
if "%choice%"=="2" goto start_dashboard
if "%choice%"=="3" goto start_simulator
if "%choice%"=="4" goto stop_docker
if "%choice%"=="5" goto run_tests
if "%choice%"=="0" goto exit_script

echo.
echo [ERROR] Invalid selection, please try again.
ping 127.0.0.1 -n 2 >nul
goto menu

:start_docker
echo.
echo [INFO] Starting databases in Docker (Postgres, Redis, Neo4j)...
call docker compose up -d postgres redis neo4j
if %ERRORLEVEL% equ 0 (
    echo [OK] Database containers started in background.
) else (
    echo [ERROR] Failed to start Docker Compose. Make sure Docker Desktop is running.
)
echo.
pause
goto menu

:start_dashboard
echo.
echo [INFO] Launching Control Panel Backend (:8080) + Vite Hot-Reload (:3000)...
start "Telegram Bot Dashboard Backend" /min "%PYTHON_EXE%" scripts\dashboard_server.py
start "Telegram Bot Frontend (Vite HMR)" /min cmd /c "cd /d ""%~dp0frontend"" && npm run dev"
echo [OK] Backend on :8080, UI on http://localhost:3000 (minimized windows).
ping 127.0.0.1 -n 2 >nul
goto menu

:start_simulator
echo.
echo [INFO] Launching Dev Simulator Backend (:8080) + Vite Hot-Reload (:3000)...
start "Telegram Bot Simulator Backend" /min "%PYTHON_EXE%" scripts\simulator_server.py
start "Telegram Bot Frontend (Vite HMR)" /min cmd /c "cd /d ""%~dp0frontend"" && npm run dev"
echo [OK] Simulator on :8080, UI on http://localhost:3000 (minimized windows).
ping 127.0.0.1 -n 2 >nul
goto menu

:stop_docker
echo.
echo [INFO] Stopping all Docker containers...
call docker compose down
echo [OK] Containers stopped.
echo.
pause
goto menu

:run_tests
echo.
echo [INFO] Running Ruff linter...
call "%PYTHON_EXE%" -m ruff check .
echo.
echo [INFO] Running Pytest test suite...
call "%PYTHON_EXE%" -m pytest
echo.
pause
goto menu

:exit_script
echo.
echo Goodbye!
exit /b 0
