@echo off
title SENTRA Frontend - Dev Server
echo ===================================================
echo   Starting SENTRA Frontend Development Server
echo ===================================================
echo.

cd /d "%~dp0"

echo Checking node_modules...
if not exist "node_modules\" (
    echo Installing dependencies...
    call npm install
)

echo Starting Vite dev server and opening default browser...
start "" "http://localhost:5173/tr"
npm run dev -- --open
