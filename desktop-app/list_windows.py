"""
Run this script while the Kroll Information Message is visible on screen.
It prints all visible window titles so you can find the exact title to match.
"""
from pywinauto import Desktop

for win in Desktop(backend="win32").windows():
    try:
        if win.is_visible():
            title = win.window_text()
            if title.strip():
                print(repr(title))
    except Exception:
        pass
