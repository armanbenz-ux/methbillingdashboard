"""
Predictive keystroke sequencer for private-plan price-adjustment windows.
Reads the Difference row + Pat Pays (already extracted by vision), computes the
full waive sequence, and fires it blind. Vision reads numbers; ALL logic is here.
"""
import time
import pywinauto.keyboard as kb
from automation import window_utils

TOL = 0.005
INTER_KEY_DELAY = 0.5  # seconds between keystrokes; lets Kroll paint the next prompt


def compute_plan(pricing: dict):
    """
    pricing: {cost_diff, markup_diff, fee_diff, total_diff, pat_pays}
             (floats; any may be missing/None).
    Returns (queue, meta, ok).
      queue : list of pywinauto key strings to fire in order.
      meta  : dict for logging.
      ok    : False => do NOT use prediction; caller falls back to legacy per-key.
    """
    if not pricing:
        return [], {"reason": "no pricing"}, False

    if not pricing.get("charge_prompt"):
        return [], {"reason": "no yes/no charge prompt — not a difference window"}, False

    def num(key):
        v = pricing.get(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    cost   = num("cost_diff")   or 0.0
    markup = num("markup_diff") or 0.0
    fee    = num("fee_diff")    or 0.0
    total  = num("total_diff")
    pat    = num("pat_pays")

    # anomaly guards: any trip => legacy fallback (never guess)
    if pat is None:
        return [], {"reason": "missing pat_pays"}, False

    summed = round(cost + markup + fee, 2)
    if total is None:
        total = summed
    elif abs(total - summed) > 0.02:
        return [], {"reason": f"total_diff {total} != sum {summed}"}, False

    residual = round(pat - total, 2)
    if residual < -TOL:
        return [], {"reason": f"negative residual ({residual})"}, False

    n_presses   = sum(1 for d in (cost, markup, fee) if d > TOL)
    copay_after = residual > TOL

    # a difference-prompt window with zero readable diffs is a misread -> fallback
    if n_presses == 0:
        return [], {"reason": "no non-zero diffs on a diff window"}, False

    queue = ["n"] * n_presses
    if copay_after:
        queue.append("0{ENTER}")

    meta = {
        "n_presses": n_presses,
        "residual": residual,
        "copay_after": copay_after,
        "total_diff": total,
        "pat_pays": pat,
    }
    return queue, meta, True


def fire(win, queue, status_cb=None) -> None:
    """Send the predicted keystrokes into the adjudication window, blind."""
    try:
        win.set_focus()
    except Exception:
        pass
    for i, key in enumerate(queue, 1):
        kb.send_keys(key)
        if status_cb:
            status_cb(f"Predictor sent {key!r} ({i}/{len(queue)})")
        time.sleep(INTER_KEY_DELAY)


def verify_closed(win, timeout: float = 6.0) -> bool:
    """True if the window closed (success signal: next window/ONNMS will follow)."""
    window_utils.wait_for_window_close(win, timeout=timeout)
    try:
        return not win.is_visible()
    except Exception:
        return True
