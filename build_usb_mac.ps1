# ============================================================
#  建立 Mac Mini USB 安裝套件
#  執行：右鍵 → 以 PowerShell 執行
# ============================================================

$ROOT    = "C:\Users\USER\Desktop\挖礦"
$SRC_MAC = "$ROOT\mining_system_mac"
$USB_OUT = "$ROOT\build\USB_Mac"

Write-Host "========================================"
Write-Host "  建立 Mac USB 安裝套件"
Write-Host "========================================"

# 清理舊版
if (Test-Path $USB_OUT) { Remove-Item $USB_OUT -Recurse -Force }
New-Item -ItemType Directory -Force $USB_OUT | Out-Null
New-Item -ItemType Directory -Force "$USB_OUT\src" | Out-Null
New-Item -ItemType Directory -Force "$USB_OUT\miners\xmrig" | Out-Null

# 複製 Python 原始碼
Write-Host "複製程式碼..."
Copy-Item "$SRC_MAC\src\*.py" "$USB_OUT\src\"

# 複製設定樣板
Write-Host "複製設定..."
Copy-Item "$SRC_MAC\config_user.json" "$USB_OUT\"

# 複製安裝腳本
Write-Host "複製安裝腳本..."
Copy-Item "$SRC_MAC\安裝挖礦系統.command" "$USB_OUT\"

Write-Host ""
Write-Host "========================================"
Write-Host "  完成！套件位置："
Write-Host "  $USB_OUT"
Write-Host "========================================"
Write-Host ""
Write-Host "下一步："
Write-Host "1. 把 $USB_OUT 裡的所有檔案複製到 USB 根目錄"
Write-Host "2. 插入 Mac Mini"
Write-Host "3. 打開終端機，執行："
Write-Host "   bash /Volumes/[USB名稱]/安裝挖礦系統.command"
Write-Host ""
Write-Host "（如果 USB 名稱有空格，用引號包起來）"
Write-Host ""
Read-Host "按 Enter 結束"
