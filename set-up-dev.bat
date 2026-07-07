@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo        Sentinel Development Setup
echo ==========================================
echo.

where py >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm is not installed.
    pause
    exit /b 1
)

echo [SUCCESS] Python Found
py --version

echo.
echo [SUCCESS] Node Found
node -v

echo.
echo [SUCCESS] npm Found
npm -v

echo.
echo ================================
echo Setting up Backend...
echo ================================

cd backend

if not exist .venv (
    echo [INFO] Creating virtual environment...
    py -m venv .venv
)

call .venv\Scripts\activate.bat

python -m ensurepip --upgrade
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        echo GROQ_API_KEY= > .env
    )
)

findstr /B "GROQ_API_KEY=" .env >nul
if errorlevel 1 (
    echo GROQ_API_KEY=>>.env
)

echo.
echo [SUCCESS] Backend setup completed.

cd ..

echo.
echo ================================
echo Setting up Frontend...
echo ================================

cd frontend

npm install

echo.
echo [SUCCESS] Frontend setup completed.

cd ..

echo.
echo ==========================================
echo Sentinel installation completed!
echo ==========================================
echo.

echo Please add your Groq API key to:
echo.
echo backend\.env
echo.

echo Starting Backend...

start "Sentinel Backend" cmd /k "cd /d backend && call .venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 5 >nul

echo Starting Frontend...

start "Sentinel Frontend" cmd /k "cd /d frontend && npm run dev"

echo.
echo ==========================================
echo Sentinel is running!
echo ==========================================
echo.
echo Backend : http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause