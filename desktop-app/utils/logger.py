import ctypes
import ctypes.wintypes
import os
import datetime


def _get_desktop_path() -> str:
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    # CSIDL_DESKTOPDIRECTORY = 0x0010; handles OneDrive-redirected Desktop
    ctypes.windll.shell32.SHGetFolderPathW(0, 0x0010, 0, 0, buf)
    return buf.value or os.path.join(os.path.expanduser("~"), "Desktop")


def log_skip(plan: str, token: str) -> None:
    desktop = _get_desktop_path()
    date_str = datetime.date.today().isoformat()
    log_path = os.path.join(desktop, f"adjudication_skipped_{date_str}.log")
    time_str = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"{time_str}  SKIPPED — {plan} | {token}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def log_shadow(plan: str, numbers: dict, predicted: list, meta: dict = None) -> None:
    desktop = _get_desktop_path()
    date_str = datetime.date.today().isoformat()
    log_path = os.path.join(desktop, f"adjudication_shadow_{date_str}.log")
    time_str = datetime.datetime.now().strftime("%H:%M:%S")
    fields = ("cost_diff", "markup_diff", "fee_diff", "total_diff", "pat_pays")
    nums = " ".join(f"{k}={numbers.get(k)}" for k in fields)
    if predicted:
        action = "predicted: " + ",".join(predicted)
    else:
        reason = (meta or {}).get("reason", "?")
        action = f"predicted: (skip: {reason})"
    line = f"{time_str}  {plan} | {nums} | {action}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def get_log_path() -> str:
    desktop = _get_desktop_path()
    date_str = datetime.date.today().isoformat()
    return os.path.join(desktop, f"adjudication_skipped_{date_str}.log")
