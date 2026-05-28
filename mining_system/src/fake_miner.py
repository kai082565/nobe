"""
假礦工 — 僅用於測試
模擬真實礦工的輸出與行為，不會真正挖礦
用法：python fake_miner.py [--crash-after N]
"""

import time
import sys
import random

crash_after = None
for i, arg in enumerate(sys.argv):
    if arg == "--crash-after" and i + 1 < len(sys.argv):
        crash_after = int(sys.argv[i + 1])

print("[FakeMiner] 啟動中...")
time.sleep(1)
print("[FakeMiner] 連線到礦池... OK")
print("[FakeMiner] 開始挖礦")

cycles = 0
while True:
    cycles += 1
    hashrate = random.randint(380, 420)
    accepted = cycles
    print(f"[FakeMiner] Hashrate: {hashrate} H/s | Accepted: {accepted} | Uptime: {cycles * 5}s")
    time.sleep(5)

    if crash_after and cycles >= crash_after:
        print("[FakeMiner] 模擬當機！")
        sys.exit(1)
