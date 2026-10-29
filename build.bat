@echo off
pip install -r requirements.txt
pyinstaller --noconsole --onefile --clean --name "Nivalis" main.py
echo Build complete! Executable is located in dist/Nivalis.exe
pause