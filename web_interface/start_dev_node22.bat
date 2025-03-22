@echo off
echo Starting Web Log Monitor development servers...

:: Start the backend server in a new window
start cmd /k python web_interface\run_backend.py

:: Wait a moment for the backend to initialize
echo Waiting for backend server to start on port 7171...
timeout /t 5 /nobreak > nul

:: Start the frontend with Node.js v22.x compatibility
echo Starting frontend server with Node.js v22.x compatibility...
cd web_interface\frontend
npm run start:node22

echo Development servers stopped.
