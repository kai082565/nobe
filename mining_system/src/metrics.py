"""
共享監控數據
執行緒安全，礦工管理器寫入，Dashboard 讀取
"""

import time
import threading
from dataclasses import dataclass, field


@dataclass
class MiningMetrics:
    coin:            str = "—"
    miner_type:      str = "—"
    status:          str = "未啟動"   # 未啟動 | 運行中 | 重啟中 | 已停止
    hashrate_str:    str = "—"
    restart_count:   int = 0
    next_check_sec:  int = 0          # 距離下次選幣的秒數
    coin_price_usd:  float = 0.0     # 目前幣價
    _log:            list = field(default_factory=list, repr=False)
    _log_seq:        int = field(default=0, repr=False)   # 單調遞增，避免日誌滿 200 筆後長度卡住不變
    _lock:           threading.Lock = field(default_factory=threading.Lock, repr=False)
    _mine_start:     float = field(default_factory=time.time, repr=False)

    MAX_LOG = 200

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if k.startswith("_"):
                    continue
                if hasattr(self, k):
                    setattr(self, k, v)

    def reset_uptime(self) -> None:
        with self._lock:
            self._mine_start = time.time()

    def add_log(self, line: str) -> None:
        ts = time.strftime("%H:%M:%S")
        entry = f"{ts}  {line}"
        with self._lock:
            self._log.append(entry)
            self._log_seq += 1
            if len(self._log) > self.MAX_LOG:
                self._log.pop(0)

    def snapshot(self) -> dict:
        with self._lock:
            uptime = int(time.time() - self._mine_start)
            h, rem = divmod(uptime, 3600)
            m, s   = divmod(rem, 60)
            return {
                "coin":           self.coin,
                "miner_type":     self.miner_type,
                "status":         self.status,
                "hashrate_str":   self.hashrate_str,
                "uptime_str":     f"{h:02d}:{m:02d}:{s:02d}",
                "restart_count":  self.restart_count,
                "next_check_sec": self.next_check_sec,
                "coin_price_usd": self.coin_price_usd,
                "log_lines":      list(self._log),
                "log_seq":        self._log_seq,
            }


# 全域單例，讓所有模組共用
metrics = MiningMetrics()
