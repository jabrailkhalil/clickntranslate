@echo off
chcp 65001 >nul
echo ================================================================
echo          Click'n'Translate Release Builder
echo ================================================================

cd /d "%~dp0"

echo [1/5] Setting up environment...
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1
pip install pyinstaller >nul 2>&1

echo [2/5] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [3/5] Building executable...
pyinstaller ClicknTranslate.spec --clean --noconfirm

echo [4/5] Adding extras...
if not exist "dist\ClicknTranslate" (
    echo ERROR: Build failed! dist\ClicknTranslate not found.
    pause
    exit /b 1
)

:: Create shortcut script
echo Creating 'CreateShortcut.bat'...
(
echo @echo off
echo chcp 65001 ^>nul
echo echo.
echo echo ================================================================
echo echo          CREATE SHORTCUT FOR ClicknTranslate
echo echo ================================================================
echo echo.
echo echo Move this folder to permanent location before creating shortcut!
echo echo.
echo set /p confirm=Create shortcut on Desktop? [Y/N]: 
echo if /i not "%%confirm%%"=="Y" exit /b
echo set SCRIPT_DIR=%%~dp0
echo set EXE_PATH=%%SCRIPT_DIR%%ClicknTranslate.exe
echo set DESKTOP=%%USERPROFILE%%\Desktop
echo set VBS=%%TEMP%%\shortcut.vbs
echo echo Set oWS = WScript.CreateObject("WScript.Shell") ^> "%%VBS%%"
echo echo sLinkFile = "%%DESKTOP%%\ClicknTranslate.lnk" ^>^> "%%VBS%%"
echo echo Set oLink = oWS.CreateShortcut(sLinkFile) ^>^> "%%VBS%%"
echo echo oLink.TargetPath = "%%EXE_PATH%%" ^>^> "%%VBS%%"
echo echo oLink.WorkingDirectory = "%%SCRIPT_DIR%%" ^>^> "%%VBS%%"
echo echo oLink.Save ^>^> "%%VBS%%"
echo cscript //nologo "%%VBS%%"
echo del "%%VBS%%"
echo echo.
echo echo Shortcut created on Desktop!
echo timeout /t 3 ^>nul
) > "dist\ClicknTranslate\CreateShortcut.bat"

if exist README.md copy README.md dist\ClicknTranslate\ >nul

echo ================================================================
echo [5/5] BUILD SUCCESSFUL!
echo ================================================================
echo Output folder: dist\ClicknTranslate
echo.
echo You can now archive the 'dist\ClicknTranslate' folder and release it.
echo.
pause
