"""
安裝模組
把 USB 上的系統複製到本機，並設定開機自動啟動
"""

import json
import shutil
import subprocess
from pathlib import Path

INSTALL_DIR = Path.home() / "AppData" / "Roaming" / "MiningSystem"
TASK_NAME   = "MiningSystemAutoStart"


def install(usb_miners_dir: Path, config: dict) -> None:
    """
    usb_miners_dir: USB 上的 miners/ 資料夾路徑
    config:         包含 miner_type、coin、wallets、lolminer_args 等
    """
    print(f"\n  安裝路徑：{INSTALL_DIR}")
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    _copy_miners(usb_miners_dir)
    _save_config(config)
    _create_task()

    print("  安裝完成\n")


def _copy_miners(usb_miners_dir: Path) -> None:
    dst = INSTALL_DIR / "miners"
    if usb_miners_dir.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(usb_miners_dir, dst)
        print("  礦工程式已複製")
    else:
        print(f"  [警告] 找不到礦工程式資料夾：{usb_miners_dir}")


def _save_config(config: dict) -> None:
    path = INSTALL_DIR / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print("  設定檔已儲存")


def _create_task() -> None:
    """建立 Windows 排程工作，登入後自動啟動挖礦"""
    launcher = INSTALL_DIR / "launcher.exe"

    ps = f"""
$action  = New-ScheduledTaskAction -Execute '{launcher}' -Argument '--mine'
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME -RunLevel Highest
Register-ScheduledTask `
    -TaskName '{TASK_NAME}' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null
"""
    r = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        print("  開機自動啟動已設定")
    else:
        print(f"  [警告] 自動啟動設定失敗：{r.stderr.strip()}")


def uninstall() -> None:
    subprocess.run(
        ["powershell", "-Command",
         f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false"],
        capture_output=True
    )
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
    print("已解除安裝")


def is_installed() -> bool:
    return (INSTALL_DIR / "config.json").exists()


def load_config() -> dict:
    path = INSTALL_DIR / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
