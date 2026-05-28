"""
挖礦獲利查詢模組
輸入：算力、功耗、電費
輸出：各幣種獲利排名 + 賣/囤建議
"""

import requests
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MiningConfig:
    hashrate_mhs: float               # 算力 (MH/s)，Ethash 類幣種
    power_watts: float                # 整機功耗 (W)
    electricity_ntd_per_kwh: float    # 電費 (NT$/度)


@dataclass
class CoinResult:
    name: str
    symbol: str
    algorithm: str
    price_usd: float
    daily_revenue_ntd: float    # 日毛收益
    daily_power_cost_ntd: float # 日電費
    daily_profit_ntd: float     # 日淨利（已扣電費）
    monthly_profit_ntd: float   # 月淨利（估算）
    recommendation: str         # 賣出 / 囤幣 / 觀望 / 暫停


class ProfitabilityChecker:

    WHATTOMINE_URL = "https://whattomine.com/coins.json"
    COINGECKO_URL  = "https://api.coingecko.com/api/v3/simple/price"

    def __init__(self, config: MiningConfig):
        self.config = config
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0 MiningBot/1.0"
        self._btc_ntd: float = 3_200_000.0  # 暫存，avoid 重複請求
        self._usd_ntd: float = 32.0

    # ── 匯率 ──────────────────────────────────────────────────────────────

    def _refresh_rates(self) -> None:
        """從 CoinGecko 更新 BTC/TWD 與 USD/TWD 匯率"""
        try:
            r = self._session.get(
                self.COINGECKO_URL,
                params={"ids": "bitcoin,tether", "vs_currencies": "twd"},
                timeout=10
            )
            data = r.json()
            self._btc_ntd = data["bitcoin"]["twd"]
            self._usd_ntd = data["tether"]["twd"]
        except Exception as e:
            print(f"  [警告] 匯率更新失敗，使用預設值：{e}")

    # ── 電費 ──────────────────────────────────────────────────────────────

    def _daily_power_cost_ntd(self) -> float:
        kwh = (self.config.power_watts / 1000) * 24
        return kwh * self.config.electricity_ntd_per_kwh

    # ── 建議邏輯 ──────────────────────────────────────────────────────────

    def _recommend(self, daily_profit_ntd: float) -> str:
        if daily_profit_ntd < 0:
            return "虧損 — 建議暫停挖礦"
        elif daily_profit_ntd < 30:
            return "接近打平 — 觀望"
        elif daily_profit_ntd < 150:
            return "小幅獲利 — 建議直接賣出"
        else:
            return "獲利良好 — 可考慮部分囤幣"

    # ── WhatToMine 查詢 ───────────────────────────────────────────────────

    def _fetch_whattomine(self) -> dict:
        """
        呼叫 WhatToMine API
        回傳的 profit 欄位已是「扣除電費後的淨利（BTC/日）」
        """
        cost_usd_kwh = round(self.config.electricity_ntd_per_kwh / self._usd_ntd, 6)
        params = {
            "eth": 1,
            "factor[eth_hr]": self.config.hashrate_mhs,
            "factor[eth_p]":  self.config.power_watts,
            "cost":           cost_usd_kwh,
            "revenue":        "current",
            "commit":         "Calculate",
        }
        r = self._session.get(self.WHATTOMINE_URL, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("coins", {})

    # ── 主查詢 ────────────────────────────────────────────────────────────

    def get_top_coins(self, top_n: int = 5) -> list[CoinResult]:
        self._refresh_rates()

        power_cost_ntd = self._daily_power_cost_ntd()
        coins_raw = self._fetch_whattomine()
        results: list[CoinResult] = []

        for name, info in coins_raw.items():
            try:
                # profit = 淨利 (BTC/日)；revenue = 毛收益 (BTC/日)
                profit_btc  = float(info.get("profit", 0) or 0)
                revenue_btc = float(info.get("revenue", 0) or 0)

                profit_ntd  = profit_btc  * self._btc_ntd
                revenue_ntd = revenue_btc * self._btc_ntd

                # 幣價（exchange_rate 可能是 BTC 或 USD）
                exchange_rate = float(info.get("exchange_rate", 0) or 0)
                curr = info.get("exchange_rate_curr", "BTC")
                price_usd = (exchange_rate * self._btc_ntd / self._usd_ntd
                             if curr == "BTC" else exchange_rate)

                results.append(CoinResult(
                    name=name,
                    symbol=info.get("tag", name),
                    algorithm=info.get("algorithm", ""),
                    price_usd=price_usd,
                    daily_revenue_ntd=revenue_ntd,
                    daily_power_cost_ntd=power_cost_ntd,
                    daily_profit_ntd=profit_ntd,
                    monthly_profit_ntd=profit_ntd * 30,
                    recommendation=self._recommend(profit_ntd),
                ))
            except (ValueError, TypeError, KeyError):
                continue

        results.sort(key=lambda x: x.daily_profit_ntd, reverse=True)
        return results[:top_n]

    # ── 報告輸出 ──────────────────────────────────────────────────────────

    def print_report(self, top_n: int = 5) -> list[CoinResult]:
        print(f"\n{'═'*60}")
        print(f"  挖礦獲利分析報告  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}")
        print(f"  算力   {self.config.hashrate_mhs} MH/s")
        print(f"  功耗   {self.config.power_watts} W")
        print(f"  電費   NT$ {self.config.electricity_ntd_per_kwh}/度")

        coins = self.get_top_coins(top_n)  # refresh_rates 在裡面已執行

        print(f"  匯率   1 USD = NT$ {self._usd_ntd:.1f}"
              f"   1 BTC = NT$ {self._btc_ntd:,.0f}")
        print(f"  每日電費  NT$ {self._daily_power_cost_ntd():.1f}")
        print(f"{'─'*60}")

        for i, c in enumerate(coins, 1):
            sign = "▲" if c.daily_profit_ntd >= 0 else "▼"
            print(f"\n  #{i}  {c.name} ({c.symbol})  [{c.algorithm}]")
            print(f"      幣價       USD {c.price_usd:>10.4f}")
            print(f"      日毛收益   NT$ {c.daily_revenue_ntd:>+10.1f}")
            print(f"      日電費     NT$ {c.daily_power_cost_ntd:>10.1f}")
            print(f"      日淨利     NT$ {c.daily_profit_ntd:>+10.1f}  {sign}")
            print(f"      月估利     NT$ {c.monthly_profit_ntd:>+10.1f}")
            print(f"      建議       {c.recommendation}")

        print(f"\n{'═'*60}\n")
        return coins
