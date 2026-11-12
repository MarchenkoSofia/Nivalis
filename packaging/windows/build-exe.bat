@echo off
rem Сборка dist\Nivalis.exe (PyInstaller, один файл).
rem Ожидает Python с зависимостями из requirements.txt и pyinstaller:
rem переменная PYTHON (по умолчанию python). Обычно вызывается из build.bat в корне или из CI.
setlocal
chcp 65001 >nul
if "%PYTHON%"=="" set "PYTHON=python"
pushd "%~dp0..\.." || exit /b 1

echo ==^> PyInstaller (onefile)
"%PYTHON%" -m PyInstaller --noconfirm --clean --noconsole --onefile ^
    --name Nivalis ^
    --distpath dist ^
    --workpath build\windows\work ^
    --specpath build\windows ^
    main.py
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" exit /b %RC%
echo Готово: dist\Nivalis.exe
exit /b 0
