"""
Adjudication Dashboard GUI — always-on-top, right-edge of screen.
Dark navy #1a1a2e, purple accent #6c5ce7.
All automation runs in daemon threads.
"""
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import pywinauto.keyboard as kb

from automation import adjudicator, watcher, window_utils
from utils import logger
from vision import client as vision_client

# ── Colours ──────────────────────────────────────────────────────────────────
BG = "#1a1a2e"
ACCENT = "#6c5ce7"
FG = "#e0e0f0"
BTN_ARM = "#00b894"
BTN_DISARM = "#d63031"
BTN_FG = "#ffffff"
STATUS_GREY = "#888888"
STATUS_BLUE = "#4fc3f7"
STATUS_AMBER = "#ffb300"
STATUS_GREEN = "#00e676"

# ── Window geometry ───────────────────────────────────────────────────────────
WIN_WIDTH = 280
WIN_HEIGHT = 480
RIGHT_MARGIN = 8


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()

        self._armed = False
        self._plan = tk.StringVar(value="odb")
        self._stop_flag = threading.Event()
        self._blink_job = None
        self._blink_state = False
        self._status_dot_color = STATUS_GREY

        self._build_ui()
        self._position_window()
        self.after(100, self._startup_server_check)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.title("Adjudication")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.wm_attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        bold = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        normal = tkfont.Font(family="Segoe UI", size=9)
        small = tkfont.Font(family="Segoe UI", size=8)

        # Title
        tk.Label(self, text="Adjudication Dashboard", bg=BG, fg=ACCENT,
                 font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
                 pady=8).pack(fill="x")

        # Server status
        self._server_frame = tk.Frame(self, bg=BG)
        self._server_frame.pack(fill="x", padx=12, pady=(0, 6))
        self._server_dot = tk.Label(self._server_frame, text="●", bg=BG,
                                    fg=STATUS_GREY, font=bold)
        self._server_dot.pack(side="left")
        self._server_label = tk.Label(self._server_frame, text="Checking server…",
                                      bg=BG, fg=FG, font=normal)
        self._server_label.pack(side="left", padx=(4, 0))

        # Separator
        tk.Frame(self, bg=ACCENT, height=1).pack(fill="x", padx=12, pady=4)

        # Drug plan radio buttons
        tk.Label(self, text="Drug Plan", bg=BG, fg=FG, font=bold,
                 anchor="w").pack(fill="x", padx=14)

        plan_frame = tk.Frame(self, bg=BG)
        plan_frame.pack(fill="x", padx=14, pady=(2, 8))

        plans = [("ODB", "odb"), ("BC", "bc"), ("CS", "cs"),
                 ("GS", "gs"), ("Assure", "ahe"), ("Cash", "cash")]
        for i, (label, value) in enumerate(plans):
            row, col = divmod(i, 2)
            rb = tk.Radiobutton(
                plan_frame, text=label, variable=self._plan, value=value,
                bg=BG, fg=FG, selectcolor=ACCENT, activebackground=BG,
                activeforeground=FG, font=normal, anchor="w",
            )
            rb.grid(row=row, column=col, sticky="w", padx=(0, 16), pady=1)

        # Separator
        tk.Frame(self, bg=ACCENT, height=1).pack(fill="x", padx=12, pady=4)

        # Status indicator row
        status_row = tk.Frame(self, bg=BG)
        status_row.pack(fill="x", padx=12, pady=(4, 0))
        self._status_dot_label = tk.Label(status_row, text="●", bg=BG,
                                          fg=STATUS_GREY, font=bold)
        self._status_dot_label.pack(side="left")
        self._status_text = tk.Label(status_row, text="Idle", bg=BG, fg=FG,
                                     font=normal)
        self._status_text.pack(side="left", padx=(4, 0))

        # Status detail
        self._detail_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._detail_var, bg=BG, fg=STATUS_GREY,
                 font=small, wraplength=WIN_WIDTH - 24, justify="left",
                 anchor="w").pack(fill="x", padx=14, pady=(2, 8))

        # ARM / DISARM buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=12, pady=4)

        self._arm_btn = tk.Button(
            btn_frame, text="ARM", bg=BTN_ARM, fg=BTN_FG,
            font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
            relief="flat", cursor="hand2", width=8,
            command=self._on_arm,
        )
        self._arm_btn.pack(side="left", padx=(0, 8))

        self._disarm_btn = tk.Button(
            btn_frame, text="DISARM", bg=BTN_DISARM, fg=BTN_FG,
            font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
            relief="flat", cursor="hand2", width=8,
            command=self._on_disarm, state="disabled",
        )
        self._disarm_btn.pack(side="left")

        # Separator
        tk.Frame(self, bg=ACCENT, height=1).pack(fill="x", padx=12, pady=8)

        # Log path
        tk.Label(self, text="Skip log:", bg=BG, fg=STATUS_GREY,
                 font=small, anchor="w").pack(fill="x", padx=14)
        log_path = logger.get_log_path()
        tk.Label(self, text=log_path, bg=BG, fg=STATUS_GREY,
                 font=tkfont.Font(family="Segoe UI", size=7),
                 wraplength=WIN_WIDTH - 24, justify="left",
                 anchor="w").pack(fill="x", padx=14, pady=(0, 8))

    # ── Window placement ──────────────────────────────────────────────────────

    def _position_window(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = sw - WIN_WIDTH - RIGHT_MARGIN
        y = (sh - WIN_HEIGHT) // 2
        self.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}+{x}+{y}")

    # ── Server check ──────────────────────────────────────────────────────────

    def _startup_server_check(self):
        threading.Thread(target=self._check_server_thread, daemon=True).start()

    def _check_server_thread(self):
        ok = vision_client.check_server()
        self.after(0, self._update_server_indicator, ok)

    def _update_server_indicator(self, ok: bool):
        if ok:
            self._server_dot.config(fg=STATUS_GREEN)
            self._server_label.config(text="Server OK", fg=STATUS_GREEN)
        else:
            self._server_dot.config(fg=BTN_DISARM)
            self._server_label.config(text="Server unreachable", fg=BTN_DISARM)

    # ── ARM / DISARM ──────────────────────────────────────────────────────────

    def _on_arm(self):
        self._set_status("blinking", "Checking server…")
        threading.Thread(target=self._arm_thread, daemon=True).start()

    def _arm_thread(self):
        ok = vision_client.check_server()
        self.after(0, self._update_server_indicator, ok)
        if not ok:
            self.after(0, self._set_status, "idle",
                       "Cannot reach server — check internet connection")
            return
        self.after(0, self._arm_confirmed)

    def _arm_confirmed(self):
        self._armed = True
        self._stop_flag.clear()
        self._arm_btn.config(state="disabled")
        self._disarm_btn.config(state="normal")
        self._set_status("blinking", "Armed — watching for Information Message")

        plan = self._plan.get()

        # Check if Information Message is already open
        win = window_utils.find_information_message()
        if win is not None:
            self._set_status("running", "Information Message already open")
            self._start_adjudication(win, plan)
        else:
            threading.Thread(
                target=self._watch_thread, args=(plan,), daemon=True
            ).start()

    def _watch_thread(self, plan: str):
        def found_cb(win):
            self.after(0, self._on_review_window_found, win, plan)

        def status_cb(msg: str):
            self.after(0, self._set_detail, msg)

        watcher.watch(found_cb, self._stop_flag, status_cb)

    def _on_review_window_found(self, win, plan: str):
        self._set_status("running", "Adjudicating…")
        self._start_adjudication(win, plan)

    def _start_adjudication(self, info_win, plan: str):
        # Click OK on Information Message window
        try:
            info_win.child_window(title=" OK", control_type="Button").click_input()
        except Exception:
            try:
                info_win.set_focus()
                kb.send_keys("{ENTER}")
            except Exception:
                pass
        time.sleep(0.3)

        def status_cb(msg: str):
            self.after(0, self._set_detail, msg)

        def done_cb():
            self.after(0, self._on_patient_done)

        threading.Thread(
            target=adjudicator.run,
            args=(plan, status_cb, done_cb, self._stop_flag),
            daemon=True,
        ).start()

    def _on_patient_done(self):
        if not self._armed:
            return
        self._set_status("done", "Patient complete — re-arming in 1.5s")
        self.after(1500, self._rearm)

    def _rearm(self):
        if not self._armed:
            return
        plan = self._plan.get()
        self._set_status("blinking", "Re-armed — watching for Information Message")
        win = window_utils.find_information_message()
        if win is not None:
            self._set_status("running", "Adjudicating…")
            self._start_adjudication(win, plan)
        else:
            threading.Thread(
                target=self._watch_thread, args=(plan,), daemon=True
            ).start()

    def _on_disarm(self):
        self._armed = False
        self._stop_flag.set()
        self._arm_btn.config(state="normal")
        self._disarm_btn.config(state="disabled")
        self._cancel_blink()
        self._set_status("idle", "Disarmed")

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_status(self, state: str, text: str):
        """state: 'idle' | 'blinking' | 'running' | 'done'"""
        self._cancel_blink()
        colors = {
            "idle": STATUS_GREY,
            "running": STATUS_AMBER,
            "done": STATUS_GREEN,
        }
        if state == "blinking":
            self._status_text.config(text=text, fg=FG)
            self._start_blink()
        else:
            color = colors.get(state, STATUS_GREY)
            self._status_dot_label.config(fg=color)
            self._status_text.config(text=text, fg=FG)
        self._detail_var.set("")

    def _set_detail(self, msg: str):
        self._detail_var.set(msg)

    def _start_blink(self):
        self._blink_state = True
        self._do_blink()

    def _do_blink(self):
        self._blink_state = not self._blink_state
        color = STATUS_BLUE if self._blink_state else BG
        self._status_dot_label.config(fg=color)
        self._blink_job = self.after(500, self._do_blink)

    def _cancel_blink(self):
        if self._blink_job is not None:
            self.after_cancel(self._blink_job)
            self._blink_job = None

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        self._stop_flag.set()
        self.destroy()
        sys.exit(0)
