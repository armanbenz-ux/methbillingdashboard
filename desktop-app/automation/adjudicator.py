"""
Main adjudication loop.
Runs in a daemon thread. Communicates status back via status_cb(str).
Calls done_cb() when all plans for a patient are complete.
"""
import time
import pywinauto.keyboard as kb

from automation import window_utils
from automation.plans import odb, bc, cs, gs, assure
from vision import client as vision_client
from utils import logger

_POLL_INTERVAL = 0.4
_DONE_TIMEOUT = 15.0
_FLUSH_TIMEOUT = 15.0
_SAFETY_CAP = 60


_PLAN_HANDLERS = {
    "ODB": odb.handle,
    "BC": bc.handle,
    "CS": cs.handle,
    "GS": gs.handle,
    "AHE": assure.handle,
}


def run(plan_name: str, status_cb, done_cb, stop_flag) -> None:
    """
    plan_name: one of 'odb'|'bc'|'cs'|'gs'|'ahe'|'cash'
    status_cb: callable(str) — update GUI status label
    done_cb: callable() — called when patient billing is complete
    stop_flag: threading.Event — set to request abort
    """
    plan_upper = plan_name.upper()

    if plan_upper == "CASH":
        status_cb("Cash — checking for ONNMS window")
        _handle_cash(status_cb)
        status_cb("Cash patient done")
        done_cb()
        return

    iterations = 0
    while not stop_flag.is_set() and iterations < _SAFETY_CAP:
        iterations += 1

        win, kind = _poll_for_window(_DONE_TIMEOUT, status_cb, stop_flag)

        if stop_flag.is_set():
            return

        if win is None:
            # Timeout — billing complete
            status_cb("Billing complete")
            done_cb()
            return

        if kind == "onnms":
            status_cb("ONNMS window — clicking OK")
            window_utils.dismiss_onnms(win)
            window_utils.wait_for_window_close(win, timeout=6.0)
            time.sleep(0.3)
            continue

        # kind == 'adjudication'
        status_cb("Adjudication window found — screenshotting")
        try:
            img = window_utils.screenshot_window(win)
        except Exception as e:
            status_cb(f"Screenshot error: {e}")
            continue

        try:
            token = vision_client.analyse(img, plan_upper, "main")
        except Exception as e:
            status_cb(f"Vision error: {e}")
            continue

        status_cb(f"Token: {token}")

        token_plan = token.split(":")[0] if ":" in token else plan_upper
        handler = _PLAN_HANDLERS.get(token_plan, _PLAN_HANDLERS.get(plan_upper))

        if handler is None:
            status_cb(f"Unknown plan in token: {token}")
            continue

        result = handler(win, token, token_plan, status_cb)

        if result == "flush":
            _flush(stop_flag, status_cb)
            status_cb("Flush complete — patient done")
            done_cb()
            return

    if iterations >= _SAFETY_CAP:
        status_cb("Safety cap reached — stopping")
    done_cb()


def _poll_for_window(timeout: float, status_cb, stop_flag):
    """Poll for ONNMS or adjudication window. Returns (win, kind) or (None, None)."""
    deadline = time.time() + timeout
    checks = 0
    while time.time() < deadline and not stop_flag.is_set():
        win, kind = window_utils.find_adjudication_or_onnms()
        if win is not None:
            return win, kind
        checks += 1
        if checks % 5 == 0:
            elapsed = int(timeout - (deadline - time.time()))
            status_cb(f"Watching… (checked {checks} times, {elapsed}s)")
        time.sleep(_POLL_INTERVAL)
    return None, None


def _flush(stop_flag, status_cb) -> None:
    """Press S on every remaining adjudication window until none appear."""
    while not stop_flag.is_set():
        win, kind = _poll_for_window(_FLUSH_TIMEOUT, status_cb, stop_flag)
        if win is None:
            return
        if kind == "onnms":
            status_cb("ONNMS during flush — clicking OK")
            window_utils.dismiss_onnms(win)
            time.sleep(0.3)
            continue
        status_cb("Flushing adjudication window")
        win.set_focus()
        kb.send_keys("s")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)


def _handle_cash(status_cb) -> None:
    """After OK on review prompt, handle any ONNMS window then done."""
    deadline = time.time() + 5
    while time.time() < deadline:
        onnms = window_utils.find_onnms_window()
        if onnms:
            status_cb("ONNMS window after cash — clicking OK")
            window_utils.dismiss_onnms(onnms)
            return
        time.sleep(0.2)
