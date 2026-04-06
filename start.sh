#!/bin/bash

# Ensure we're in the project directory and the virtual environment is activated
export PYTHONPATH=.
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Warning: Virtual environment not found at venv/bin/activate. Make sure you run this script from the project root."
fi

# Start the proxy server on port 8001
echo "Starting proxy server on port 8001..."
uvicorn app.main:app --host 0.0.0.0 --port 8001 &
PROXY_PID=$!

# Start the dashboard server on port 8080
echo "Starting dashboard server on port 8080..."
uvicorn app.dashboard:app --host 0.0.0.0 --port 8080 &
DASH_PID=$!

# Trap SIGINT and SIGTERM to gracefully shut down both servers
trap "echo 'Shutting down servers...'; kill $PROXY_PID $DASH_PID" SIGINT SIGTERM EXIT

# Wait for all background processes to finish
wait
