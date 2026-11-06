@echo off
echo ========================================================
echo Building Hotspot.exe (Standalone Windows Binary)...
echo ========================================================

cd /d "%~dp0"
pyinstaller --noconfirm --onefile --windowed --name "Hotspot" --distpath dist client/main.py

echo.
if exist "dist\Hotspot.exe" (
    echo [SUCCESS] Hotspot.exe generated in dist\Hotspot.exe
) else (
    echo [FAILED] Executable build failed.
)
pause
