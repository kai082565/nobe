"""
設定生成模組
根據硬體自動選擇最佳幣種與礦工程式，並生成設定檔
"""

from __future__ import annotations
import json
from pathlib import Path
from detector import HardwareInfo


# 礦池設定（免費，不需要註冊，用錢包地址當帳號）
POOLS = {
    "XMR": {
        "url":  "pool.supportxmr.com:3333",
        "algo": "rx/0",
        "desc": "Monero (CPU 挖礦)",
    },
    "ETC": {
        "url":  "etc.2miners.com:1010",
        "algo": "ETCHASH",
        "desc": "Ethereum Classic (GPU 4GB+)",
    },
    "ERGO": {
        "url":  "ergo.2miners.com:8888",
        "algo": "AUTOLYKOS2",
        "desc": "Ergo (GPU 3GB+)",
    },
    "RVN": {
        "url":  "rvn.2miners.com:6060",
        "algo": "KAWPOW",
        "desc": "Ravencoin (GPU 2GB+)",
    },
}


def select_miner(hw: HardwareInfo) -> tuple[str, str]:
    """
    根據硬體回傳 (miner_type, coin)
    miner_type: "xmrig_cpu" | "lolminer"
    """
from __future__ import annotations
    gpu = hw.best_gpu

    if gpu is None:
        return "xmrig_cpu", "XMR"

    if gpu.vram_mb >= 4096:
        return "lolminer", "ETC"

    if gpu.vram_mb >= 3072:
        return "lolminer", "ERGO"

    if gpu.vram_mb >= 2048:
        return "lolminer", "RVN"

    # VRAM 不足，改用 CPU
    return "xmrig_cpu", "XMR"


def build_xmrig_config(hw: HardwareInfo, wallet: str, worker: str) -> dict:
    """生成 XMRig CPU 設定檔（JSON）"""
from __future__ import annotations
    pool = POOLS["XMR"]
    return {
        "autosave": True,
        "background": False,
        "http": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 3001,
            "access-token": None,
            "restricted": True,
        },
        "cpu": {
            "enabled": True,
            "max-threads-hint": 75,
            "priority": 1,
        },
        "opencl": {"enabled": False},
        "cuda":   {"enabled": False},
        "pools": [{
            "url":       pool["url"],
            "user":      f"{wallet}.{worker}",
            "pass":      "x",
            "algo":      pool["algo"],
            "keepalive": True,
            "tls":       False,
        }],
        "print-time": 60,
        "log-file":   None,
    }


def build_lolminer_args(wallet: str, worker: str, coin: str) -> list[str]:
    """生成 lolMiner 啟動參數"""
from __future__ import annotations
    pool = POOLS[coin]
    host, port = pool["url"].split(":")
    return [
        "--algo",     pool["algo"],
        "--pool",     host,
        "--port",     port,
        "--user",     f"{wallet}.{worker}",
        "--pass",     "x",
        "--watchdog", "1",
    ]


def write_xmrig_config(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
