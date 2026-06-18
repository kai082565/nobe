@echo off
chcp 65001 > nul
echo.
echo ================================================
echo   挖礦系統安裝程式
echo ================================================
echo.

:: 需要管理員權限才能建立排程工作
net session > nul 2>&1
if %errorLevel% neq 0 (
    echo 需要管理員權限，正在重新啟動...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

if not exist "MiningSystem\launcher.exe" (
    echo [錯誤] 找不到 MiningSystem\launcher.exe
    echo 請確認 USB 內容完整
    pause
    exit /b 1
)

if not exist "config_user.json" (
    echo [錯誤] 找不到 config_user.json
    echo 請填入錢包地址後再執行
    pause
    exit /b 1
)

echo 複製礦工程式...
if not exist "C:\MiningSystem\miners\xmrig" mkdir "C:\MiningSystem\miners\xmrig"
if not exist "C:\MiningSystem\miners\lolminer" mkdir "C:\MiningSystem\miners\lolminer"
xcopy /e /y /q "%~dp0MiningSystem\miners\xmrig\*" "C:\MiningSystem\miners\xmrig\"
xcopy /e /y /q "%~dp0MiningSystem\miners\lolminer\*" "C:\MiningSystem\miners\lolminer\"

echo 開始安裝...
MiningSystem\launcher.exe --install

if %errorLevel% equ 0 (
    echo.
    echo 安裝成功！
) else (
    echo.
    echo 安裝過程發生問題，請檢查上方訊息
)

pause
