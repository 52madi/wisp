"""Display smoke test, run on Windows and macOS CI (no microphone or network)."""
import sys
from pathlib import Path
import time
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wisp import Pill

root = tk.Tk()
root.withdraw()
errors = []
root.report_callback_exception = lambda *args: errors.append(args)
try:
    pill = Pill(root, lambda: None, lambda: None, lambda: None)
    for state in ("idle", "rec", "busy", "loading"):
        pill.set_state(state)
        pill.push(0.5)
        root.update()
        if sys.platform == "win32":
            pill._render(time.time(), False)
        else:
            pill._tick()
    assert not errors, errors
    print("Overlay created and all states rendered")
finally:
    root.destroy()
