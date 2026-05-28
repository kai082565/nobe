"""
即時挖礦監控視窗
tkinter 內建，不需額外安裝
"""

import tkinter as tk
from tkinter import font as tkfont
import threading
import time

REFRESH_MS  = 1000   # 每秒更新一次
BG          = "#1e1e2e"
BG2         = "#2a2a3e"
FG          = "#cdd6f4"
FG_DIM      = "#6c7086"
GREEN       = "#a6e3a1"
YELLOW      = "#f9e2af"
RED         = "#f38ba8"
ACCENT      = "#89b4fa"
FONT_MONO   = ("Consolas", 10)
FONT_LABEL  = ("Segoe UI", 10)
FONT_VALUE  = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_BIG    = ("Consolas", 22, "bold")


class MiningDashboard:

    def __init__(self, metrics, stop_callback=None, switch_callback=None):
        """
        metrics:         MiningMetrics 實例
        stop_callback:   按「停止挖礦」時呼叫
        switch_callback: 按「立即選幣」時呼叫
        """
        self.metrics         = metrics
        self._stop_cb        = stop_callback
        self._switch_cb      = switch_callback
        self.root:           tk.Tk | None = None
        self._thread:        threading.Thread | None = None
        self._last_log_count = 0

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def run_in_background(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def run_blocking(self) -> None:
        self._run()

    # ── 視窗建立 ──────────────────────────────────────────────────────────

    def _run(self) -> None:
        self.root = tk.Tk()
        self.root.title("挖礦監控")
        self.root.configure(bg=BG)
        self.root.geometry("460x560")
        self.root.resizable(False, True)
        self._build_ui()
        self._refresh()
        self.root.mainloop()

    def _build_ui(self) -> None:
        r = self.root
        pad = {"padx": 16, "pady": 4}

        # ── 標題 ──────────────────────────────────────────────────────────
        tk.Label(r, text="⛏  挖礦監控系統",
                 font=FONT_TITLE, bg=BG, fg=ACCENT).pack(pady=(14, 6))

        # ── 狀態卡片 ──────────────────────────────────────────────────────
        card = tk.Frame(r, bg=BG2, bd=0)
        card.pack(fill="x", **pad)

        def row(label, var_name):
            f = tk.Frame(card, bg=BG2)
            f.pack(fill="x", padx=12, pady=3)
            tk.Label(f, text=label, width=8, anchor="w",
                     font=FONT_LABEL, bg=BG2, fg=FG_DIM).pack(side="left")
            lbl = tk.Label(f, text="—", anchor="w",
                           font=FONT_VALUE, bg=BG2, fg=FG)
            lbl.pack(side="left")
            setattr(self, var_name, lbl)

        # 狀態那行特別處理（有顏色圓點）
        sf = tk.Frame(card, bg=BG2)
        sf.pack(fill="x", padx=12, pady=(10, 3))
        tk.Label(sf, text="狀態", width=8, anchor="w",
                 font=FONT_LABEL, bg=BG2, fg=FG_DIM).pack(side="left")
        self.dot = tk.Label(sf, text="●", font=("Segoe UI", 11),
                            bg=BG2, fg=FG_DIM)
        self.dot.pack(side="left")
        self.lbl_status = tk.Label(sf, text="—", anchor="w",
                                   font=FONT_VALUE, bg=BG2, fg=FG)
        self.lbl_status.pack(side="left", padx=(4, 0))

        row("幣種",    "lbl_coin")
        row("礦工",    "lbl_miner")
        row("運行",    "lbl_uptime")
        row("重啟",    "lbl_restarts")
        row("下次選幣", "lbl_next")

        # ── 算力大字 ──────────────────────────────────────────────────────
        self.lbl_hashrate = tk.Label(r, text="— H/s",
                                     font=FONT_BIG, bg=BG, fg=GREEN)
        self.lbl_hashrate.pack(pady=(10, 2))
        tk.Label(r, text="目前算力", font=FONT_LABEL,
                 bg=BG, fg=FG_DIM).pack()

        # ── 按鈕 ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(r, bg=BG)
        btn_frame.pack(pady=10)
        self._btn("停止挖礦", RED,     self._on_stop,   btn_frame)
        self._btn("立即選幣", YELLOW,  self._on_switch, btn_frame)
        self._btn("清除日誌", FG_DIM,  self._on_clear,  btn_frame)

        # ── 日誌區 ────────────────────────────────────────────────────────
        tk.Label(r, text="日誌", font=FONT_LABEL,
                 bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", padx=16)

        log_frame = tk.Frame(r, bg=BG2)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(2, 12))

        self.log_text = tk.Text(
            log_frame,
            bg=BG2, fg=FG, font=FONT_MONO,
            bd=0, wrap="none", state="disabled",
            selectbackground=ACCENT,
        )
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview,
                                  bg=BG2, troughcolor=BG2)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _btn(self, text, color, cmd, parent) -> None:
        tk.Button(
            parent, text=text, command=cmd,
            bg=BG2, fg=color, relief="flat",
            font=FONT_LABEL, cursor="hand2",
            activebackground=BG, activeforeground=color,
            padx=12, pady=4,
        ).pack(side="left", padx=6)

    # ── 刷新邏輯 ──────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        try:
            snap = self.metrics.snapshot()
            self._update_widgets(snap)
        except Exception:
            pass
        self.root.after(REFRESH_MS, self._refresh)

    def _update_widgets(self, snap: dict) -> None:
        status = snap["status"]

        # 狀態圓點顏色
        dot_color = {
            "運行中": GREEN,
            "重啟中": YELLOW,
            "已停止": RED,
        }.get(status, FG_DIM)
        self.dot.configure(fg=dot_color)
        self.lbl_status.configure(text=status)

        self.lbl_coin.configure(text=snap["coin"])
        self.lbl_miner.configure(text=snap["miner_type"])
        self.lbl_uptime.configure(text=snap["uptime_str"])
        self.lbl_restarts.configure(text=f"{snap['restart_count']} 次")

        ncs = snap["next_check_sec"]
        nm, ns = divmod(max(0, ncs), 60)
        self.lbl_next.configure(text=f"{nm:02d}:{ns:02d} 後")

        # 算力大字
        hr = snap["hashrate_str"]
        self.lbl_hashrate.configure(text=hr if hr != "—" else "— H/s")

        # 日誌（只在有新行時更新，避免閃爍）
        log_lines = snap["log_lines"]
        if len(log_lines) != self._last_log_count:
            self._last_log_count = len(log_lines)
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("end", "\n".join(log_lines))
            self.log_text.configure(state="disabled")
            self.log_text.see("end")

    # ── 按鈕回呼 ──────────────────────────────────────────────────────────

    def _on_stop(self) -> None:
        if self._stop_cb:
            self._stop_cb()
        self.metrics.update(status="已停止")

    def _on_switch(self) -> None:
        if self._switch_cb:
            self._switch_cb()

    def _on_clear(self) -> None:
        with self.metrics._lock:
            self.metrics._log.clear()
        self._last_log_count = 0
