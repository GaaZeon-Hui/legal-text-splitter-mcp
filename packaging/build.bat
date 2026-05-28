@echo off
echo ======================================
echo   Legal Text Splitter Desktop Build
echo ======================================
echo.

pip install pyinstaller pywebview
if errorlevel 1 goto :fail

echo.
echo Building exe...
pyinstaller --clean --noconfirm split_app.spec
if errorlevel 1 goto :fail

echo.
echo Creating installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if errorlevel 1 (
    echo Inno Setup not found, skipping installer
    echo Install from https://jrsoftware.org/isinfo.php
)
echo.
echo ======================================
echo   Done: dist\法规拆分.exe
echo   Installer: 法规拆分_安装包.exe
echo ======================================
pause
exit /b 0
:fail
echo FAILED
pause
exit /b 1
