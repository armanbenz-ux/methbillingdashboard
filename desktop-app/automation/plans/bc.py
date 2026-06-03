import time
import pywinauto.keyboard as kb
from pywinauto import Desktop
from automation import window_utils
from vision import client as vision_client
from utils import logger


def handle(win, token: str, plan: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        kb.send_keys("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status in ("COST_DIFF", "FEE_DIFF"):
        kb.send_keys("n")
        time.sleep(1)
        img = window_utils.screenshot_window(win)
        next_token = vision_client.analyse(img, plan, "main")
        status_cb(f"After N: {next_token}")
        return _handle_post_n(win, next_token, status_cb)

    if status == "COPAY":
        kb.send_keys("0{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_IDENTICAL_CLAIM":
        return _bc_intervention(win, plan, status_cb)

    if status in ("REJECTED_COVERAGE_ERROR", "REJECTED_OTHER"):
        kb.send_keys("s")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        logger.log_skip(plan, token)
        return "flush"

    kb.send_keys("s")
    window_utils.wait_for_window_close(win)
    time.sleep(0.3)
    logger.log_skip(plan, token)
    return "flush"


def _handle_post_n(win, token: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""
    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        kb.send_keys("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"
    if status == "COPAY":
        kb.send_keys("0{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"
    window_utils.wait_for_window_close(win)
    time.sleep(0.3)
    return "continue"


def _bc_intervention(win, plan: str, status_cb) -> str:
    """BC identical claim intervention: I → select list → double-click → UN → Enter."""
    kb.send_keys("i")
    time.sleep(0.8)

    list_win = None
    deadline = time.time() + 6
    while time.time() < deadline:
        for w in Desktop(backend="win32").windows():
            try:
                if w.window_text() == "Select an item from the list" and w.is_visible():
                    list_win = w
                    break
            except Exception:
                pass
        if list_win:
            break
        time.sleep(0.2)

    if list_win is None:
        status_cb("BC intervention: list window not found")
        return "continue"

    img = window_utils.screenshot_window(list_win)
    item_text = vision_client.analyse(img, plan, "bc_intervention")
    status_cb(f"BC intervention item: {item_text}")

    if item_text == "NOT_FOUND":
        status_cb("BC intervention: item not found by vision")
        return "continue"

    try:
        list_win.child_window(title=item_text).double_click_input()
    except Exception:
        for ctrl in list_win.descendants():
            try:
                if item_text in ctrl.window_text():
                    ctrl.double_click_input()
                    break
            except Exception:
                pass

    time.sleep(0.5)  # wait for free form code dialog to open
    kb.send_keys("UN{ENTER}")
    time.sleep(0.5)
    # wait for the rejection window to fully close after resubmission
    window_utils.wait_for_window_close(win, timeout=10.0)
    time.sleep(0.3)
    return "continue"
