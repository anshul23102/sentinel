#!/usr/bin/env bash

set -Eeuo pipefail

GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

trap 'error "Command failed at line $LINENO"; echo "Failed command: $BASH_COMMAND"; exit 1' ERR

run() {
    info "$*"
    "$@"
    success "Done"
}

if [[ ! -d backend || ! -d frontend ]]; then
    error "Run this script from the project root."
    exit 1
fi

info "Checking Python..."

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    error "Python not found."
    exit 1
fi

VERSION=$("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
success "Found Python $VERSION"

info "Checking Node.js..."

if ! command -v node >/dev/null 2>&1; then
    error "Node.js is not installed."
    exit 1
fi

success "Found Node $(node -v)"

if ! command -v npm >/dev/null 2>&1; then
    error "npm not found."
    exit 1
fi

success "Found npm $(npm -v)"

info "Setting up backend..."

cd backend

if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment..."
    run "$PYTHON" -m venv .venv
else
    success "Virtual environment already exists."
fi

info "Activating virtual environment..."
source .venv/bin/activate
success "Virtual environment activated."

run python -m ensurepip --upgrade
run python -m pip install --upgrade pip
run python -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        run cp .env.example .env
        success ".env created from .env.example."
    else
        run touch .env
        echo "GROQ_API_KEY=" >> .env
        success ".env created."
    fi
fi

if ! grep -q "^GROQ_API_KEY=" .env; then
    echo "GROQ_API_KEY=" >> .env
fi

success "Backend setup completed."

deactivate
success "Virtual environment deactivated."

cd ..

info "Installing frontend dependencies..."

cd frontend

run npm install

success "Frontend setup completed."

cd ..

echo
echo "=================================================="
success "Sentinel installation completed successfully!"
echo "=================================================="
echo
echo
echo "=================================================="
success "Sentinel installation completed successfully!"
echo "=================================================="
echo

info "Starting backend..."

cd backend
source .venv/bin/activate

python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd ..

sleep 3

info "Starting frontend..."

cd frontend

npm run dev &
FRONTEND_PID=$!

cd ..

echo
success "Sentinel is now running!"
echo
echo "Backend : http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo
warning "Remember to add your GROQ_API_KEY to backend/.env if you haven't already."
echo
echo "Press Ctrl+C to stop both services."

cleanup() {
    echo
    info "Stopping Sentinel..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    success "Sentinel stopped."
}

trap cleanup INT TERM

wait