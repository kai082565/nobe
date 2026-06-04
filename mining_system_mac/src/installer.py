"""
安裝模組 (macOS)
安裝到 ~/Library/Application Support/MiningSystem
開機自動啟動使用 launchd
"""

import json
import shutil
import subprocess
from pathlib import Path

INSTALL_DIR = Path.home() / "Library" / "Application Support" / "MiningSystem"
PLIST_LABEL = "com.user.miningsystem"
PLIST_PATH  = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def install(root_dir: Path, config: dict) -> None:
    """
    root_dir: mining_system_mac 根目錄（含 src/ 和 miners/）
    config:   完整設定
    """
    print(f"\n  安裝路徑：{INSTALL_DIR}")
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    _copy_src(root_dir / "src")
    _copy_miners(root_dir / "miners")
    _save_config(config)
    _create_launchd()

    print("  安裝完成\n")


def _copy_src(src: Path) -> None:
    dst = INSTALL_DIR / "src"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("  程式碼已複製")


def _copy_miners(miners_src: Path) -> None:
    dst = INSTALL_DIR / "miners"
    if miners_src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(miners_src, dst)
        xmrig = dst / "xmrig" / "xmrig"
        if xmrig.exists():
            xmrig.chmod(0o755)
        print("  礦工程式已複製")
    else:
        print(f"  [警告] 找不到礦工程式：{miners_src}")


def _save_config(config: dict) -> None:
    path = INSTALL_DIR / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print("  設定檔已儲存")


def _create_launchd() -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    python3 = shutil.which("python3") or "/usr/bin/python3"
    main_py = INSTALL_DIR / "src" / "main.py"

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>             <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python3}</string>
        <string>{main_py}</string>
        <string>--mine</string>
    </array>
    <key>RunAtLoad</key>         <true/>
    <key>KeepAlive</key>         <false/>
    <key>StandardOutPath</key>   <string>{INSTALL_DIR}/mining.log</string>
    <key>StandardErrorPath</key> <string>{INSTALL_DIR}/mining_err.log</string>
</dict>
</plist>
"""
    with open(PLIST_PATH, "w") as f:
        f.write(plist)

    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    r = subprocess.run(["launchctl", "load",   str(PLIST_PATH)],
                       capture_output=True, text=True)

    if r.returncode == 0:
        print("  開機自動啟動已設定")
    else:
        print(f"  [警告] 自動啟動設定失敗：{r.stderr.strip()}")


def uninstall() -> None:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink()
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
    print("已解除安裝")


def is_installed() -> bool:
    return (INSTALL_DIR / "config.json").exists()


def load_config() -> dict:
    path = INSTALL_DIR / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
