"""
Dashboard 視覺測試
用假資料模擬挖礦狀態，不需要礦工程式
直接執行：python test_dashboard.py
"""

import sys
import time
import random
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from metrics import metrics
from dashboard import MiningDashboard


def simulate_mining():
    """背景執行緒：模擬挖礦數據變化"""
    coins    = ["XMR", "ETC", "ERGO"]
    coin_idx = 0

    metrics.update(
        coin=coins[coin_idx],
        miner_type="xmrig_cpu",
        status="運行中",
    )
    metrics.reset_uptime()
    metrics.add_log("系統啟動")
    metrics.add_log("偵測到 CPU：AMD Ryzen 5 1400 (4核8緒)")
    metrics.add_log("偵測到 GPU：NVIDIA GeForce GT 640 (2048MB)")
    metrics.add_log(f"最佳幣種：{coins[coin_idx]}，開始挖礦")
    metrics.add_log("連線到礦池 pool.supportxmr.com:3333... OK")

    tick = 0
    while True:
        time.sleep(2)
        tick += 1

        # 模擬算力波動
        hr = random.uniform(390, 420)
        metrics.update(hashrate_str=f"{hr:.1f} H/s")

        # 每 10 秒加一條日誌
        if tick % 5 == 0:
            accepted = tick // 5
            metrics.add_log(f"Hashrate: {hr:.1f} H/s | Accepted: {accepted}")

        # 模擬第 20 秒切幣
        if tick == 10:
            metrics.add_log("偵測到更好的幣種：切換中...")
            metrics.update(status="重啟中", hashrate_str="—")
            time.sleep(2)
            coin_idx = (coin_idx + 1) % len(coins)
            metrics.update(
                coin=coins[coin_idx],
                miner_type="lolminer",
                status="運行中",
                restart_count=1,
            )
            metrics.add_log(f"已切換到 {coins[coin_idx]}，礦工重啟")
            metrics.add_log("連線到礦池 etc.2miners.com:1010... OK")

        # 模擬第 40 秒礦工當機重啟
        if tick == 20:
            metrics.add_log("[警告] 礦工意外退出，5 秒後重啟...")
            metrics.update(status="重啟中", hashrate_str="—")
            time.sleep(5)
            metrics.update(status="運行中", restart_count=2)
            metrics.add_log("礦工重啟成功")

        # 倒數
        remaining = max(0, 1800 - tick * 2)
        metrics.update(next_check_sec=remaining)


if __name__ == "__main__":
    # 背景跑模擬
    t = threading.Thread(target=simulate_mining, daemon=True)
    t.start()

    # 前景跑視窗（阻塞直到關閉）
    dash = MiningDashboard(metrics)
    print("Dashboard 啟動中...")
    dash.run_blocking()
    print("視窗已關閉")
