@echo off
rem Сборка Nivalis.exe. Готовит окружение в build\venv и вызывает packaging\windows\build-exe.bat.
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "VENV=%ROOT%build\venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo Создаю окружение для сборки...
    py -3 -m venv "%VENV%" 2>nul || python -m venv "%VENV%" || goto :fail
)
"%VENV%\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "%ROOT%requirements.txt" pyinstaller || goto :fail

set "PYTHON=%VENV%\Scripts\python.exe"
call "%ROOT%packaging\windows\build-exe.bat" || goto :fail
pause
exit /b 0

:fail
echo Сборка не удалась.
pause
exit /b 1
