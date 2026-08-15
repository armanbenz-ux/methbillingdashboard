"""
Main adjudication loop.
Runs in a daemon thread. Communicates status back via status_cb(str).
Calls done_cb() when all plans for a patient are complete.

Plan is auto-detected from each adjudication window screenshot — no upfront
selection needed. Cash patients never show an adjudication window, so if only
ONNMS windows appear the loop times out and declares billing complete.
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


def run(status_cb, done_cb, stop_flag) -> None:
    """
    status_cb: callable(str) — update GUI status label
    done_cb: callable() — called when patient billing is complete
    stop_flag: threading.Event — set to request abort
    """
    iterations = 0
    while not stop_flag.is_set() and iterations < _SAFETY_CAP:
        iterations += 1

        win, kind = _poll_for_window(_DONE_TIMEOUT, status_cb, stop_flag)

        if stop_flag.is_set():
            return

        if win is None:
            # Timed out with no window — billing complete (covers cash patients
            # where only ONNMS windows appeared, and normal end-of-billing)
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
        status_cb("Adjudication window found — screenshotting")
        time.sleep(0.8)  # let window finish painting before capture
        try:
            img = window_utils.screenshot_window(win)
        except Exception as e:
            status_cb(f"Screenshot error: {e}")
            continue

        try:
            analysis = vision_client.analyse_full(img, "", "main")
        except Exception as e:
            status_cb(f"Vision error: {e}")
            continue

        token   = analysis["token"]
        pricing = analysis.get("pricing")
        status_cb(f"Token: {token}")

        token_plan = token.split(":")[0] if ":" in token else ""
        handler = _PLAN_HANDLERS.get(token_plan)

        if handler is None:
            status_cb(f"Unrecognised plan in token: {token} — skipping")
            kb.send_keys("s")
            window_utils.wait_for_window_close(win)
            time.sleep(0.3)
            continue

        try:
            result = handler(win, token, token_plan, status_cb, pricing)
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
