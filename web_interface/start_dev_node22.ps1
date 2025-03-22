# Script to start both backend and frontend with Node.js v22.x compatibility

Write-Host "Starting Web Log Monitor development servers..."

# Start the backend server in a new PowerShell window
$backendProcess = Start-Process powershell -ArgumentList "-Command python web_interface/run_backend.py" -PassThru -WindowStyle Normal

# Wait a moment for the backend to initialize
Write-Host "Waiting for backend server to start on port 8000..."
Start-Sleep -Seconds 5

# Start the frontend with Node.js v22.x compatibility
Write-Host "Starting frontend server with Node.js v22.x compatibility..."
$frontendDir = Join-Path -Path $PSScriptRoot -ChildPath "frontend"
Set-Location -Path $frontendDir

# Use the custom npm script that includes the necessary flags
npm run start:node22

# When the frontend is closed, also close the backend
if ($backendProcess -ne $null) {
    Write-Host "Stopping backend server..."
    Stop-Process -Id $backendProcess.Id -Force
}

Write-Host "Development servers stopped."
