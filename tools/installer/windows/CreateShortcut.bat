@echo off
setlocal
set "APP_DIR=%~dp0"
set "APP_EXE=%APP_DIR%ClicknTranslate.exe"
set "SHORTCUT=%USERPROFILE%\Desktop\Click'n'Translate.lnk"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$shell = New-Object -ComObject WScript.Shell;" ^
  "$shortcut = $shell.CreateShortcut('%SHORTCUT%');" ^
  "$shortcut.TargetPath = '%APP_EXE%';" ^
  "$shortcut.WorkingDirectory = '%APP_DIR%';" ^
  "$shortcut.Save()"

if errorlevel 1 (
  echo Could not create the desktop shortcut.
  exit /b 1
)

echo Desktop shortcut created.
exit /b 0
