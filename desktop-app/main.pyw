"""
Windowless launcher for the Adjudication Dashboard.

Double-click this file (or point a shortcut at it) to open the dashboard
without a command-prompt window. Windows runs .pyw files with pythonw.exe,
which has no console.

Because there is no console, stdout/stderr are redirected to
adjudication_dashboard.log next to this file so errors are not lost, and a
startup crash is shown in a message box.
"""
import os
import sys
import traceback

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

_log_path = os.path.join(_here, "adjudication_dashboard.log")
try:
    _log = open(_log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log
except OSError:
    pass


def _show_error(msg: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Adjudication Dashboard", msg)
        root.destroy()
    except Exception:
        pass


try:
    from main import main
    main()
except Exception:
    tb = traceback.format_exc()
    if sys.stderr:
        sys.stderr.write(tb)
    _show_error(f"The dashboard failed to start:\n\n{tb}\n\nDetails were saved to:\n{_log_path}")
