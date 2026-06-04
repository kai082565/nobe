#!/bin/bash
# 挖礦系統 macOS 一鍵設定腳本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINERS_DIR="$SCRIPT_DIR/miners/xmrig"

echo "========================================"
echo "  挖礦系統 macOS 設定腳本"
echo "========================================"

# ── 1. 確認 Python 3 ─────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[錯誤] 找不到 Python 3"
    echo "請先安裝：brew install python"
    exit 1
fi
echo "Python: $(python3 --version)"

# ── 2. 安裝 pip 套件 ──────────────────────────────────────────────────────
echo ""
echo "安裝 Python 套件 (requests)..."
python3 -m pip install requests --quiet --break-system-packages 2>/dev/null || \
python3 -m pip install requests --quiet || true

# ── 3. 下載 XMRig (macOS ARM64) ───────────────────────────────────────────
mkdir -p "$MINERS_DIR"

if [ ! -f "$MINERS_DIR/xmrig" ]; then
    echo ""
    echo "下載 XMRig macOS ARM64..."

    LATEST_URL=$(curl -s https://api.github.com/repos/xmrig/xmrig/releases/latest | \
        python3 -c "
import sys, json
data = json.load(sys.stdin)
assets = [a for a in data['assets'] if 'macos-arm64' in a['name'] and a['name'].endswith('.tar.gz')]
print(assets[0]['browser_download_url'] if assets else '')
" 2>/dev/null)

    if [ -z "$LATEST_URL" ]; then
        echo ""
        echo "[!] 自動下載失敗，請手動操作："
        echo "    1. 前往 https://github.com/xmrig/xmrig/releases/latest"
        echo "    2. 下載 xmrig-x.x.x-macos-arm64.tar.gz"
        echo "    3. 解壓後把 xmrig 執行檔放到："
        echo "       $MINERS_DIR/xmrig"
        echo "    4. 執行：chmod +x $MINERS_DIR/xmrig"
        echo ""
        echo "放好後再執行："
        echo "    python3 src/main.py --install"
        exit 0
    fi

    echo "連結：$LATEST_URL"
    curl -L "$LATEST_URL" -o /tmp/xmrig_mac.tar.gz --progress-bar

    XMRIG_FOLDER=$(tar -tzf /tmp/xmrig_mac.tar.gz | head -1 | cut -f1 -d"/")
    tar -xzf /tmp/xmrig_mac.tar.gz -C /tmp/
    cp "/tmp/$XMRIG_FOLDER/xmrig" "$MINERS_DIR/xmrig"
    chmod +x "$MINERS_DIR/xmrig"
    rm -f /tmp/xmrig_mac.tar.gz
    rm -rf "/tmp/$XMRIG_FOLDER"

    echo "XMRig 下載完成 ✓"
else
    echo "XMRig 已存在，跳過下載 ✓"
fi

# ── 4. 完成 ───────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  設定完成！"
echo "========================================"
echo ""
echo "下一步，在終端機執行："
echo ""
echo "  cd $SCRIPT_DIR"
echo "  python3 src/main.py --install"
echo ""
echo "（如果 macOS 阻擋 xmrig，請至 系統設定 → 隱私權與安全性 → 允許）"
echo ""
