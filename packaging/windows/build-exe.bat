@echo off
rem Сборка dist\Nivalis-<версия>-x86_64.exe (PyInstaller, один файл).
rem Ожидает Python с зависимостями из requirements.txt и pyinstaller:
rem переменная PYTHON (по умолчанию python). Версию можно задать переменной VERSION,
rem иначе она берётся из nivalis\config.py. Обычно вызывается из build.bat в корне или из CI.
setlocal
chcp 65001 >nul
if "%PYTHON%"=="" set "PYTHON=python"
pushd "%~dp0..\.." || exit /b 1

if "%VERSION%"=="" (
    for /f "usebackq delims=" %%v in (`call "%PYTHON%" packaging\version.py`) do set "VERSION=%%v"
)
if "%VERSION%"=="" (
    echo Не удалось определить версию.
    popd
    exit /b 1
)
set "NAME=Nivalis-%VERSION%-x86_64"

echo ==^> PyInstaller (onefile): %NAME%.exe
"%PYTHON%" -m PyInstaller --noconfirm --clean --noconsole --onefile ^
    --name "%NAME%" ^
    --distpath dist ^
    --workpath build\windows\work ^
    --specpath build\windows ^
    main.py
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" exit /b %RC%
echo Готово: dist\%NAME%.exe
exit /b 0
