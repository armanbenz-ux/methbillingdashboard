import time
import pywinauto.keyboard as kb
from automation import window_utils
from vision import client as vision_client
from utils import logger


def handle(win, token: str, plan: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        win.set_focus()
        kb.send_keys("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status in ("COST_DIFF", "FEE_DIFF"):
        win.set_focus()
        kb.send_keys("n")
        time.sleep(1)
        img = window_utils.screenshot_screen()
        next_token = vision_client.analyse(img, plan, "main")
        status_cb(f"After N: {next_token}")
        return _handle_post_n(next_token)

    if status == "COPAY":
        win.set_focus()
        kb.send_keys("0{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_DRUG_INTERACTION":
        win.set_focus()
        kb.send_keys("i")
        time.sleep(0.4)
        kb.send_keys("UA{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status in ("REJECTED_IDENTICAL_CLAIM", "REJECTED_REFILL_TOO_SOON"):
        # First intervention option already selected — I → Enter
        win.set_focus()
        kb.send_keys("i{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status in ("REJECTED_COVERAGE_ERROR", "REJECTED_OTHER"):
        win.set_focus()
        kb.send_keys("s")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        logger.log_skip(plan, token)
        return "flush"

    win.set_focus()
    kb.send_keys("s")
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
