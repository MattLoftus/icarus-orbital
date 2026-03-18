#!/bin/bash
# Start both the API server and the frontend dev server.
# API: http://localhost:8790
# Frontend: http://localhost:5180 (proxies /api to :8790)

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Orbital Mechanics..."

# Start API server
cd "$DIR"
source venv/bin/activate
python -m src.api.server > /tmp/orbital-api.log 2>&1 &
API_PID=$!
echo "  API server started (PID $API_PID) → http://localhost:8790"

# Start frontend dev server
cd "$DIR/dashboard"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 22 > /dev/null 2>&1
npm run dev > /tmp/orbital-dev.log 2>&1 &
DEV_PID=$!
echo "  Frontend started (PID $DEV_PID) → http://localhost:5180"

echo ""
echo "  Logs: /tmp/orbital-api.log, /tmp/orbital-dev.log"
echo "  Stop: kill $API_PID $DEV_PID"

# Wait for either to exit
wait
