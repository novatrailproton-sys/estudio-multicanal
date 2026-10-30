@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto local_python
py -3 scripts\publicar_github.py
goto end
:local_python
.venv\Scripts\python.exe scripts\publicar_github.py
:end
pause
endlocal
