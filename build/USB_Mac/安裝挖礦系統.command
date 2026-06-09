#!/bin/bash
# ============================================================
#  挖礦系統 USB 一鍵安裝腳本 (macOS Apple Silicon)
#  使用方法：插入 USB → 雙擊此檔案
# ============================================================
USB_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/Library/Application Support/MiningSystem"

echo "========================================"
echo "  挖礦系統安裝程式"
echo "========================================"
echo ""

# ── 1. 確認 Python 3 ─────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[錯誤] 找不到 Python 3"
    echo ""
    echo "請先安裝 Python 3："
    echo "  https://www.python.org/downloads/macos/"
    echo ""
    read -p "按 Enter 結束..."
    exit 1
fi
echo "Python: $(python3 --version)"

# ── 2. 安裝 pip 套件 ──────────────────────────────────────────
echo "安裝必要套件 (requests)..."
python3 -m pip install requests --quiet --break-system-packages 2>/dev/null || \
    python3 -m pip install requests --quiet || true

# ── 3. 複製程式碼到本機 ───────────────────────────────────────
echo "複製程式碼..."
mkdir -p "$INSTALL_DIR/miners/xmrig"
rm -rf "$INSTALL_DIR/src"
cp -r "$USB_DIR/src" "$INSTALL_DIR/"
cp "$USB_DIR/config_user.json" "$INSTALL_DIR/"

# ── 4. 下載 XMRig ARM64 ───────────────────────────────────────
if [ ! -f "$INSTALL_DIR/miners/xmrig/xmrig" ]; then
    echo ""
    echo "下載 XMRig (Apple Silicon 版)..."

    LATEST_URL=$(curl -s https://api.github.com/repos/xmrig/xmrig/releases/latest | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    assets = [a for a in data.get('assets', [])
              if 'macos-arm64' in a['name'] and a['name'].endswith('.tar.gz')]
    print(assets[0]['browser_download_url'] if assets else '')
except Exception as e:
    print('')
" 2>/dev/null)

    if [ -z "$LATEST_URL" ]; then
        echo ""
        echo "[錯誤] 無法取得下載連結，請確認網路連線"
        echo ""
        echo "手動安裝方式："
        echo "1. 前往 https://github.com/xmrig/xmrig/releases/latest"
        echo "2. 下載 xmrig-x.x.x-macos-arm64.tar.gz"
        echo "3. 解壓後把 xmrig 執行檔放到："
        echo "   $INSTALL_DIR/miners/xmrig/xmrig"
        echo "4. 重新執行本腳本"
        read -p "按 Enter 結束..."
        exit 1
    fi

    echo "連結：$LATEST_URL"
    curl -L "$LATEST_URL" -o /tmp/xmrig_mac.tar.gz --progress-bar

    FOLDER=$(tar -tzf /tmp/xmrig_mac.tar.gz | head -1 | cut -f1 -d"/")
    tar -xzf /tmp/xmrig_mac.tar.gz -C /tmp/
    cp "/tmp/$FOLDER/xmrig" "$INSTALL_DIR/miners/xmrig/xmrig"
    chmod +x "$INSTALL_DIR/miners/xmrig/xmrig"
    rm -f /tmp/xmrig_mac.tar.gz
    rm -rf "/tmp/$FOLDER"
    echo "XMRig 下載完成 ✓"
else
    echo "XMRig 已存在，跳過下載 ✓"
fi

# ── 5. 偵測硬體、生成設定、設置開機自動啟動 ──────────────────
echo ""
echo "偵測硬體並設定..."
python3 "$INSTALL_DIR/src/main.py" --configure

# ── 6. macOS 安全性：移除隔離屬性 ────────────────────────────
xattr -d com.apple.quarantine "$INSTALL_DIR/miners/xmrig/xmrig" 2>/dev/null || true

echo "========================================"
echo "  安裝完成！"
echo "========================================"
echo ""
echo "下次登入會自動開始挖礦"
echo "現在立即啟動..."
echo ""

# ── 7. 啟動挖礦 ───────────────────────────────────────────────
python3 "$INSTALL_DIR/src/main.py" --mine
