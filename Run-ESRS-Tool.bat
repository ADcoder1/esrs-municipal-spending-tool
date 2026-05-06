@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 launch_local_tool.py
) else (
  python launch_local_tool.py
)

pause
