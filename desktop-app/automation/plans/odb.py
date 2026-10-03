import time
import pywinauto.keyboard as kb
from automation import window_utils
from vision import client as vision_client
from utils import logger


def _waive_copay_amounts() -> set:
    return {"2.00", "6.11"}


def handle(win, token: str, plan: str, status_cb, pricing=None) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        window_utils.send_to(win, "{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status in ("COST_DIFF", "MARKUP_DIFF"):
        window_utils.send_to(win, "n")
        time.sleep(1)
        if not window_utils.is_window_open(win):
            time.sleep(0.3)
            return "continue"
        img = window_utils.screenshot_window(win)
        next_token = vision_client.analyse(img, plan, "main")
        status_cb(f"After N: {next_token}")
        return handle_post_n(win, next_token, plan, status_cb)

    if status == "COPAY":
        amount = extra
        if amount in _waive_copay_amounts():
            window_utils.send_to(win, "0{ENTER}")
        else:
            window_utils.send_to(win, "{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_DRUG_INTERACTION":
        window_utils.send_to(win, "i", status_cb)
        time.sleep(0.4)
        # The `i` above opens the intervention dialog, and THIS goes to that
        # dialog, not back to the adjudication window. There is no handle for
        # it here, so it stays a blind send -- forcing focus back to `win`
        # would type the intervention code into the window behind the dialog.
        kb.send_keys("UA{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_IDENTICAL_CLAIM":
        window_utils.send_to(win, "i", status_cb)
        time.sleep(0.4)
        # The `i` above opens the intervention dialog, and THIS goes to that
        # dialog, not back to the adjudication window. There is no handle for
        # it here, so it stays a blind send -- forcing focus back to `win`
        # would type the intervention code into the window behind the dialog.
        kb.send_keys("UA{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status in ("REJECTED_COVERAGE_ERROR", "REJECTED_OTHER", "REJECTED_REFILL_TOO_SOON"):
        window_utils.send_to(win, "s")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        logger.log_skip(plan, token)
        return "flush"

    window_utils.send_to(win, "s")
    window_utils.wait_for_window_close(win)
    time.sleep(0.3)
    logger.log_skip(plan, token)
    return "flush"


def handle_post_n(win, token: str, plan: str, status_cb) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        window_utils.send_to(win, "{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "COPAY":
        amount = extra
        if amount in _waive_copay_amounts():
            window_utils.send_to(win, "0{ENTER}")
        else:
            window_utils.send_to(win, "{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    window_utils.wait_for_window_close(win)
    time.sleep(0.3)
    return "continue"
