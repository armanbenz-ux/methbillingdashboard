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
        status_cb("Cash — handling ONNMS windows")
        _handle_cash(status_cb, stop_flag)
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
            clicked = window_utils.dismiss_onnms(win)
            if not clicked:
                status_cb("ONNMS dismiss failed — could not find OK button")
            window_utils.wait_for_window_close(win, timeout=6.0)
            time.sleep(0.3)
            continue

        # kind == 'adjudication'
        # Detect plan from window title — more reliable than vision
        window_plan = plan_upper
        try:
            title = win.window_text()
            for p in ("ODB", "BC", "CS", "GS", "AHE"):
                if f"for {p}" in title:
                    window_plan = p
                    break
        except Exception:
            pass

        status_cb("Adjudication window found — screenshotting")
        try:
            img = window_utils.screenshot_window(win)
        except Exception as e:
            status_cb(f"Screenshot error: {e}")
            continue

        try:
            token = vision_client.analyse(img, window_plan, "main")
        except Exception as e:
            status_cb(f"Vision error: {e}")
            continue

        status_cb(f"Token: {token}")

        token_plan = token.split(":")[0] if ":" in token else window_plan
        handler = _PLAN_HANDLERS.get(token_plan, _PLAN_HANDLERS.get(window_plan))

        if handler is None:
            status_cb(f"Unknown plan in token: {token}")
            continue

        try:
            result = handler(win, token, token_plan, status_cb)
        except Exception as e:
            status_cb(f"Handler error: {e}")
            continue

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
        try:
            win, kind = window_utils.find_adjudication_or_onnms()
        except Exception:
            time.sleep(_POLL_INTERVAL)
            continue
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
        win.send_keystrokes("s")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)


def _handle_cash(status_cb, stop_flag) -> None:
    """Dismiss ONNMS windows one by one until none appear within timeout."""
    while not stop_flag.is_set():
        onnms = None
        deadline = time.time() + 10
        while time.time() < deadline and not stop_flag.is_set():
            try:
                onnms = window_utils.find_onnms_window()
            except Exception:
                pass
            if onnms:
                break
            time.sleep(0.3)
        if onnms is None:
            return
        status_cb("ONNMS window — clicking OK")
        window_utils.dismiss_onnms(onnms)
        window_utils.wait_for_window_close(onnms)
        time.sleep(0.3)
