"""
Double-click THIS instead of main.py: the same app, with no console window.

Windows runs a `.py` with `python.exe`, which always gets a Command Prompt
alongside it. A `.pyw` runs on `pythonw.exe`, which has no console at all --
so this is not a console being hidden, it is one never being created.

`main.py` still exists and still works (`python main.py`), and is the one to
run when something is wrong: it shows what Python said.

Because there is no console here, a crash before the window opens would be
completely silent. So it is written to `last-crash.txt` next to this file and
shown in a message box -- an invisible failure is worse than an ugly one.
"""
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG = os.path.join(_HERE, "last-crash.txt")


def _report(detail: str) -> None:
    """Leave the traceback somewhere it can be read, then say so."""
    try:
        with open(CRASH_LOG, "w", encoding="utf-8") as fh:
            fh.write(detail)
        where = CRASH_LOG
    except OSError:
        where = "(could not be written)"

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Adjudication Dashboard",
            "The dashboard could not start.\n\n"
            f"{detail.strip().splitlines()[-1]}\n\n"
            f"The full details are in:\n{where}\n\n"
            "Running main.py instead opens a window and shows the same thing.")
        root.destroy()
    except Exception:
        pass                              # no Tk: the file is still written


if __name__ == "__main__":
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    try:
        from main import main
        main()
    except Exception:
        _report(traceback.format_exc())
        sys.exit(1)
