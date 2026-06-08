"""
即時挖礦監控視窗 (macOS)
Tab 1：監控  Tab 2：設定
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
from pathlib import Path
from installer import INSTALL_DIR

REFRESH_MS = 1000
BG         = "#1e1e2e"
BG2        = "#2a2a3e"
BG3        = "#313244"
FG         = "#cdd6f4"
FG_DIM     = "#6c7086"
GREEN      = "#a6e3a1"
YELLOW     = "#f9e2af"
RED        = "#f38ba8"
ACCENT     = "#89b4fa"
PURPLE     = "#cba6f7"
FONT_MONO  = ("Menlo", 10)
FONT_SM    = ("Helvetica Neue", 9)
FONT_LB    = ("Helvetica Neue", 10)
FONT_VAL   = ("Helvetica Neue", 10, "bold")
FONT_TITLE = ("Helvetica Neue", 13, "bold")
FONT_BIG   = ("Menlo", 20, "bold")


class MiningDashboard:

    def __init__(self, metrics, config: dict = None,
                 stop_callback=None, switch_callback=None,
                 seller=None):
        self.metrics    = metrics
        self.config     = config or {}
        self._stop_cb   = stop_callback
        self._switch_cb = switch_callback
        self.seller     = seller
        self.root:      tk.Tk | None = None
        self._last_log  = 0
        self._thread:   threading.Thread | None = None

    def run_in_background(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def run_blocking(self) -> None:
        self._run()

    def _run(self) -> None:
        self.root = tk.Tk()
        self.root.title("挖礦監控系統")
        self.root.configure(bg=BG)
        self.root.geometry("480x620")
        self.root.resizable(False, True)
        self._build_ui()
        self._refresh()
        self.root.mainloop()

    def _build_ui(self) -> None:
        r = self.root
        tk.Label(r, text="⛏  挖礦監控系統",
                 font=FONT_TITLE, bg=BG, fg=ACCENT).pack(pady=(12, 4))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook",     background=BG,  borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=FG_DIM,
                        padding=[14, 5], font=FONT_LB)
        style.map("TNotebook.Tab",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])

        self.nb = ttk.Notebook(r)
        self.nb.pack(fill="both", expand=True, padx=12, pady=4)

        self._tab_monitor  = tk.Frame(self.nb, bg=BG)
        self._tab_settings = tk.Frame(self.nb, bg=BG)
        self.nb.add(self._tab_monitor,  text="  監控  ")
        self.nb.add(self._tab_settings, text="  設定  ")

        self._build_monitor_tab(self._tab_monitor)
        self._build_settings_tab(self._tab_settings)

    # ── 監控 Tab ──────────────────────────────────────────────────────────

    def _build_monitor_tab(self, parent) -> None:
        card = tk.Frame(parent, bg=BG2)
        card.pack(fill="x", padx=8, pady=(8, 4))

        def row(label, attr):
            f = tk.Frame(card, bg=BG2)
            f.pack(fill="x", padx=12, pady=2)
            tk.Label(f, text=label, width=9, anchor="w",
                     font=FONT_LB, bg=BG2, fg=FG_DIM).pack(side="left")
            lbl = tk.Label(f, text="—", anchor="w", font=FONT_VAL, bg=BG2, fg=FG)
            lbl.pack(side="left")
            setattr(self, attr, lbl)

        sf = tk.Frame(card, bg=BG2)
        sf.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(sf, text="狀態", width=9, anchor="w",
                 font=FONT_LB, bg=BG2, fg=FG_DIM).pack(side="left")
        self.dot = tk.Label(sf, text="●", font=("Helvetica Neue", 11), bg=BG2, fg=FG_DIM)
        self.dot.pack(side="left")
        self.lbl_status = tk.Label(sf, text="—", anchor="w", font=FONT_VAL, bg=BG2, fg=FG)
        self.lbl_status.pack(side="left", padx=(4, 0))

        row("幣種",    "lbl_coin")
        row("礦工",    "lbl_miner")
        row("運行",    "lbl_uptime")
        row("重啟",    "lbl_restarts")
        row("幣價",    "lbl_price")
        row("下次選幣", "lbl_next")

        self.lbl_hashrate = tk.Label(parent, text="— H/s",
                                     font=FONT_BIG, bg=BG, fg=GREEN)
        self.lbl_hashrate.pack(pady=(8, 0))
        tk.Label(parent, text="目前算力", font=FONT_SM, bg=BG, fg=FG_DIM).pack()

        bf = tk.Frame(parent, bg=BG)
        bf.pack(pady=8)
        self._btn("停止挖礦", RED,    self._on_stop,   bf)
        self._btn("立即選幣", YELLOW, self._on_switch, bf)
        self._btn("清除日誌", FG_DIM, self._on_clear,  bf)

        tk.Label(parent, text="日誌", font=FONT_SM,
                 bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", padx=12)
        lf = tk.Frame(parent, bg=BG2)
        lf.pack(fill="both", expand=True, padx=12, pady=(2, 10))
        self.log_text = tk.Text(lf, bg=BG2, fg=FG, font=FONT_MONO,
                                bd=0, wrap="none", state="disabled",
                                selectbackground=ACCENT)
        sb = tk.Scrollbar(lf, command=self.log_text.yview, bg=BG2, troughcolor=BG2)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    # ── 設定 Tab ──────────────────────────────────────────────────────────

    def _build_settings_tab(self, parent) -> None:
        canvas    = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame     = tk.Frame(canvas, bg=BG)

        frame.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        pad = {"padx": 16, "pady": 4}

        def section(title):
            tk.Label(frame, text=title, font=("Helvetica Neue", 10, "bold"),
                     bg=BG, fg=PURPLE).pack(anchor="w", padx=16, pady=(14, 2))
            tk.Frame(frame, bg=BG3, height=1).pack(fill="x", padx=16, pady=(0, 6))

        def field(label, default="") -> tk.Entry:
            f = tk.Frame(frame, bg=BG)
            f.pack(fill="x", **pad)
            tk.Label(f, text=label, width=12, anchor="w",
                     font=FONT_LB, bg=BG, fg=FG_DIM).pack(side="left")
            e = tk.Entry(f, bg=BG2, fg=FG, insertbackground=FG,
                         relief="flat", font=FONT_MONO, width=34)
            e.insert(0, default)
            e.pack(side="left", padx=(4, 0))
            return e

        section("基本設定")
        self._e_worker = field("Worker 名稱", self.config.get("worker_name", "mac01"))
        self._e_elec   = field("電費 NT$/度",  str(self.config.get("electricity_ntd_per_kwh", 4.5)))

        section("錢包地址")
        wallets = self.config.get("wallets", {})
        self._e_wallets = {}
        for coin in ("XMR", "ETC", "ERGO", "RVN"):
            self._e_wallets[coin] = field(coin, wallets.get(coin, ""))

        section("自動賣幣（目標達到時提醒）")
        self.lbl_prices = tk.Label(frame, text="查詢中...", font=FONT_MONO,
                                   bg=BG, fg=FG_DIM, justify="left")
        self.lbl_prices.pack(anchor="w", padx=16, pady=(0, 6))

        targets = self.config.get("sell_targets", {})
        self._e_targets = {}
        for coin in ("XMR", "ETC", "ERGO", "RVN"):
            self._e_targets[coin] = field(
                f"{coin} 目標 (USD)",
                str(targets.get(coin, "")) if targets.get(coin) else ""
            )

        tk.Frame(frame, bg=BG3, height=1).pack(fill="x", padx=16, pady=12)
        self._btn_save = tk.Button(
            frame, text="儲存所有設定", command=self._on_save,
            bg=ACCENT, fg=BG, relief="flat", font=("Helvetica Neue", 10, "bold"),
            cursor="hand2", padx=20, pady=6
        )
        self._btn_save.pack(pady=(0, 16))
        self._lbl_save_msg = tk.Label(frame, text="", font=FONT_SM, bg=BG, fg=GREEN)
        self._lbl_save_msg.pack()

    # ── 刷新 ──────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        try:
            snap = self.metrics.snapshot()
            self._update_monitor(snap)
            self._update_prices()
        except Exception:
            pass
        self.root.after(REFRESH_MS, self._refresh)

    def _update_monitor(self, snap: dict) -> None:
        status    = snap["status"]
        dot_color = {"運行中": GREEN, "重啟中": YELLOW, "已停止": RED}.get(status, FG_DIM)
        self.dot.configure(fg=dot_color)
        self.lbl_status.configure(text=status)
        self.lbl_coin.configure(text=snap["coin"])
        self.lbl_miner.configure(text=snap["miner_type"])
        self.lbl_uptime.configure(text=snap["uptime_str"])
        self.lbl_restarts.configure(text=f"{snap['restart_count']} 次")

        price = snap.get("coin_price_usd", 0)
        self.lbl_price.configure(
            text=f"${price:.2f} USD" if price else "查詢中..."
        )

        ncs  = snap["next_check_sec"]
        nm, ns = divmod(max(0, ncs), 60)
        self.lbl_next.configure(text=f"{nm:02d}:{ns:02d} 後")

        hr = snap["hashrate_str"]
        self.lbl_hashrate.configure(text=hr if hr != "—" else "— H/s")

        log_lines = snap["log_lines"]
        if len(log_lines) != self._last_log:
            self._last_log = len(log_lines)
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("end", "\n".join(log_lines))
            self.log_text.configure(state="disabled")
            self.log_text.see("end")

    def _update_prices(self) -> None:
        if self.seller:
            prices  = self.seller.get_prices()
            targets = self.seller.get_targets()
            if prices:
                lines = []
                for coin, price in prices.items():
                    t = targets.get(coin)
                    if t:
                        pct = (price / t) * 100
                        lines.append(f"  {coin}: ${price:.2f}  （目標 ${t:.2f}，已達 {pct:.0f}%）")
                    else:
                        lines.append(f"  {coin}: ${price:.2f}")
                self.lbl_prices.configure(text="\n".join(lines))
            else:
                self.lbl_prices.configure(text="  查詢中...")

    # ── 按鈕 ──────────────────────────────────────────────────────────────

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
        self._last_log = 0

    def _on_save(self) -> None:
        try:
            self.config["worker_name"]              = self._e_worker.get().strip()
            self.config["electricity_ntd_per_kwh"]  = float(self._e_elec.get().strip())

            wallets = {}
            for coin, entry in self._e_wallets.items():
                val = entry.get().strip()
                if val and not val.startswith("YOUR_"):
                    wallets[coin] = val
            self.config["wallets"] = wallets

            targets = {}
            for coin, entry in self._e_targets.items():
                val = entry.get().strip()
                if val:
                    try:
                        targets[coin] = float(val)
                        if self.seller:
                            self.seller.set_target(coin, float(val))
                    except ValueError:
                        pass
            self.config["sell_targets"] = targets

            config_path = INSTALL_DIR / "config.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)

            self._lbl_save_msg.configure(text="儲存成功！", fg=GREEN)
            self.metrics.add_log("設定已儲存")
            self.root.after(3000, lambda: self._lbl_save_msg.configure(text=""))

        except Exception as e:
            self._lbl_save_msg.configure(text=f"儲存失敗：{e}", fg=RED)

    def show_alert(self, coin: str, price: float, target: float) -> None:
        if self.root:
            self.root.after(0, lambda: messagebox.showwarning(
                "賣幣提醒",
                f"{coin} 已達目標價格！\n"
                f"目前價格：${price:.2f} USD\n"
                f"目標價格：${target:.2f} USD\n\n"
                f"建議現在去交易所賣出！"
            ))

    def _btn(self, text, color, cmd, parent) -> None:
        tk.Button(
            parent, text=text, command=cmd,
            bg=BG2, fg=color, relief="flat", font=FONT_LB,
            cursor="hand2", activebackground=BG, activeforeground=color,
            padx=10, pady=4,
        ).pack(side="left", padx=5)
