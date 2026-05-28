"""
開發機直接安裝腳本
不需要 USB，直接把這台電腦設定好
"""

import sys
import json
import shutil
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from detector import detect
from configurator import build_xmrig_config, write_xmrig_config
from installer import INSTALL_DIR, _save_config

BASE_DIR    = Path(__file__).parent
MINERS_SRC  = BASE_DIR / "miners"
PYTHON_EXE  = sys.executable
MAIN_PY     = BASE_DIR / "src" / "main.py"

WALLET_XMR  = "878ttBnGWbrcGpjE2wnaf18NyFnJzpuCUWLL4pXiNAHELZAJoDr8fBY53bRu88P7SN5YKm3Bp8AwU7US759eVwcYD4Tz4RS"
WORKER_NAME = "rig01"
ELEC_COST   = 4.5

print("=" * 50)
print("  挖礦系統安裝")
print("=" * 50)

# 偵測硬體
print("\n偵測硬體...")
hw = detect()
print(hw.summary())

# 檢查哪些礦工程式存在
xmrig_exe   = MINERS_SRC / "xmrig"   / "xmrig.exe"
lolminer_exe = MINERS_SRC / "lolminer" / "lolminer.exe"

if xmrig_exe.exists():
    miner_type, coin = "xmrig_cpu", "XMR"
    print(f"\n使用 XMRig CPU 挖 XMR（lolMiner 尚未安裝）")
elif lolminer_exe.exists():
    miner_type, coin = "lolminer", "ETC"
    print(f"\n使用 lolMiner 挖 ETC")
else:
    print("[錯誤] 找不到任何礦工程式")
    sys.exit(1)

# 建立安裝目錄
INSTALL_DIR.mkdir(parents=True, exist_ok=True)
print(f"安裝路徑：{INSTALL_DIR}")

# 複製礦工程式
dst_miners = INSTALL_DIR / "miners"
if dst_miners.exists():
    shutil.rmtree(dst_miners)
shutil.copytree(MINERS_SRC, dst_miners)
print("礦工程式已複製")

# 建立設定檔
config = {
    "miner_type": miner_type,
    "coin": coin,
    "worker_name": WORKER_NAME,
    "electricity_ntd_per_kwh": ELEC_COST,
    "wallets": {
        "XMR":  WALLET_XMR,
        "ETC":  "YOUR_ETC_WALLET",
        "ERGO": "YOUR_ERGO_WALLET",
        "RVN":  "YOUR_RVN_WALLET",
    },
}

# 生成 XMRig 設定檔
if miner_type == "xmrig_cpu":
    xmrig_cfg = build_xmrig_config(hw, WALLET_XMR, WORKER_NAME)
    write_xmrig_config(xmrig_cfg, INSTALL_DIR / "xmrig_config.json")

_save_config(config)
print("設定檔已儲存")

# 建立啟動腳本
LAUNCHER_BAT = INSTALL_DIR / "launcher.bat"
LAUNCHER_BAT.write_text(
    f'@echo off\n"{PYTHON_EXE}" "{MAIN_PY}" --mine\n',
    encoding="utf-8"
)

# 開機自動啟動（寫入登錄檔，不需要管理員權限）
reg_cmd = (
    f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" '
    f'/v "MiningSystem" /t REG_SZ '
    f'/d "\\"{LAUNCHER_BAT}\\"" /f'
)
r = subprocess.run(reg_cmd, shell=True, capture_output=True, text=True)
if r.returncode == 0:
    print("開機自動啟動已設定（登錄檔）")
else:
    print(f"[警告] 自動啟動設定失敗：{r.stderr.strip()}")

print("\n安裝完成！啟動挖礦系統...\n")

# 啟動完整系統（含 Dashboard）
subprocess.Popen(
    [PYTHON_EXE, str(MAIN_PY), "--mine"],
    creationflags=subprocess.CREATE_NEW_CONSOLE,
    cwd=str(BASE_DIR / "src"),
)
print("挖礦系統已啟動，請查看新開的視窗")
