# Script to start React app with Node.js v22.x compatibility
Write-Host "Starting React development server with Node.js v22.x compatibility..."

# Change to the frontend directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptPath

# Use the custom npm script that includes the necessary flags
npm run start:node22
