#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# launch.command — double-click this to start The Signal web app
# ─────────────────────────────────────────────────────────────────────────────

# Move to the directory containing this script (the project root)
cd "$(dirname "$0")"

echo ""
echo "  📡 The Signal"
echo "  ─────────────────────────────────"
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "  ✗ Python 3 not found."
  echo "  Install it from https://www.python.org/downloads/"
  read -p "  Press Enter to close…"
  exit 1
fi

PYTHON=$(command -v python3)
echo "  Python: $($PYTHON --version)"

# ── Install / update dependencies ────────────────────────────────────────────
echo "  Checking dependencies…"
if ! $PYTHON -c "import fastapi, uvicorn" &>/dev/null 2>&1; then
  echo "  Installing web dependencies (first run only)…"
  $PYTHON -m pip install "fastapi>=0.111" "uvicorn[standard]>=0.30" -q
  if [ $? -ne 0 ]; then
    echo "  ✗ pip install failed. Run manually:"
    echo "    pip install fastapi uvicorn[standard]"
    read -p "  Press Enter to close…"
    exit 1
  fi
fi

# ── Load .env so MPS env vars are available ───────────────────────────────────
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

# ── Port ──────────────────────────────────────────────────────────────────────
PORT=${SIGNAL_PORT:-8765}

# Check if port is already in use
if lsof -i :$PORT -sTCP:LISTEN &>/dev/null 2>&1; then
  echo ""
  echo "  ⚠  Port $PORT is already in use."
  echo "  The Signal may already be running."
  echo "  Opening http://localhost:$PORT …"
  open "http://localhost:$PORT"
  read -p "  Press Enter to close…"
  exit 0
fi

# ── Start server ──────────────────────────────────────────────────────────────
echo ""
echo "  Starting server on http://localhost:$PORT"
echo "  Press Ctrl+C to stop."
echo ""

# Open browser after a short delay
(sleep 2 && open "http://localhost:$PORT") &

# Run uvicorn (log to Terminal + ~/the-signal.log)
LOG_FILE="$HOME/the-signal.log"
echo "  Logging to $LOG_FILE"
echo ""
export PYTHONPATH="$(pwd):$PYTHONPATH"
$PYTHON -m uvicorn web.server:app --host 127.0.0.1 --port $PORT --log-level warning 2>&1 | tee -a "$LOG_FILE"

echo ""
echo "  Server stopped."
read -p "  Press Enter to close…"
