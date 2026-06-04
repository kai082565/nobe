"""
獲利自動選幣模組
定期查詢 WhatToMine，選出目前最划算的幣種
"""

import requests
import logging
import time
import threading
from dataclasses import dataclass
from detector import HardwareInfo

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 1800   # 每 30 分鐘重新查一次
SWITCH_THRESHOLD   = 0.10   # 新幣獲利比目前幣高 10% 才切換（避免頻繁切換）

WHATTOMINE_URL = "https://whattomine.com/coins.json"
COINGECKO_URL  = "https://api.coingecko.com/api/v3/simple/price"


@dataclass
class CoinProfit:
    coin: str           # "ETC" | "ERGO" | "RVN" | "XMR"
    algo: str
    daily_profit_usd: float
    miner_type: str     # "lolminer" | "xmrig_cpu"


class ProfitSelector:

    # 我們支援的幣種（必須在 config_user.json 有填錢包地址）
    SUPPORTED_GPU_COINS = {
        "ETC":  {"algo": "ETCHASH",    "min_vram_mb": 4096},
        "ERGO": {"algo": "AUTOLYKOS2", "min_vram_mb": 3072},
        "RVN":  {"algo": "KAWPOW",     "min_vram_mb": 2048},
    }

    def __init__(self, hw: HardwareInfo, electricity_ntd_per_kwh: float):
        self.hw       = hw
        self.elec_ntd = electricity_ntd_per_kwh
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0"
        self._usd_ntd: float = 32.0
        self._current_coin: str | None = None
        self._on_switch = None        # callback(new_coin, new_miner_type)
        self._running   = False
        self._thread: threading.Thread | None = None

    def set_switch_callback(self, fn) -> None:
        """當需要切換幣種時呼叫此 callback"""
        self._on_switch = fn

    def start_auto_check(self) -> None:
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── 外部查詢 ──────────────────────────────────────────────────────────

    def best_coin_now(self) -> CoinProfit | None:
        """立即查詢並回傳目前最佳幣種"""
        try:
            self._refresh_usd_ntd()
            return self._query_best()
        except Exception as e:
            logger.warning(f"獲利查詢失敗：{e}")
            return None

    # ── 內部邏輯 ──────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                best = self.best_coin_now()
                if best:
                    logger.info(f"目前最佳：{best.coin}  日淨利 ${best.daily_profit_usd:.2f} USD")
                    self._maybe_switch(best)
            except Exception as e:
                logger.warning(f"自動選幣例外：{e}")
            time.sleep(CHECK_INTERVAL_SEC)

    def _maybe_switch(self, best: CoinProfit) -> None:
        if self._current_coin is None:
            self._current_coin = best.coin
            if self._on_switch:
                self._on_switch(best.coin, best.miner_type)
            return

        if best.coin == self._current_coin:
            return

        # 只有新幣獲利超過門檻才切換
        current_profit = self._get_profit_for(self._current_coin)
        if current_profit and current_profit > 0:
            improvement = (best.daily_profit_usd - current_profit) / current_profit
            if improvement < SWITCH_THRESHOLD:
                logger.info(f"改善幅度 {improvement:.1%} < {SWITCH_THRESHOLD:.0%}，維持挖 {self._current_coin}")
                return

        logger.info(f"切換幣種：{self._current_coin} → {best.coin}")
        self._current_coin = best.coin
        if self._on_switch:
            self._on_switch(best.coin, best.miner_type)

    def _refresh_usd_ntd(self) -> None:
        try:
            r = self._session.get(
                COINGECKO_URL,
                params={"ids": "tether", "vs_currencies": "twd"},
                timeout=8
            )
            self._usd_ntd = r.json()["tether"]["twd"]
        except Exception:
            pass

    def _query_best(self) -> CoinProfit | None:
        gpu = self.hw.best_gpu
        cost_usd = self.elec_ntd / self._usd_ntd

        if gpu and gpu.vram_mb >= 2048:
            return self._query_gpu_best(gpu.vram_mb, cost_usd)
        else:
            return self._cpu_profit(cost_usd)

    def _query_gpu_best(self, vram_mb: int, cost_usd_kwh: float) -> CoinProfit | None:
        eligible = {
            k: v for k, v in self.SUPPORTED_GPU_COINS.items()
            if vram_mb >= v["min_vram_mb"]
        }
        if not eligible:
            return self._cpu_profit(cost_usd_kwh)

        params = {
            "eth": 1,
            "factor[eth_hr]": max(1, self.hw.best_gpu.vram_mb // 100),  # 粗估算力
            "factor[eth_p]":  self.hw.power_estimate_watts(),
            "cost":           round(cost_usd_kwh, 6),
            "revenue":        "current",
        }
        r = self._session.get(WHATTOMINE_URL, params=params, timeout=15)
        r.raise_for_status()
        coins_raw = r.json().get("coins", {})

        # 幣名對應表（WhatToMine 使用全名）
        name_map = {
            "Ethereum Classic": "ETC",
            "Ergo":             "ERGO",
            "Ravencoin":        "RVN",
        }

        best: CoinProfit | None = None
        for full_name, symbol in name_map.items():
            if symbol not in eligible:
                continue
            info = coins_raw.get(full_name)
            if not info:
                continue
            try:
                profit_btc = float(info.get("profit", 0) or 0)
                btc_usd = self._get_btc_usd()
                profit_usd = profit_btc * btc_usd
                if best is None or profit_usd > best.daily_profit_usd:
                    best = CoinProfit(
                        coin=symbol,
                        algo=self.SUPPORTED_GPU_COINS[symbol]["algo"],
                        daily_profit_usd=profit_usd,
                        miner_type="lolminer",
                    )
            except (ValueError, TypeError):
                continue

        return best or self._cpu_profit(cost_usd_kwh)

    def _cpu_profit(self, cost_usd_kwh: float) -> CoinProfit:
        # CPU 挖 XMR，獲利估算（約 400 H/s Ryzen 5 1400）
        hashrate = self.hw.cpu_threads * 50   # 粗估每緒 50 H/s
        xmr_usd_per_day = hashrate * 0.000001  # 非常粗估，實際看礦池
        power_w = self.hw.cpu_cores * 15       # 粗估每核 15W
        cost_per_day = (power_w / 1000) * 24 * cost_usd_kwh
        return CoinProfit(
            coin="XMR",
            algo="rx/0",
            daily_profit_usd=max(0.0, xmr_usd_per_day - cost_per_day),
            miner_type="xmrig_cpu",
        )

    def _get_profit_for(self, coin: str) -> float | None:
        best = self.best_coin_now()
        if best and best.coin == coin:
            return best.daily_profit_usd
        return None

    def _get_btc_usd(self) -> float:
        try:
            r = self._session.get(
                COINGECKO_URL,
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=8
            )
            return r.json()["bitcoin"]["usd"]
        except Exception:
            return 60000.0


# 讓 HardwareInfo 支援功耗估算
def _power_estimate(self) -> int:
    """粗估整機功耗（W）"""
    base = 80  # 主機板 + CPU 待機
    if self.cpu_cores:
        base += self.cpu_cores * 15
    for gpu in self.gpus:
        if "4090" in gpu.name:
            base += 450
        elif "4080" in gpu.name:
            base += 320
        elif "3080" in gpu.name:
            base += 320
        elif "3070" in gpu.name:
            base += 220
        elif "3060" in gpu.name:
            base += 170
        else:
            base += 150   # 其他顯卡預設
    return base

# 動態注入到 HardwareInfo
HardwareInfo.power_estimate_watts = _power_estimate
