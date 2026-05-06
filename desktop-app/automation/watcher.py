"""
Polls for the Kroll "Information Message" window.
Runs in a daemon thread. Calls found_cb() when the window appears.
"""
import time
from automation import window_utils

_POLL_INTERVAL = 0.4


def watch(found_cb, stop_flag, status_cb) -> None:
    checks = 0
    while not stop_flag.is_set():
        win = window_utils.find_information_message()
        if win is not None:
            status_cb("Information Message window found")
            found_cb(win)
            return
        checks += 1
        if checks % 5 == 0:
            status_cb(f"Watching… (checked {checks} times)")
        time.sleep(_POLL_INTERVAL)
