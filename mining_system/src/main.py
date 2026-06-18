"""
主程式入口
--install  從 USB 安裝到本機
--mine     開始挖礦（由排程工作呼叫）
--status   查看目前狀態
--stop     停止排程工作（暫時停止挖礦）
"""

import sys
import json
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def cmd_install() -> None:
    from detector import detect
    from configurator import select_miner, build_xmrig_config, build_lolminer_args, write_xmrig_config
    from installer import install, INSTALL_DIR

    print("=" * 50)
    print("  挖礦系統安裝程式")
    print("=" * 50)

    # USB 根目錄 = 本執行檔的上兩層（exe 在 MiningSystem/ 下）
    usb_root = Path(sys.executable).parent.parent

    # 讀取使用者設定
    user_cfg_path = usb_root / "config_user.json"
    if not user_cfg_path.exists():
        print(f"[錯誤] 找不到 {user_cfg_path}")
        print("請確認 USB 根目錄有 config_user.json")
        _pause()
        return

    with open(user_cfg_path, encoding="utf-8") as f:
        user_cfg = json.load(f)

    wallets = user_cfg.get("wallets", {})
    if all(str(v).startswith("YOUR_") for v in wallets.values()):
        print("[錯誤] 請先填入你的錢包地址到 config_user.json")
        _pause()
        return

    # 偵測硬體
    print("\n正在偵測硬體...")
    hw = detect()
    print(hw.summary())

    # 選擇礦工與幣種
    miner_type, coin = select_miner(hw)
    wallet = wallets.get(coin) or next(iter(wallets.values()), "")
    worker = user_cfg.get("worker_name", "rig01")

    print(f"\n推薦方案：{miner_type}  挖  {coin}")
    print(f"錢包：{wallet[:12]}...")
    print(f"Worker：{worker}")

    # 建立完整設定
    config = {
        "miner_type": miner_type,
        "coin":       coin,
        "worker_name": worker,
        "wallets":    wallets,
        "electricity_ntd_per_kwh": user_cfg.get("electricity_ntd_per_kwh", 4.5),
    }

    if miner_type == "lolminer":
        config["lolminer_args"] = build_lolminer_args(wallet, worker, coin)
    else:
        xmrig_cfg = build_xmrig_config(hw, wallet, worker)
        config["xmrig_config"] = xmrig_cfg

    # 安裝
    print("\n開始安裝...")
    usb_miners = usb_root / "MiningSystem" / "miners"
    install(usb_miners, config)

    # 寫入 XMRig 獨立設定檔
    if miner_type == "xmrig_cpu":
        write_xmrig_config(config["xmrig_config"], INSTALL_DIR / "xmrig_config.json")

    # 複製 launcher.exe 到安裝目錄
    launcher_src = usb_root / "MiningSystem" / "launcher.exe"
    if launcher_src.exists():
        import shutil
        shutil.copy2(launcher_src, INSTALL_DIR / "launcher.exe")

    print("安裝完成！下次開機將自動開始挖礦")
    print("現在立即啟動挖礦...\n")
    cmd_mine()


def cmd_mine(show_gui: bool = True) -> None:
    from installer import is_installed, load_config, INSTALL_DIR
    from miner_manager import MinerManager
    from profit_selector import ProfitSelector
    from detector import detect
    from metrics import metrics
    from dashboard import MiningDashboard
    from auto_seller import AutoSeller

    if not is_installed():
        logger.error("尚未安裝，請先執行 --install")
        return

    config = load_config()
    hw     = detect()

    # 初始化 metrics
    metrics.update(coin="查詢中...", miner_type="—", status="啟動中")
    metrics.add_log("系統啟動，偵測硬體完成")

    # 查詢最佳幣種
    selector = ProfitSelector(hw, config.get("electricity_ntd_per_kwh", 4.5))
    metrics.add_log("查詢最佳幣種...")
    best = selector.best_coin_now()

    if best:
        msg = f"最佳幣種：{best.coin}（日淨利 ${best.daily_profit_usd:.4f} USD）"
        logger.info(msg)
        metrics.add_log(msg)
        config["miner_type"] = best.miner_type
        config["coin"]       = best.coin
        wallet = config["wallets"].get(best.coin, "")
        worker = config.get("worker_name", "rig01")
        if best.miner_type == "lolminer":
            from configurator import build_lolminer_args
            config["lolminer_args"] = build_lolminer_args(wallet, worker, best.coin)
        else:
            from configurator import build_xmrig_config, write_xmrig_config
            xmrig_cfg = build_xmrig_config(hw, wallet, worker)
            config["xmrig_config"] = xmrig_cfg
            write_xmrig_config(xmrig_cfg, INSTALL_DIR / "xmrig_config.json")
    else:
        logger.warning("獲利查詢失敗，使用上次設定")
        metrics.add_log("獲利查詢失敗，使用上次設定")

    # 建立礦工管理器（傳入 metrics）
    manager = MinerManager(INSTALL_DIR, config, metrics=metrics)

    def on_coin_switch(new_coin: str, new_miner_type: str) -> None:
        manager.switch_coin(new_coin, new_miner_type, hw=hw)

    def on_stop() -> None:
        selector.stop()
        manager.stop()

    # 讓 profit_selector 每秒倒數更新 next_check_sec
    import threading as _threading
    def _countdown():
        remaining = 1800
        while True:
            metrics.update(next_check_sec=remaining)
            time.sleep(1)
            remaining -= 1
            if remaining <= 0:
                remaining = 1800
    _threading.Thread(target=_countdown, daemon=True).start()

    # 自動賣幣監控
    seller = AutoSeller(config, metrics=metrics)
    seller.start()

    selector.set_switch_callback(on_coin_switch)
    manager.start()
    selector.start_auto_check()

    if show_gui:
        dashboard = MiningDashboard(
            metrics,
            config=config,
            stop_callback=on_stop,
            switch_callback=lambda: on_coin_switch(
                *((best.coin, best.miner_type) if best else (config["coin"], config["miner_type"]))
            ),
            seller=seller,
        )
        seller.set_alert_callback(dashboard.show_alert)
        dashboard.run_blocking()   # 阻塞直到視窗關閉
    else:
        try:
            while True:
                time.sleep(60)
                logger.info(f"礦工：{config['coin']}  {'運行中' if manager.is_alive else '停止'}")
        except KeyboardInterrupt:
            pass

    selector.stop()
    manager.stop()


def cmd_status() -> None:
    from installer import is_installed, load_config, INSTALL_DIR

    if not is_installed():
        print("尚未安裝")
        return

    config = load_config()
    print(f"\n  安裝路徑：{INSTALL_DIR}")
    print(f"  挖礦程式：{config['miner_type']}")
    print(f"  幣種    ：{config['coin']}")
    print(f"  Worker  ：{config.get('worker_name', '-')}")
    print(f"  電費    ：NT$ {config.get('electricity_ntd_per_kwh', '-')}/度\n")


def cmd_stop() -> None:
    import subprocess
    from installer import TASK_NAME
    r = subprocess.run(
        ["powershell", "-Command", f"Disable-ScheduledTask -TaskName '{TASK_NAME}'"],
        capture_output=True, text=True
    )
    print("已停用自動啟動" if r.returncode == 0 else f"失敗：{r.stderr.strip()}")


def cmd_uninstall() -> None:
    from installer import uninstall
    confirm = input("確定要解除安裝嗎？(y/N) ").strip().lower()
    if confirm == "y":
        uninstall()


def _pause() -> None:
    input("\n按 Enter 結束...")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--install" in args:
        cmd_install()
    elif "--mine" in args:
        cmd_mine()
    elif "--status" in args:
        cmd_status()
    elif "--stop" in args:
        cmd_stop()
    elif "--uninstall" in args:
        cmd_uninstall()
    else:
        from installer import is_installed
        if is_installed():
            cmd_mine()
        else:
            print("用法：")
            print("  launcher.exe --install    從 USB 安裝")
            print("  launcher.exe --mine       開始挖礦")
            print("  launcher.exe --status     查看狀態")
            print("  launcher.exe --stop       停用自動啟動")
            print("  launcher.exe --uninstall  解除安裝")
