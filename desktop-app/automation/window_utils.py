import time
from PIL import ImageGrab
from pywinauto import Desktop


def all_windows():
    for _ in range(3):
        try:
            return Desktop(backend="win32").windows()
        except Exception:
            time.sleep(0.1)
    return []


def find_information_message():
    for win in all_windows():
        try:
            if win.window_text() == "Information Message" and win.is_visible():
                return win
        except Exception:
            pass
    return None


def find_adjudication_window():
    """Return the first visible adjudication response window (any plan)."""
    for win in all_windows():
        try:
            title = win.window_text()
            if "Adjudication Response" in title and win.is_visible():
                return win
        except Exception:
            pass
    return None


def find_onnms_window():
    for win in all_windows():
        try:
            if win.window_text() == "Adjudication Response for ONNMS" and win.is_visible():
                return win
        except Exception:
            pass
    return None


def find_adjudication_or_onnms():
    """Return (win, kind) where kind is 'onnms' or 'adjudication', or (None, None)."""
    for win in all_windows():
        try:
            if not win.is_visible():
                continue
            title = win.window_text()
            if title == "Adjudication Response for ONNMS":
                return win, "onnms"
            if "Adjudication Response" in title:
                return win, "adjudication"
        except Exception:
            pass
    return None, None


def screenshot_window(win) -> "Image.Image":
    rect = win.rectangle()
    return ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))


def screenshot_screen() -> "Image.Image":
    return ImageGrab.grab()


def dismiss_onnms(win) -> bool:
    """Click the OK button in an ONNMS window. Returns True if a button was clicked."""
    import pywinauto.keyboard as kb
    for title in ("OK", " OK", "Ok"):
        try:
            btn = win.child_window(title=title, control_type="Button")
            btn.click_input()
            return True
        except Exception:
            pass
    try:
        win.set_focus()
        kb.send_keys("{ENTER}")
        return True
    except Exception:
        pass
    return False


def wait_for_window_close(win, timeout: float = 6.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not win.is_visible():
                break
        except Exception:
            break
        time.sleep(0.1)
