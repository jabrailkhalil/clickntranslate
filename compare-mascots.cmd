@echo off
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "tools\compare_reference_walk.py"
