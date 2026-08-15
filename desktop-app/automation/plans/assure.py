import time
import pywinauto.keyboard as kb
from automation import window_utils, predictor
from vision import client as vision_client
from utils import logger
import config


def handle(win, token: str, plan: str, status_cb, pricing=None) -> str:
    parts = token.split(":")
    status = parts[1] if len(parts) > 1 else ""

    if status in ("ACCEPTED", "COPAY_AUTO_WAIVED"):
        kb.send_keys("{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status in ("COST_DIFF", "FEE_DIFF", "MARKUP_DIFF"):
        queue, meta, ok = predictor.compute_plan(pricing)
        if config.PREDICTOR_SHADOW:
            logger.log_shadow(plan, pricing or {}, queue if ok else [], meta)
            shown = ",".join(queue) if ok and queue else f"(skip: {meta.get('reason')})"
            status_cb(f"[SHADOW] {plan} would fire {shown}")
            # fall through to legacy
        elif ok and queue and config.PREDICTOR_ENABLED:
            status_cb(f"Predicted {queue} | {meta}")
            predictor.fire(win, queue, status_cb)
            if predictor.verify_closed(win):
                time.sleep(0.3)
                return "continue"
            status_cb("Prediction mismatch — reverting to per-key")
        elif pricing:
            status_cb(f"Predictor skipped ({meta.get('reason')}) — per-key")
        # legacy per-keystroke fallback
        kb.send_keys("n")
        time.sleep(1)
        img = window_utils.screenshot_window(win)
        next_token = vision_client.analyse(img, plan, "main")
        status_cb(f"After N: {next_token}")
        return _handle_post_n(win, next_token)

    if status == "COPAY":
        kb.send_keys("0{ENTER}")
        window_utils.wait_for_window_close(win)
        time.sleep(0.3)
        return "continue"

    if status == "REJECTED_DRUG_INTERACTION":
        kb.send_keys("i")
        time.sleep(0.4)
        kb.send_keys("UA{ENTER}")
        time.sleep(0.3)
        return "continue"

    if status in ("REJECTED_IDENTICAL_CLAIM", "REJECTED_REFILL_TOO_SOON"):
        kb.send_keys("i{ENTER}")
        time.sleep(0.3)
        return "continue"

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


def _handle_post_n(win, token: str) -> str:
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
