@echo off
setlocal
cd /d "%~dp0"
echo.
echo  ESTUDIO MULTICANAL
echo  Preparando tu espacio de creacion...
echo.
if exist ".venv\Scripts\python.exe" goto run
where py >nul 2>nul
if errorlevel 1 goto python_fallback
py -3 -m venv .venv
if errorlevel 1 goto error
goto install
:python_fallback
where python >nul 2>nul
if errorlevel 1 goto missing_python
python -m venv .venv
if errorlevel 1 goto error
:install
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e .
if errorlevel 1 goto error
:run
.venv\Scripts\python.exe -m estudio
if errorlevel 1 goto error
goto end
:missing_python
echo Instala Python 3.11 o posterior desde https://www.python.org/downloads/
echo Activa la opcion Add Python to PATH y vuelve a abrir este archivo.
goto pause_end
:error
echo.
echo No se pudo iniciar. Comprueba Internet durante la primera instalacion.
echo Si actualizaste el codigo, ejecuta ACTUALIZAR.bat y vuelve a intentarlo.
:pause_end
pause
:end
endlocal
