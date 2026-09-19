@echo off
echo Starting VoiceShield AI Services...

REM --- Backend (skip if port 8000 already in use) ---
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo Backend already running on :8000 - skipping.
) else (
  start "VoiceShield Backend" cmd /k "cd /d ""%~dp0backend"" && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
)

REM --- Frontend (skip if port 5173 already in use) ---
netstat -ano | findstr /R /C:":5173 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo Frontend already running on :5173 - skipping.
) else (
  start "VoiceShield Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
)

echo Both services launched successfully!
echo Backend API:  http://localhost:8000
echo Frontend App: http://localhost:5173