import time
import pywinauto.keyboard as kb_mod
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
            if "ONNMS" in win.window_text() and win.is_visible():
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
            if "ONNMS" in title:
                return win, "onnms"
            if "Adjudication Response" in title:
                return win, "adjudication"
        except Exception:
            pass
    return None, None


def _is_active(win) -> bool:
    """Is this window the one keystrokes will actually reach?"""
    try:
        return bool(win.is_active())
    except Exception:
        pass
    try:
        import win32gui
        return win32gui.GetForegroundWindow() == win.handle
    except Exception:
        return False


def focus_window(win, attempts: int = 3, settle: float = 0.2) -> bool:
    """
    Bring a window to the front and CONFIRM it got there. True if it did.

    `pywinauto.keyboard.send_keys` types into whatever owns the foreground, not
    into the window you were looking at. Every plan handler read one window and
    then typed blind, so a popup arriving in between took the keystroke instead.

    Stropnicki, live 2026-10-03: an ONNMS window appeared between reading an
    `Adjudication Response` and answering it. The `{ENTER}` for
    `ODB:COPAY_AUTO_WAIVED` went to the ONNMS; the adjudication window stayed
    open; the loop re-read the same token six times and stopped at its safety
    cap on the 30th claim of 35.

    `set_focus()` can also fail silently, so the result is checked rather than
    assumed -- the point is to be able to NOT type when the window did not come
    forward.
    """
    for attempt in range(attempts):
        try:
            if _is_active(win):
                return True
            win.set_focus()
        except Exception:
            pass
        time.sleep(settle)
        if _is_active(win):
            return True
    return _is_active(win)


def send_to(win, keys: str, status_cb=None) -> bool:
    """
    Type into a specific window, or type NOTHING. True if the keys were sent.

    The alternative to refusing is sending them somewhere nobody chose, and in
    this app the keystrokes are claim answers -- `{ENTER}` accepts, `s` skips,
    `0{ENTER}` waives a copay. A skip that lands on the wrong window is a claim
    nobody adjudicated.
    """
    if not focus_window(win):
        if status_cb:
            status_cb(f"could not bring the window forward -- {keys!r} NOT sent")
        return False
    kb_mod.send_keys(keys)
    return True


def is_window_open(win) -> bool:
    """True if the window still exists and is visible; False if it has closed."""
    try:
        return bool(win.is_visible())
    except Exception:
        return False


def screenshot_window(win) -> "Image.Image":
    rect = win.rectangle()
    if rect.right <= rect.left or rect.bottom <= rect.top:
        raise ValueError("window rectangle is empty (window closed or minimized)")
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


def wait_for_window_close(win, timeout: float = 6.0) -> bool:
    """
    Wait for a window to close. **True if it actually did.**

    It used to return nothing at all, so every caller carried on identically
    whether the window had gone or was still sitting there unanswered -- which
    is how the same claim was answered six times over and nothing noticed.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not win.is_visible():
                return True
        except Exception:
            return True                  # destroyed: gone is gone
        time.sleep(0.1)
    return not is_window_open(win)
