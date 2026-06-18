"""
自動賣幣模組
監控目標幣種價格，達到設定目標時提醒並記錄
"""
from __future__ import annotations

import time
import threading
import logging
import requests
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 300   # 每 5 分鐘查一次價格

COINGECKO_IDS = {
    "XMR":  "monero",
    "ETC":  "ethereum-classic",
    "ERGO": "ergo",
    "RVN":  "ravencoin",
}


@dataclass
class PriceAlert:
    coin: str
    target_usd: float
    triggered: bool = False


class AutoSeller:

    def __init__(self, config: dict, metrics=None):
        self.config   = config
        self.metrics  = metrics
        self._targets: dict[str, PriceAlert] = {}
        self._prices:  dict[str, float] = {}
        self._running  = False
        self._thread:  threading.Thread | None = None
        self._session  = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0"
        self._on_alert = None   # callback(coin, price, target)

        # 從 config 載入已儲存的目標
        for coin, target in config.get("sell_targets", {}).items():
            if target and float(target) > 0:
                self._targets[coin] = PriceAlert(coin=coin, target_usd=float(target))

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def set_alert_callback(self, fn) -> None:
        self._on_alert = fn

    def set_target(self, coin: str, price_usd: float) -> None:
        """設定或更新目標價格（0 = 取消）"""
        if price_usd <= 0:
            self._targets.pop(coin, None)
            logger.info(f"已取消 {coin} 目標價格")
        else:
            self._targets[coin] = PriceAlert(coin=coin, target_usd=price_usd)
            logger.info(f"已設定 {coin} 目標價格：${price_usd:.2f} USD")
            if self.metrics:
                self.metrics.add_log(f"設定目標賣出價：{coin} >= ${price_usd:.2f} USD")

    def get_targets(self) -> dict[str, float]:
        return {coin: a.target_usd for coin, a in self._targets.items()}

    def get_prices(self) -> dict[str, float]:
        return dict(self._prices)

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("自動賣幣監控已啟動")

    def stop(self) -> None:
        self._running = False

    # ── 內部邏輯 ──────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                self._fetch_prices()
                self._check_targets()
            except Exception as e:
                logger.warning(f"價格查詢失敗：{e}")
            time.sleep(CHECK_INTERVAL)

    def _fetch_prices(self) -> None:
        coins_to_check = set(COINGECKO_IDS.keys())
        if self.config.get("coin"):
            coins_to_check.add(self.config["coin"])

        ids = ",".join(
            COINGECKO_IDS[c] for c in coins_to_check if c in COINGECKO_IDS
        )
        r = self._session.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ids, "vs_currencies": "usd,twd"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        for coin, cg_id in COINGECKO_IDS.items():
            if cg_id in data:
                self._prices[coin] = data[cg_id]["usd"]

        if self.metrics:
            current = self.config.get("coin", "XMR")
            if current in self._prices:
                self.metrics.update(coin_price_usd=self._prices[current])

    def _check_targets(self) -> None:
        for coin, alert in list(self._targets.items()):
            price = self._prices.get(coin)
            if price is None:
                continue

            if price >= alert.target_usd and not alert.triggered:
                alert.triggered = True
                msg = (f"目標達成！{coin} 現價 ${price:.2f} USD"
                       f"（目標 ${alert.target_usd:.2f}）— 建議立即賣出")
                logger.info(msg)
                if self.metrics:
                    self.metrics.add_log(f"[賣幣提醒] {msg}")
                if self._on_alert:
                    self._on_alert(coin, price, alert.target_usd)

            elif price < alert.target_usd * 0.95:
                # 價格跌回目標 95% 以下，重置觸發狀態
                alert.triggered = False

    def price_summary(self) -> str:
        lines = []
        for coin, price in self._prices.items():
            target = self._targets.get(coin)
            if target:
                pct = (price / target.target_usd) * 100
                lines.append(f"{coin}: ${price:.2f} / 目標 ${target.target_usd:.2f} ({pct:.0f}%)")
            else:
                lines.append(f"{coin}: ${price:.2f}")
        return "\n".join(lines) if lines else "尚未查詢"
