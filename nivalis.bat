@echo off
rem Запуск Nivalis из исходников на Windows.
rem При первом запуске создаёт .venv рядом со скриптом и ставит зависимости.
rem
rem   nivalis.bat              запустить
rem   nivalis.bat --reinstall  пересоздать окружение и переустановить зависимости
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "STAMP=%VENV%\requirements.installed"

if /i "%~1"=="--reinstall" (
    if exist "%VENV%" (
        echo Удаляю старое окружение...
        rmdir /s /q "%VENV%"
    )
)

rem --- Python 3.10+ ---
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo Нужен Python 3.10 или новее: https://www.python.org/downloads/
    echo При установке отметьте "Add python.exe to PATH".
    pause
    exit /b 1
)

rem --- Виртуальное окружение ---
if not exist "%VENV%\Scripts\pythonw.exe" (
    echo Создаю виртуальное окружение в %VENV% ...
    %PY% -m venv "%VENV%" || goto :fail
)

fc /b "%ROOT%requirements.txt" "%STAMP%" >nul 2>&1
if errorlevel 1 (
    echo Устанавливаю зависимости ^(один раз, может занять минуту^)...
    "%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip || goto :fail
    "%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt" || goto :fail
    copy /y "%ROOT%requirements.txt" "%STAMP%" >nul
)

rem --- Запуск без окна консоли ---
start "" "%VENV%\Scripts\pythonw.exe" "%ROOT%main.py"
exit /b 0

:fail
echo Не удалось подготовить окружение. Попробуйте: nivalis.bat --reinstall
pause
exit /b 1
