@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e .
pause
goto end
:missing
echo Abre primero INICIAR.bat.
pause
:end
endlocal
