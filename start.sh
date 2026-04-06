#!/bin/bash

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
