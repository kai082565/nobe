@echo off
chcp 65001 > nul
echo.
echo ================================================
echo   打包 USB 安裝套件
echo ================================================
echo.

cd /d "%~dp0.."

:: 安裝依賴
echo [1/4] 安裝 Python 依賴...
pip install pyinstaller requests -q

:: 打包成單一 exe
echo [2/4] 打包 launcher.exe...
pyinstaller ^
    --onefile ^
    --noupx ^
    --name launcher ^
    --distpath build\dist ^
    --workpath build\pyinstaller_tmp ^
    --specpath build ^
    --noconfirm ^
    src\main.py

if %errorLevel% neq 0 (
    echo [錯誤] 打包失敗
    pause
    exit /b 1
)

:: 建立 USB 目錄結構
echo [3/4] 建立 USB 資料夾結構...
if exist "build\USB" rd /s /q "build\USB"

mkdir "build\USB\MiningSystem\miners\xmrig"
mkdir "build\USB\MiningSystem\miners\lolminer"

copy "build\dist\launcher.exe"              "build\USB\MiningSystem\launcher.exe"
copy "usb_template\install.bat"             "build\USB\install.bat"
copy "usb_template\config_user.json"        "build\USB\config_user.json"

echo [4/4] 完成！

echo.
echo ================================================
echo  USB 套件已建立在：build\USB\
echo.
echo  接下來還需要：
echo  1. 下載 XMRig 解壓到：
echo     build\USB\MiningSystem\miners\xmrig\
echo     下載：https://github.com/xmrig/xmrig/releases
echo.
echo  2. 下載 lolMiner 解壓到：
echo     build\USB\MiningSystem\miners\lolminer\
echo     下載：https://github.com/Lolliedieb/lolMiner-releases/releases
echo.
echo  3. 填入你的錢包地址到：
echo     build\USB\config_user.json
echo.
echo  4. 把 build\USB\ 的全部內容複製到 USB 隨身碟
echo ================================================
pause
