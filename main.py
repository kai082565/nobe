"""
執行這個檔案即可查詢當前挖礦獲利
"""

from mining_profitability import MiningConfig, ProfitabilityChecker

# ── 在這裡填入你的礦機規格 ────────────────────────────────────────────────

config = MiningConfig(
    hashrate_mhs=360,             # 算力 (MH/s)  ← 改成你的數值
                                  #   參考：RTX 3070 約 60 MH/s，6張 = 360
                                  #         RTX 3080 約 98 MH/s
    power_watts=900,              # 整機功耗 (W) ← 含 CPU/主機板/風扇
    electricity_ntd_per_kwh=4.5,  # 台電電費 NT$/度
                                  #   一般家用約 3.5~5.5，工業用較低
)

# ── 查詢並印出報告 ────────────────────────────────────────────────────────

checker = ProfitabilityChecker(config)
checker.print_report(top_n=5)
