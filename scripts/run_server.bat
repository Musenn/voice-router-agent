@echo off
setlocal
cd /d "%~dp0\.."
if not exist .env (
    echo .env not found. Copy .env.example and fill in the values.
    exit /b 1
)
python -m server.main
endlocal
