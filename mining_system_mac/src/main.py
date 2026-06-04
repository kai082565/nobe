"""
主程式入口 (macOS)
--install  安裝到本機
--mine     開始挖礦
--status   查看狀態
--stop     停用自動啟動
--uninstall 解除安裝
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
    print("  挖礦系統安裝程式 (macOS)")
    print("=" * 50)

    # config_user.json 在 src/ 的上一層
    root_dir      = Path(__file__).parent.parent
    user_cfg_path = root_dir / "config_user.json"

    if not user_cfg_path.exists():
        print(f"[錯誤] 找不到 {user_cfg_path}")
        print("請先編輯 config_user.json 填入錢包地址")
        return

    with open(user_cfg_path, encoding="utf-8") as f:
        user_cfg = json.load(f)

    wallets = user_cfg.get("wallets", {})
    if all(str(v).startswith("YOUR_") for v in wallets.values()):
        print("[錯誤] 請先填入你的錢包地址到 config_user.json")
        return

    print("\n正在偵測硬體...")
    hw = detect()
    print(hw.summary())

    miner_type, coin = select_miner(hw)
    wallet = wallets.get(coin) or next(iter(wallets.values()), "")
    worker = user_cfg.get("worker_name", "mac01")

    print(f"\n推薦方案：{miner_type}  挖  {coin}")
    print(f"錢包：{wallet[:12]}...")
    print(f"Worker：{worker}")

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

    print("\n開始安裝...")
    install(root_dir, config)

    if miner_type == "xmrig_cpu":
        write_xmrig_config(config["xmrig_config"], INSTALL_DIR / "xmrig_config.json")

    print("安裝完成！下次登入將自動開始挖礦")
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

    metrics.update(coin="查詢中...", miner_type="—", status="啟動中")
    metrics.add_log("系統啟動，偵測硬體完成")

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
        worker = config.get("worker_name", "mac01")
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

    manager = MinerManager(INSTALL_DIR, config, metrics=metrics)

    def on_coin_switch(new_coin: str, new_miner_type: str) -> None:
        manager.switch_coin(new_coin, new_miner_type, hw=hw)

    def on_stop() -> None:
        selector.stop()
        manager.stop()

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
        dashboard.run_blocking()
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
    from installer import PLIST_PATH
    r = subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                       capture_output=True, text=True)
    print("已停用自動啟動" if r.returncode == 0 else f"失敗：{r.stderr.strip()}")


def cmd_uninstall() -> None:
    from installer import uninstall
    confirm = input("確定要解除安裝嗎？(y/N) ").strip().lower()
    if confirm == "y":
        uninstall()


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
            print("  python3 src/main.py --install    安裝")
            print("  python3 src/main.py --mine       開始挖礦")
            print("  python3 src/main.py --status     查看狀態")
            print("  python3 src/main.py --stop       停用自動啟動")
            print("  python3 src/main.py --uninstall  解除安裝")
