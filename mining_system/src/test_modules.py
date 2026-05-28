"""
系統測試腳本
不需要真實礦工程式，直接在開發機上執行即可
"""

import sys
import json
import time
import subprocess
import threading
from pathlib import Path

# 確保 src/ 在路徑中
sys.path.insert(0, str(Path(__file__).parent))

PASS = "  [OK]"
FAIL = "  [FAIL]"
SEP  = "─" * 50


def section(title: str) -> None:
    print(f"\n{'═' * 50}")
    print(f"  {title}")
    print('═' * 50)


# ── 測試 1：硬體偵測 ──────────────────────────────────────────────────────

def test_detector() -> bool:
    section("測試 1：硬體偵測")
    try:
        from detector import detect
        hw = detect()
        print(hw.summary())
        print(f"\n  best_gpu : {hw.best_gpu}")
        print(f"  has_nvidia: {hw.has_nvidia}")
        print(f"  has_amd  : {hw.has_amd}")
        print(f"{PASS} 硬體偵測正常")
        return True
    except Exception as e:
        print(f"{FAIL} 硬體偵測失敗：{e}")
        return False


# ── 測試 2：幣種選擇 & 設定生成 ──────────────────────────────────────────

def test_configurator() -> bool:
    section("測試 2：幣種選擇 & 設定生成")
    try:
        from detector import detect
        from configurator import select_miner, build_xmrig_config, build_lolminer_args

        hw = detect()
        miner_type, coin = select_miner(hw)
        print(f"  推薦方案：{miner_type}  →  {coin}")

        dummy_wallet = "44AFFq5kSiGBoZ4NMDwYtN18obc8AemS33DBLWs3H7otXft3XjrpDtQGv7SqSsaBYBb98uNbr2VBBEt7f2wfn3RVGQBEP3A"
        dummy_worker = "test_rig"

        if miner_type == "xmrig_cpu":
            cfg = build_xmrig_config(hw, dummy_wallet, dummy_worker)
            print(f"  XMRig pool : {cfg['pools'][0]['url']}")
            print(f"  XMRig user : {cfg['pools'][0]['user'][:30]}...")
        else:
            args = build_lolminer_args(dummy_wallet, dummy_worker, coin)
            print(f"  lolMiner args: {' '.join(args[:6])} ...")

        print(f"{PASS} 設定生成正常")
        return True
    except Exception as e:
        print(f"{FAIL} 設定生成失敗：{e}")
        return False


# ── 測試 3：獲利查詢 API ──────────────────────────────────────────────────

def test_profit_selector() -> bool:
    section("測試 3：獲利查詢（需要網路）")
    try:
        from detector import detect
        from profit_selector import ProfitSelector

        hw       = detect()
        selector = ProfitSelector(hw, electricity_ntd_per_kwh=4.5)

        print("  查詢中（最多等 20 秒）...")
        best = selector.best_coin_now()

        if best:
            print(f"  最佳幣種  ：{best.coin}")
            print(f"  礦工程式  ：{best.miner_type}")
            print(f"  日淨利估算：${best.daily_profit_usd:.4f} USD")
            print(f"{PASS} 獲利查詢正常")
            return True
        else:
            print(f"{FAIL} 查詢回傳空值（可能網路問題）")
            return False
    except Exception as e:
        print(f"{FAIL} 獲利查詢失敗：{e}")
        return False


# ── 測試 4：看門狗自動重啟 ────────────────────────────────────────────────

def test_watchdog() -> bool:
    section("測試 4：看門狗自動重啟")
    print("  使用假礦工測試（會故意當機 2 次，看看是否自動重啟）")

    fake_miner = Path(__file__).parent / "fake_miner.py"
    if not fake_miner.exists():
        print(f"{FAIL} 找不到 fake_miner.py")
        return False

    # 建立假的 install_dir
    import tempfile, shutil
    tmp_dir = Path(tempfile.mkdtemp())
    miners_dir = tmp_dir / "miners" / "xmrig"
    miners_dir.mkdir(parents=True)

    # 假的 xmrig.exe：其實是一個 .bat 跑 fake_miner.py
    fake_exe = miners_dir / "xmrig.exe"
    bat_content = f'@echo off\npython "{fake_miner}" --crash-after 3\n'
    bat_path = miners_dir / "xmrig.bat"
    bat_path.write_text(bat_content, encoding="utf-8")

    # xmrig_config.json（空的就好）
    (tmp_dir / "xmrig_config.json").write_text("{}", encoding="utf-8")

    try:
        from miner_manager import MinerManager

        config = {
            "miner_type": "xmrig_cpu",
            "coin": "XMR",
            "wallets": {"XMR": "test_wallet"},
            "worker_name": "test",
        }

        # 把 xmrig.exe 指向 bat（Windows 可執行 .bat）
        # 直接 patch build_cmd
        original_build = MinerManager._build_cmd

        def patched_build(self):
            return ["cmd", "/c", str(bat_path)]

        MinerManager._build_cmd = patched_build

        manager = MinerManager(tmp_dir, config)
        restart_count = [0]
        original_watchdog = manager._watchdog

        # 計算重啟次數
        original_kill = manager._kill
        def counting_launch():
            restart_count[0] += 1
            manager._launch_orig()

        manager._launch_orig = manager._launch
        manager._launch      = counting_launch

        manager.start()
        print("  假礦工啟動，等待 40 秒觀察重啟行為...")

        for i in range(8):
            time.sleep(5)
            status = "運行中" if manager.is_alive else "已停止（等待重啟）"
            print(f"  {(i+1)*5:2d}s  狀態：{status}  已啟動次數：{restart_count[0]}")

        manager.stop()
        MinerManager._build_cmd = original_build

        if restart_count[0] >= 2:
            print(f"{PASS} 看門狗正常（共重啟 {restart_count[0]-1} 次）")
            return True
        else:
            print(f"{FAIL} 看門狗未正確重啟（只啟動 {restart_count[0]} 次）")
            return False

    except Exception as e:
        print(f"{FAIL} 看門狗測試失敗：{e}")
        import traceback; traceback.print_exc()
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    print("\n" + "═" * 50)
    print("  挖礦系統測試")
    print("═" * 50)

    results = {
        "硬體偵測":    test_detector(),
        "設定生成":    test_configurator(),
        "獲利查詢":    test_profit_selector(),
        "看門狗重啟":  test_watchdog(),
    }

    section("測試結果總覽")
    all_pass = True
    for name, passed in results.items():
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  全部通過！系統可以正常運作")
    else:
        print("  部分測試失敗，請查看上方錯誤訊息")
    print()


if __name__ == "__main__":
    main()
