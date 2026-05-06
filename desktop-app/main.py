"""
Entry point for the Adjudication Dashboard desktop app.
Run on Windows with Kroll installed:
    python main.py
"""
import sys
import os

# Ensure the desktop-app directory is on sys.path regardless of cwd
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from gui.dashboard import Dashboard


def main():
    app = Dashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
