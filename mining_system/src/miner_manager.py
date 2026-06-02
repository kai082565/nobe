"""
礦工管理模組
啟動、監控、解析輸出算力、自動重啟、動態切幣
"""

import subprocess
import time
import threading
import re
import logging
from pathlib import Path
from configurator import build_lolminer_args, build_xmrig_config, write_xmrig_config

logger = logging.getLogger(__name__)

RESTART_DELAY_SEC = 5
MAX_RESTARTS      = 20
STABLE_THRESHOLD  = 300

# ANSI 色碼清除
_RE_ANSI     = re.compile(r'\x1b\[[0-9;]*[mGKHF]')
# 算力解析 regex（支援 XMRig 多種輸出格式）
_RE_XMRIG    = re.compile(r"speed\s+[\d./smh]+\s+([\d.]+)", re.IGNORECASE)
_RE_LOLMINER = re.compile(r"Total\s+speed[:\s]+([\d.]+)\s*(MH|GH|KH|H)", re.IGNORECASE)


class MinerManager:

    def __init__(self, install_dir: Path, config: dict, metrics=None):
        self.install_dir  = install_dir
        self.config       = config
        self.metrics      = metrics       # MiningMetrics | None
        self._process:    subprocess.Popen | None = None
        self._running     = False
        self._thread:     threading.Thread | None = None
        self._reader:     threading.Thread | None = None
        self._restarts    = 0
        self._last_start  = 0.0
        self._lock        = threading.Lock()

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(target=self._watchdog, daemon=True)
        self._thread.start()
        coin = self.config.get("coin", "?")
        mt   = self.config.get("miner_type", "?")
        logger.info(f"開始挖礦：{mt} → {coin}")
        if self.metrics:
            self.metrics.update(coin=coin, miner_type=mt, status="運行中")
            self.metrics.reset_uptime()
            self.metrics.add_log(f"開始挖礦：{mt} → {coin}")

    def stop(self) -> None:
        self._running = False
        self._kill()
        if self._thread:
            self._thread.join(timeout=15)
        if self.metrics:
            self.metrics.update(status="已停止")
        logger.info("挖礦已停止")

    def switch_coin(self, new_coin: str, new_miner_type: str, hw=None) -> None:
        with self._lock:
            old = self.config.get("coin", "?")
            if old == new_coin:
                return
            logger.info(f"切換幣種：{old} → {new_coin}")
            if self.metrics:
                self.metrics.add_log(f"切換幣種：{old} → {new_coin}")

            self.config["coin"]       = new_coin
            self.config["miner_type"] = new_miner_type
            wallet = self.config["wallets"].get(new_coin, "")
            worker = self.config.get("worker_name", "rig01")

            if new_miner_type == "lolminer":
                self.config["lolminer_args"] = build_lolminer_args(wallet, worker, new_coin)
            elif new_miner_type == "xmrig_cpu" and hw:
                xmrig_cfg = build_xmrig_config(hw, wallet, worker)
                self.config["xmrig_config"] = xmrig_cfg
                write_xmrig_config(xmrig_cfg, self.install_dir / "xmrig_config.json")

            self._restarts = 0
            self._kill()

            if self.metrics:
                self.metrics.update(
                    coin=new_coin,
                    miner_type=new_miner_type,
                    status="重啟中",
                    hashrate_str="—",
                )

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # ── 內部邏輯 ──────────────────────────────────────────────────────────

    def _build_cmd(self) -> list[str]:
        miner_type = self.config["miner_type"]

        if miner_type == "xmrig_cpu":
            exe    = self.install_dir / "miners" / "xmrig" / "xmrig.exe"
            config = self.install_dir / "xmrig_config.json"
            return [str(exe), "--config", str(config), "--no-color"]

        if miner_type == "lolminer":
            exe  = self.install_dir / "miners" / "lolminer" / "lolminer.exe"
            args = self.config.get("lolminer_args", [])
            return [str(exe)] + args

        raise ValueError(f"未知的礦工類型：{miner_type}")

    def _launch(self) -> None:
        cmd = self._build_cmd()
        logger.info(f"啟動：{' '.join(cmd[:3])} ...")
        self._process    = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._last_start = time.time()

        # 啟動 stdout 讀取執行緒
        self._reader = threading.Thread(
            target=self._read_stdout,
            args=(self._process,),
            daemon=True
        )
        self._reader.start()

        if self.metrics:
            self.metrics.update(status="運行中")

    def _read_stdout(self, proc: subprocess.Popen) -> None:
        """讀取礦工輸出，解析算力，寫入 metrics"""
        try:
            for raw in proc.stdout:
                if proc.poll() is not None:
                    break
                try:
                    line = raw.decode("utf-8", errors="replace").rstrip()
                except Exception:
                    continue

                # 去除 ANSI 色碼再解析
                clean = _RE_ANSI.sub("", line).strip()
                if not clean:
                    continue

                hr = self._parse_hashrate(clean)
                if self.metrics:
                    if hr:
                        self.metrics.update(hashrate_str=hr)
                    if any(kw in clean.lower() for kw in
                           ("speed", "mh/s", "h/s", "accepted", "pool",
                            "error", "connect", "hashrate", "total")):
                        self.metrics.add_log(clean[:120])
        except Exception as e:
            logger.debug(f"stdout 讀取結束：{e}")

    def _parse_hashrate(self, line: str) -> str | None:
        m = _RE_XMRIG.search(line)
        if m:
            return f"{float(m.group(1)):.1f} H/s"

        m = _RE_LOLMINER.search(line)
        if m:
            val  = float(m.group(1))
            unit = m.group(2).upper()
            return f"{val:.2f} {unit}/s"

        return None

    def _kill(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=10)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def _watchdog(self) -> None:
        while self._running:
            try:
                with self._lock:
                    self._launch()

                self._process.wait()

                if not self._running:
                    break

                if time.time() - self._last_start > STABLE_THRESHOLD:
                    self._restarts = 0

                self._restarts += 1

                if self.metrics:
                    self.metrics.update(
                        status="重啟中",
                        restart_count=self._restarts,
                        hashrate_str="—",
                    )
                    self.metrics.add_log(
                        f"礦工退出，{RESTART_DELAY_SEC}s 後重啟（第 {self._restarts} 次）"
                    )

                logger.warning(f"礦工退出，{RESTART_DELAY_SEC}s 後重啟（第 {self._restarts} 次）")

                if self._restarts > MAX_RESTARTS:
                    logger.error("重啟次數過多，停止")
                    if self.metrics:
                        self.metrics.update(status="已停止")
                    break

                time.sleep(RESTART_DELAY_SEC)

            except Exception as e:
                logger.error(f"看門狗例外：{e}")
                time.sleep(RESTART_DELAY_SEC)
