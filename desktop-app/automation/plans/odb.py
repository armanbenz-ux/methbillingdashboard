import time
import pywinauto.keyboard as kb
from automation import window_utils
from vision import client as vision_client
from utils import logger


def _waive_copay_amounts() -> set:
    return {"2.00", "6.11"}


def handle(win, token: str, plan: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        win.send_keystrokes("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "COST_DIFF":
        win.send_keystrokes("n")
        time.sleep(1)
        img = window_utils.screenshot_screen()
        next_token = vision_client.analyse(img, plan, "main")
        status_cb(f"After N: {next_token}")
        return handle_post_n(win, next_token, plan, status_cb)

    if status == "COPAY":
        amount = extra
        if amount in _waive_copay_amounts():
            win.send_keystrokes("0{ENTER}")
        else:
            win.send_keystrokes("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_DRUG_INTERACTION":
        win.send_keystrokes("i")
        time.sleep(0.4)
        kb.send_keys("UA{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_IDENTICAL_CLAIM":
        win.send_keystrokes("i")
        time.sleep(0.4)
        kb.send_keys("UA{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status in ("REJECTED_COVERAGE_ERROR", "REJECTED_OTHER", "REJECTED_REFILL_TOO_SOON"):
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


def handle_post_n(win, token: str, plan: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        kb.send_keys("{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status == "COPAY":
        amount = extra
        if amount in _waive_copay_amounts():
            kb.send_keys("0{ENTER}")
        else:
            kb.send_keys("{ENTER}")
        time.sleep(0.3)
        return "continue"

    return "continue"
