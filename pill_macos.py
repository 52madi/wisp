"""Tk overlay for macOS, independent of Win32 and NVIDIA libraries."""
import time
import tkinter as tk


class Pill(tk.Toplevel):
    scale = 1.0

    def __init__(self, master, on_mic, on_more, on_stop):
        super().__init__(master)
        self.state = "loading"
        self.hotkey_name = "Rechte Strg"
        self.menu_open = False
        self.dirty = True
        self.error_until = 0
        self.level = 0
        self.overrideredirect(True)
        # Tk Aqua window styles: https://github.com/tcltk/tk/blob/main/macosx/README
        self.tk.call("::tk::unsupported::MacWindowStyle", "style", self._w,
                     "help", "noActivates")
        self.attributes("-topmost", True)
        self.configure(bg="#151515")
        self.x = (self.winfo_screenwidth() - 310) // 2
        self.y = self.winfo_screenheight() - 140
        self.geometry(f"310x54+{self.x}+{self.y}")
        self.label = tk.Label(self, bg="#151515", fg="white", width=28)
        self.label.pack(side="left", padx=8)
        self.label.bind("<Button-1>", lambda e: on_stop() if self.state == "rec" else on_mic())
        tk.Button(self, text="•••", command=on_more).pack(side="right", padx=8)
        self.after(50, self._tick)

    @property
    def top_screen(self):
        return self.y

    @property
    def menu_center_x(self):
        return self.x + 155

    def set_state(self, state):
        self.state = state

    def flash_error(self):
        self.error_until = time.time() + 3

    def push(self, level):
        self.level = level

    def _tick(self):
        text = {"loading": "Modell wird geladen …", "idle": self.hotkey_name + " zum Diktieren",
                "rec": "Aufnahme – klicken zum Stoppen", "busy": "Text wird erkannt …"}.get(self.state, "WISP")
        if time.time() < self.error_until:
            text = "Fehler – Einstellungen prüfen"
        self.label.configure(text=text)
        self.after(50, self._tick)
