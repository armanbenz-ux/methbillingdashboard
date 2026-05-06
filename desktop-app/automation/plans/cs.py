import time
import pywinauto.keyboard as kb
from automation import window_utils
from vision import client as vision_client
from utils import logger


def handle(win, token: str, plan: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        win.send_keystrokes("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status in ("COST_DIFF", "FEE_DIFF"):
        win.send_keystrokes("n")
        time.sleep(1)
        img = window_utils.screenshot_screen()
        next_token = vision_client.analyse(img, plan, "main")
        status_cb(f"After N: {next_token}")
        return _handle_post_n(next_token)

    if status == "COPAY":
        win.send_keystrokes("0{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status in (
        "REJECTED_IDENTICAL_CLAIM",
        "REJECTED_COVERAGE_ERROR",
        "REJECTED_OTHER",
    ):
        win.send_keystrokes("s")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        logger.log_skip(plan, token)
        return "flush"

    win.send_keystrokes("s")
    window_utils.wait_for_window_close(win)
    time.sleep(0.3)
    logger.log_skip(plan, token)
    return "flush"


def _handle_post_n(token: str) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""
    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        kb.send_keys("{ENTER}")
        time.sleep(0.3)
        return "continue"
    if status == "COPAY":
        kb.send_keys("0{ENTER}")
        time.sleep(0.3)
        return "continue"
    return "continue"
