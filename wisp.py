"""WISP - Push-to-Talk Diktat mit OpenAI Whisper (lokal, offline).

wisp.py              -> startet WISP im Hintergrund (nur die kleine Pille am Bildschirmrand)
wisp.py --settings   -> öffnet das Einstellungsfenster
"""
import ctypes
import gc
import ctypes.wintypes as wt
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cloud
import ersetzungen
import ki
import nutzung
import postprocess

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.environ.get("APPDATA", APP_DIR), "WISP")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
LOG_PATH = os.path.join(DATA_DIR, "wisp.log")
STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup")
STARTUP_LNK = os.path.join(STARTUP_DIR, "WISP.lnk")
STARTUP_VBS = os.path.join(STARTUP_DIR, "WISP.vbs")      # alte Variante, wird beim Umschalten entfernt
ICON_ICO = os.path.join(APP_DIR, "assets", "wisp.ico")
ICON_PNG = os.path.join(APP_DIR, "assets", "wisp.png")
APP_ID = "WISP.Diktat"

SAMPLE_RATE = 16000
IDLE_UNLOAD_S = 300     # Modell nach 5 Min ohne Diktat entladen
MODELS = ["tiny", "base", "small", "medium", "large-v3", "turbo"]
LANGUAGES = {
    "Deutsch": "de", "Englisch": "en", "Automatisch": None, "Türkisch": "tr",
    "Persisch": "fa", "Arabisch": "ar", "Französisch": "fr", "Spanisch": "es",
    "Italienisch": "it", "Russisch": "ru",
}
QUICK_LANGUAGES = ["Deutsch", "Englisch", "Automatisch"]
HOTKEY_NAMES = ["Rechte Strg", "Rechte Alt (AltGr)", "Rechte Umschalt", "F8", "F9"]
HALLUCINATIONS = ("untertitel", "amara.org", "vielen dank fürs zuschauen", "thanks for watching")
DEFAULTS = {"model": "turbo", "language": "Deutsch", "device": "Auto",
            "hotkey": "Rechte Strg", "paste": True, "smart": True,
            "clipboard": False, "cloud": False, "cloud_modell": cloud.MODELL, "ki": False, "ki_anbieter": "openrouter", "history": True}


def log(msg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return dict(DEFAULTS)


def save_settings(s):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


def update_setting(field, value):
    c = load_settings()
    c[field] = value
    save_settings(c)


def load_history():
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def clear_history():
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    except Exception:
        pass


def add_history(text):
    h = load_history()
    h.insert(0, {"t": time.strftime("%d.%m.%Y %H:%M"), "text": text})
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(h[:100], f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _register_cuda_dlls():
    """Macht pip-installierte NVIDIA-DLLs (cublas/cudnn) für CTranslate2 auffindbar."""
    for base in sys.path:
        nv = os.path.join(base, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            b = os.path.join(nv, pkg, "bin")
            if os.path.isdir(b):
                os.add_dll_directory(b)
                os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")


# ======================================================================
# Einstellungsfenster (schwarz/weiß)
# ======================================================================
BG, SIDE, CARD, BORDER, HOVER = "#0b0b0b", "#101010", "#151515", "#262626", "#202020"
FG, MUTED = "#f2f2f2", "#8a8a8a"


def run_settings():
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    app = ctk.CTk(fg_color=BG)
    app.title("WISP")
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        app.after(250, lambda: app.iconbitmap(ICON_ICO))   # customtkinter setzt sonst sein eigenes Icon
    except Exception:
        pass
    app.geometry("820x600")
    app.minsize(760, 520)

    def F(size, bold=False):
        return ctk.CTkFont(family="Segoe UI", size=size, weight="bold" if bold else "normal")

    cfg = load_settings()

    # ---- Sidebar ----
    side = ctk.CTkFrame(app, width=190, fg_color=SIDE, corner_radius=0)
    side.pack(side="left", fill="y")
    side.pack_propagate(False)
    ctk.CTkLabel(side, text="wisp", font=F(26, True), text_color=FG).pack(anchor="w", padx=24, pady=(28, 24))
    pages, navs = {}, {}

    def show(name):
        for k, pg in pages.items():
            pg.pack_forget()
            navs[k].configure(fg_color="transparent", text_color=MUTED)
        pages[name].pack(side="left", fill="both", expand=True)
        navs[name].configure(fg_color=HOVER, text_color=FG)
        if name == "Verlauf":
            fill_history()
        elif name == "Nutzung":
            fill_usage()

    for name in ("Allgemein", "Verlauf", "Nutzung"):
        b = ctk.CTkButton(side, text=name, anchor="w", height=38, corner_radius=10, font=F(14),
                          fg_color="transparent", hover_color=HOVER, text_color=MUTED,
                          command=lambda n=name: show(n))
        b.pack(fill="x", padx=14, pady=2)
        navs[name] = b

    ctk.CTkButton(side, text="WISP beenden", height=36, corner_radius=10, font=F(13),
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                  text_color=FG, command=lambda: update_setting("quit", time.time())
                  ).pack(side="bottom", fill="x", padx=14, pady=20)

    # ---- Bausteine ----
    def card(parent, title):
        ctk.CTkLabel(parent, text=title, font=F(12, True), text_color=MUTED).pack(anchor="w", pady=(18, 6), padx=4)
        c = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        c.pack(fill="x")
        return c

    def row(parent, label, hint, last):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=(12, 12 if last else 0))
        left = ctk.CTkFrame(r, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text=label, font=F(14), text_color=FG).pack(anchor="w")
        if hint:
            ctk.CTkLabel(left, text=hint, font=F(12), text_color=MUTED).pack(anchor="w")
        return r

    def menu_row(parent, label, field, values, hint=None, last=False):
        r = row(parent, label, hint, last)
        var = ctk.StringVar(value=cfg[field])
        ctk.CTkOptionMenu(r, values=values, variable=var, width=190, height=34, corner_radius=10,
                          font=F(13), dropdown_font=F(13), fg_color=HOVER, button_color=HOVER,
                          button_hover_color="#2b2b2b", dropdown_fg_color="#161616",
                          dropdown_hover_color="#2b2b2b", dropdown_text_color=FG, text_color=FG,
                          command=lambda v: update_setting(field, v)).pack(side="right")

    def switch_row(parent, label, value, command, hint=None, last=False):
        r = row(parent, label, hint, last)
        sw = ctk.CTkSwitch(r, text="", width=46, progress_color="#ffffff", fg_color="#333333",
                           button_color="#111111", button_hover_color="#222222",
                           command=lambda: command(bool(sw.get())))
        sw.pack(side="right")
        sw.select() if value else sw.deselect()

    # ---- Seite: Allgemein ----
    page = ctk.CTkFrame(app, fg_color="transparent")
    pages["Allgemein"] = page
    body = ctk.CTkScrollableFrame(page, fg_color="transparent")   # scrollbar, damit alle Schalter erreichbar sind
    body.pack(fill="both", expand=True, padx=32, pady=(24, 0))
    ctk.CTkLabel(body, text="Allgemein", font=F(24, True), text_color=FG).pack(anchor="w")
    ctk.CTkLabel(body, text="Änderungen werden sofort übernommen.", font=F(13), text_color=MUTED).pack(anchor="w")

    c = card(body, "DIKTAT")
    menu_row(c, "Diktier-Taste", "hotkey", HOTKEY_NAMES, "Halten zum Sprechen, loslassen zum Einfügen")
    menu_row(c, "Sprache", "language", list(LANGUAGES))
    menu_row(c, "Modell", "model", MODELS, "„turbo“ ist schnell und genau")
    menu_row(c, "Gerät", "device", ["Auto", "GPU", "CPU"], "GPU (NVIDIA) ist deutlich schneller", last=True)

    def toggle_autostart(on):
        for old in (STARTUP_VBS,):
            if os.path.exists(old):
                os.remove(old)
        if on:
            import setup_app
            setup_app.shortcut(STARTUP_LNK, '"%s"' % os.path.join(APP_DIR, "wisp.py"), "WISP Diktat")
        elif os.path.exists(STARTUP_LNK):
            os.remove(STARTUP_LNK)

    c = card(body, "VERHALTEN")
    switch_row(c, "Text automatisch einfügen", cfg["paste"], lambda v: update_setting("paste", v),
               "Fügt den Text direkt am Cursor ein")
    switch_row(c, "Zwischenablage verwenden", cfg["clipboard"], lambda v: update_setting("clipboard", v),
               "Aus: Text wird direkt getippt und nicht kopiert")
    switch_row(c, "Verlauf speichern", cfg["history"], lambda v: update_setting("history", v),
               "Aus: Diktate werden nicht gespeichert")
    switch_row(c, "Intelligente Korrektur", cfg["smart"], lambda v: update_setting("smart", v),
               "Versprecher („nein, ich meinte …“) und Stichpunkte („neuer Stichpunkt“)")
    switch_row(c, "Mit Windows starten", os.path.exists(STARTUP_LNK) or os.path.exists(STARTUP_VBS),
               toggle_autostart, last=True)

    c = card(body, "CLOUD & ONLINE-MODELLE (OPTIONAL)")
    switch_row(c, "Cloud-Erkennung (Groq)", cfg["cloud"], lambda v: update_setting("cloud", v),
               "Spracherkennung online statt lokal (extrem schnell, kaum RAM). Standard: aus")
    menu_row(c, "Cloud-Modell", "cloud_modell", cloud.MODELLE,
             "whisper-large-v3 ist maximal genau, turbo noch schneller")
    switch_row(c, "KI-Korrektur (Online-Fallback)", cfg["ki"], lambda v: update_setting("ki", v),
               "Korrigiert schwierige Versprecher über ein Online-Sprachmodell. Standard: aus")
    menu_row(c, "KI-Anbieter", "ki_anbieter", list(ki.ANBIETER),
             "Groq nutzt denselben Schlüssel wie die Cloud-Erkennung")

    def key_row(parent, label, key_env, placeholder, url, hint, last=False):
        r = row(parent, label, hint, last)
        right = ctk.CTkFrame(r, fg_color="transparent")
        right.pack(side="right")
        ent = ctk.CTkEntry(right, width=180, height=32, corner_radius=8, font=F(12),
                           fg_color=HOVER, border_color=BORDER, text_color=FG,
                           placeholder_text=placeholder, show="•")
        ent.pack(side="left", padx=(0, 6))
        aktuell = ki.schluessel(key_env)
        if aktuell:
            ent.insert(0, aktuell)
        btn = ctk.CTkButton(right, text="Speichern", width=78, height=32, corner_radius=8, font=F(12),
                            fg_color="#ffffff", text_color="#000000", hover_color="#d9d9d9")

        def save(_e=None):
            ki.speichere_schluessel(key_env, ent.get())
            update_setting("key_updated", time.time())
            btn.configure(text="Gespeichert ✓")
            app.after(1500, lambda: btn.configure(text="Speichern"))

        btn.configure(command=save)
        ent.bind("<Return>", save)
        btn.pack(side="left", padx=(0, 6))
        import webbrowser
        ctk.CTkButton(right, text="Key holen ↗", width=86, height=32, corner_radius=8, font=F(12),
                      fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                      text_color=FG, command=lambda: webbrowser.open(url)).pack(side="left")

    key_row(c, "Groq API-Key", "GROQ_API_KEY", "gsk_...", "https://console.groq.com/keys",
            "Kostenlos bei console.groq.com (für Cloud-Erkennung & Groq-KI)")
    key_row(c, "OpenRouter API-Key", "OPENROUTER_API_KEY", "sk-or-...", "https://openrouter.ai/keys",
            "Optional, falls KI-Anbieter auf „openrouter“ steht", last=True)

    def open_textfile(path, default_text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(default_text)
        os.startfile(path)

    c = card(body, "WÖRTERBUCH & ERSETZUNGEN")
    r_w = row(c, "Eigene Wörter & Namen (woerter.txt)",
              "Hilft der Erkennung bei Eigennamen und Fachbegriffen (ein Wort pro Zeile)", False)
    ctk.CTkButton(r_w, text="Bearbeiten", width=110, height=32, corner_radius=8, font=F(12),
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                  text_color=FG, command=lambda: open_textfile(
                      cloud.WOERTER_DATEI,
                      "# Ein Wort oder Name pro Zeile. Hilft der Cloud-Erkennung, sie richtig zu schreiben.\n"
                  )).pack(side="right")
    r_e = row(c, "Feste Ersetzungen (ersetzungen.txt)",
              "Ersetzt typische Hörfehler automatisch (Format: falsch = richtig)", True)
    ctk.CTkButton(r_e, text="Bearbeiten", width=110, height=32, corner_radius=8, font=F(12),
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                  text_color=FG, command=lambda: open_textfile(
                      ersetzungen.DATEI,
                      "# falsch = richtig  (eine Regel pro Zeile, Gross-/Kleinschreibung egal, nur ganze Woerter)\n"
                      "cloud code = Claude Code\n"
                  )).pack(side="right")
    ctk.CTkFrame(body, height=24, fg_color="transparent").pack()

    # ---- Seite: Verlauf ----
    page = ctk.CTkFrame(app, fg_color="transparent")
    pages["Verlauf"] = page
    body = ctk.CTkFrame(page, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=32, pady=(24, 16))
    head = ctk.CTkFrame(body, fg_color="transparent")
    head.pack(fill="x")
    ctk.CTkLabel(head, text="Verlauf", font=F(24, True), text_color=FG).pack(side="left")
    ctk.CTkButton(head, text="Aktualisieren", width=110, height=32, corner_radius=10, font=F(13),
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                  text_color=FG, command=lambda: fill_history()).pack(side="right")

    def leeren():
        clear_history()
        fill_history()

    ctk.CTkButton(head, text="Leeren", width=90, height=32, corner_radius=10, font=F(13),
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                  text_color=FG, command=leeren).pack(side="right", padx=(0, 8))
    lst = ctk.CTkScrollableFrame(body, fg_color="transparent")
    lst.pack(fill="both", expand=True, pady=(12, 0))

    def fill_history():
        for w in lst.winfo_children():
            w.destroy()
        items = load_history()
        if not items:
            ctk.CTkLabel(lst, text="Noch nichts diktiert.", font=F(14), text_color=MUTED).pack(pady=40)
        for it in items:
            cd = ctk.CTkFrame(lst, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
            cd.pack(fill="x", pady=5)
            top = ctk.CTkFrame(cd, fg_color="transparent")
            top.pack(fill="x", padx=16, pady=(10, 0))
            ctk.CTkLabel(top, text=it["t"], font=F(12), text_color=MUTED).pack(side="left")

            def copy(t=it["text"]):
                app.clipboard_clear()
                app.clipboard_append(t)

            ctk.CTkButton(top, text="Kopieren", width=80, height=26, corner_radius=8, font=F(12),
                          fg_color="#ffffff", text_color="#000000", hover_color="#d9d9d9",
                          command=copy).pack(side="right")
            ctk.CTkLabel(cd, text=it["text"], font=F(14), text_color=FG, justify="left", anchor="w",
                         wraplength=520).pack(fill="x", padx=16, pady=(6, 12))

    # ---- Seite: Nutzung ----
    page = ctk.CTkFrame(app, fg_color="transparent")
    pages["Nutzung"] = page
    body = ctk.CTkScrollableFrame(page, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=32, pady=(24, 0))
    head = ctk.CTkFrame(body, fg_color="transparent")
    head.pack(fill="x")
    ctk.CTkLabel(head, text="Nutzung", font=F(24, True), text_color=FG).pack(side="left")
    ctk.CTkButton(head, text="Aktualisieren", width=110, height=32, corner_radius=10, font=F(13),
                  fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
                  text_color=FG, command=lambda: fill_usage()).pack(side="right")
    usage_box = ctk.CTkFrame(body, fg_color="transparent")
    usage_box.pack(fill="x")

    def fill_usage():
        for w in usage_box.winfo_children():
            w.destroy()
        eintraege = nutzung.lade()
        h = nutzung.heute(eintraege)
        ctk.CTkLabel(usage_box, text="Von WISP gezählt (Schätzung). Nutzung außerhalb von WISP, z. B. im "
                     "Groq-Playground, ist nicht enthalten.", font=F(12), text_color=MUTED, justify="left",
                     wraplength=520).pack(anchor="w", pady=(2, 0))

        c = card(usage_box, "HEUTE – GROQ CLOUD (FREE-TARIF)")
        for label, wert, limit, text in (
                ("Audio heute", h["audio_s"], nutzung.LIMIT_AUDIO_TAG,
                 f"{nutzung.dauer(h['audio_s'])} von {nutzung.dauer(nutzung.LIMIT_AUDIO_TAG)}"),
                ("Audio letzte Stunde", h["stunde_s"], nutzung.LIMIT_AUDIO_STUNDE,
                 f"{nutzung.dauer(h['stunde_s'])} von {nutzung.dauer(nutzung.LIMIT_AUDIO_STUNDE)}"),
                ("Anfragen heute", h["anfragen"], nutzung.LIMIT_ANFRAGEN_TAG,
                 f"{h['anfragen']} von {nutzung.LIMIT_ANFRAGEN_TAG}")):
            r = ctk.CTkFrame(c, fg_color="transparent")
            r.pack(fill="x", padx=18, pady=(12, 4))
            ctk.CTkLabel(r, text=label, font=F(14), text_color=FG).pack(side="left")
            ctk.CTkLabel(r, text=text, font=F(13), text_color=MUTED).pack(side="right")
            bar = ctk.CTkProgressBar(c, height=8, progress_color="#ffffff", fg_color="#333333")
            bar.pack(fill="x", padx=18, pady=(0, 8))
            bar.set(min(1.0, wert / limit))
        stand = nutzung.groq_stand(eintraege)
        gemeldet = ("Noch keine Rückmeldung von Groq." if not stand else
                    f"Groq meldet: {stand['rest']} von {stand['limit']} Anfragen übrig "
                    f"(Stand {time.strftime('%d.%m. %H:%M', time.localtime(stand['t']))}).")
        ctk.CTkLabel(c, text=gemeldet, font=F(13), text_color=FG).pack(anchor="w", padx=18, pady=(4, 0))
        ctk.CTkLabel(c, text="Limits laut Groq-Konsole (Organization → Limits). Groq meldet nur die Anfragen, "
                     "nicht die Audiosekunden.", font=F(12), text_color=MUTED, justify="left",
                     wraplength=520).pack(anchor="w", padx=18, pady=(2, 12))

        c = card(usage_box, "LETZTE TAGE")
        tage = nutzung.pro_tag(eintraege)
        if not tage:
            ctk.CTkLabel(c, text="Noch keine Diktate gezählt.", font=F(14), text_color=MUTED).pack(pady=24)
            return
        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=12)
        kopf = ("Datum", "Diktate", "Audio", "Cloud", "Lokal", "KI-Tokens")
        for col, text in enumerate(kopf):
            ctk.CTkLabel(grid, text=text, font=F(12, True), text_color=MUTED, anchor="w"
                         ).grid(row=0, column=col, sticky="w", padx=(0, 18), pady=(0, 6))
        for i, z in enumerate(tage, 1):
            werte = (z["datum"], z["diktate"], nutzung.dauer(z["audio_s"]), z["cloud"], z["lokal"],
                     z["ki_tokens"] or "–")
            for col, wert in enumerate(werte):
                ctk.CTkLabel(grid, text=str(wert), font=F(13), text_color=FG, anchor="w"
                             ).grid(row=i, column=col, sticky="w", padx=(0, 18), pady=2)

    show("Allgemein")
    app.mainloop()


# ======================================================================
# Whisper-Engine
# ======================================================================
class Engine:
    def __init__(self):
        self.model = None
        self.device = None
        self.lock = threading.Lock()

    def load(self, name, dev):
        from faster_whisper import WhisperModel
        attempts = {"CPU": [("cpu", "int8")], "GPU": [("cuda", "float16")]}.get(
            dev, [("cuda", "float16"), ("cpu", "int8")])
        last = None
        with self.lock:
            self.model = None
            for device, ctype in attempts:
                try:
                    m = WhisperModel(name, device=device, compute_type=ctype)
                    list(m.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), beam_size=1)[0])
                    self.model, self.device = m, device
                    return device
                except Exception as e:
                    log(f"Laden auf {device} fehlgeschlagen: {e}")
                    last = e
        raise last

    def unload(self):
        """Gibt das Modell frei (RAM/VRAM); load() holt es bei Bedarf zurück."""
        with self.lock:
            self.model = None
        gc.collect()

    def transcribe(self, audio, language):
        with self.lock:
            if self.model is None:
                return ""
            segs, _ = self.model.transcribe(
                audio, language=language, beam_size=1, vad_filter=True,
                condition_on_previous_text=False, without_timestamps=True, temperature=0.0)
            text = " ".join(s.text.strip() for s in segs).strip()
            return "" if any(h in text.lower() for h in HALLUCINATIONS) else text


# ======================================================================
# Pille (Per-Pixel-Alpha-Overlay wie bei Wispr Flow)
# ======================================================================
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_void_p, ctypes.c_void_p, wt.HDC,
                                       ctypes.c_void_p, wt.COLORREF, ctypes.c_void_p, wt.DWORD]
user32.UpdateLayeredWindow.restype = wt.BOOL
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


def _font(name, size):
    try:
        return ImageFont.truetype(name, size)
    except Exception:
        return ImageFont.load_default()


class Pill(tk.Toplevel):
    LW, LH = 320, 100         # logische Größe der Zeichenfläche
    S = 3                     # Supersampling für glatte Kanten
    BARS = 11
    CY = 24                   # Abstand Pillenmitte zum unteren Rand
    # Hover-Layout (logisch, relativ zur Mitte): Mikrofon-Button und Menü-Button
    MIC = (-33, 7)
    MORE_X, R = 22, 10

    def __init__(self, master, on_mic, on_more, on_stop):
        super().__init__(master)
        self.on_mic, self.on_more, self.on_stop = on_mic, on_more, on_stop
        self.scale = max(1.0, user32.GetDpiForSystem() / 96.0) if hasattr(user32, "GetDpiForSystem") else 1.0
        self.W, self.H = int(self.LW * self.scale), int(self.LH * self.scale)
        self.state = "loading"      # loading | idle | rec | busy
        self.hotkey_name = "Rechte Strg"
        self.error_until = 0.0
        self.w, self.h = 40.0, 9.0
        self.hover = False
        self.hover_btn = None
        self.menu_open = False
        self.levels = deque([0.0] * self.BARS, maxlen=self.BARS)
        self.smooth = [0.0] * self.BARS
        self.dirty = True
        sc = self.scale * self.S
        self.f_reg = _font("segoeui.ttf", int(12 * sc))
        self.f_bold = _font("segoeuib.ttf", int(12 * sc))

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        rect = wt.RECT()
        user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)  # Arbeitsbereich ohne Taskleiste
        self.x = (rect.left + rect.right - self.W) // 2
        self.y = rect.bottom - self.H - int(6 * self.scale)
        self.geometry(f"{self.W}x{self.H}+{self.x}+{self.y}")
        self.update()
        self.hwnd = user32.GetAncestor(self.winfo_id(), 2) or self.winfo_id()
        style = user32.GetWindowLongW(self.hwnd, -20)
        user32.SetWindowLongW(self.hwnd, -20, style | 0x80000 | 0x08000000 | 0x80)  # LAYERED|NOACTIVATE|TOOLWINDOW

        self.hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), self.W, -self.H, 1, 32, 0)
        self.bits = ctypes.c_void_p()
        self.hbmp = gdi32.CreateDIBSection(self.hdc_mem, ctypes.byref(bmi), 0, ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.hdc_mem, self.hbmp)

        self.bind("<Motion>", self._motion)
        self.bind("<Enter>", self._motion)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.bind("<Button-3>", lambda e: self.on_more())
        self.after(33, self._tick)

    # ---- Zustand ----
    def set_state(self, s):
        self.state = s
        self.dirty = True

    def flash_error(self):
        self.error_until = time.time() + 2.0
        self.dirty = True

    def push(self, level):
        self.levels.append(level)

    @property
    def top_screen(self):
        """Obere Kante der aufgeklappten Pille in Bildschirmkoordinaten (für das Menü)."""
        return self.y + int((self.LH - self.CY - 13) * self.scale)

    @property
    def menu_center_x(self):
        return self.x + self.W // 2

    # ---- Maus ----
    def _hit(self, e):
        x = e.x / self.scale - self.LW / 2
        y = e.y / self.scale - (self.LH - self.CY)
        if self.MIC[0] <= x <= self.MIC[1] and abs(y) <= 10:
            return "mic"
        if math.hypot(x - self.MORE_X, y) <= self.R + 2:
            return "more"
        return None

    def _motion(self, e):
        btn = self._hit(e)
        if not self.hover or btn != self.hover_btn:
            self.hover, self.hover_btn, self.dirty = True, btn, True

    def _leave(self, e):
        self.hover, self.hover_btn, self.dirty = False, None, True

    def _click(self, e):
        if self.state == "rec":
            self.on_stop()
        elif self.state == "idle":
            btn = self._hit(e)
            if btn == "mic":
                self.on_mic()
            elif btn == "more":
                self.on_more()

    # ---- Zeichnen ----
    def _tick(self):
        now = time.time()
        expanded = self.hover and self.state == "idle"
        if self.state == "rec":
            tw, th = 112.0, 38.0
        elif self.state == "busy":
            tw, th = 62.0, 24.0
        elif expanded:
            tw, th = 74.0, 26.0
        else:
            tw, th = 40.0, 9.0
        moving = abs(self.w - tw) > 0.3 or abs(self.h - th) > 0.3
        if moving:
            self.w += (tw - self.w) * 0.35
            self.h += (th - self.h) * 0.35
            self._was_moving = True
        elif getattr(self, "_was_moving", False):
            self._was_moving = False
            self.dirty = True       # Animation zu Ende: einmal mit Buttons/Tooltip neu zeichnen
        animated = self.state in ("rec", "busy", "loading") or now < self.error_until
        if moving or animated or self.dirty:
            self._render(now, expanded and not moving)
            self.dirty = False
            self.after(33, self._tick)
        else:
            self.after(100, self._tick)     # Leerlauf: seltener prüfen

    def _tooltip(self, d, cx, cy, sc):
        if self.menu_open:
            return
        if self.hover_btn == "mic":
            parts = [("Diktieren  ", self.f_reg), (self.hotkey_name, self.f_bold)]
        elif self.hover_btn == "more":
            parts = [("Menü", self.f_reg)]
        else:
            return
        pad = 16 * sc
        tw = sum(d.textlength(t, font=f) for t, f in parts)
        bw, bh = tw + 2 * pad, 28 * sc
        ty = cy - 13 * sc - 6 * sc - bh / 2
        d.rounded_rectangle([cx - bw / 2, ty - bh / 2, cx + bw / 2, ty + bh / 2], radius=bh / 2,
                            fill=(0, 0, 0, 255), outline=(48, 48, 48, 255), width=int(sc))
        x = cx - tw / 2
        for t, f in parts:
            d.text((x, ty), t, font=f, fill=(255, 255, 255, 255), anchor="lm")
            x += d.textlength(t, font=f)

    def _render(self, now, show_buttons):
        S, sc = self.S, self.scale * self.S
        img = Image.new("RGBA", (self.W * S, self.H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, cy = self.W * S / 2, self.H * S - self.CY * sc
        # Fast unsichtbare Fläche (Alpha 1), damit Hover/Klick auch knapp neben der Pille greifen
        d.rectangle([cx - 52 * sc, cy - 19 * sc, cx + 52 * sc, cy + 19 * sc], fill=(0, 0, 0, 1))
        w, h = self.w * sc, self.h * sc
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]

        if self.state == "rec":
            d.rounded_rectangle(box, radius=h / 2, fill=(0, 0, 0, 255), outline=(40, 40, 40, 255), width=int(sc))
            bw, gap = 3.2 * sc, 3.6 * sc
            total = self.BARS * bw + (self.BARS - 1) * gap
            x = cx - total / 2
            for i in range(self.BARS):
                self.smooth[i] += (self.levels[i] - self.smooth[i]) * 0.5
                env = 0.55 + 0.45 * math.sin(math.pi * (i + 0.5) / self.BARS)
                lv = min(1.0, (self.smooth[i] * 14) ** 0.65) * env
                bh = (4 + lv * 22) * sc
                d.rounded_rectangle([x, cy - bh / 2, x + bw, cy + bh / 2], radius=bw / 2, fill=(255, 255, 255, 255))
                x += bw + gap
        elif self.state == "busy":
            d.rounded_rectangle(box, radius=h / 2, fill=(0, 0, 0, 255), outline=(40, 40, 40, 255), width=int(sc))
            for i in range(3):
                a = 0.5 + 0.5 * math.sin(now * 7 - i * 0.9)
                r = (2.2 + 1.2 * a) * sc
                px = cx + (i - 1) * 11 * sc
                g = int(110 + 145 * a)
                d.ellipse([px - r, cy - r, px + r, cy + r], fill=(g, g, g, 255))
        elif self.hover:
            d.rounded_rectangle(box, radius=h / 2, fill=(0, 0, 0, 255), outline=(48, 48, 48, 255), width=int(sc))
            if show_buttons:
                self._buttons(d, cx, cy, sc)
                self._tooltip(d, cx, cy, sc)
        else:
            if now < self.error_until:
                outline = (235, 80, 80, 255)
            elif self.state == "loading":
                a = 0.5 + 0.5 * math.sin(now * 4)
                outline = (int(120 + 100 * a), int(120 + 80 * a), 90, 255)
            else:
                outline = (150, 150, 150, 255)
            d.rounded_rectangle(box, radius=h / 2, fill=(18, 18, 18, 215), outline=outline, width=max(2, int(1.3 * sc)))

        # Herunterrechnen (Box-Filter) und direkt als vormultipliziertes BGRA an Windows übergeben
        small = img.reduce(S).convert("RGBa")
        bgra = np.ascontiguousarray(np.asarray(small)[..., [2, 1, 0, 3]])
        ctypes.memmove(self.bits, bgra.ctypes.data, bgra.nbytes)

        pt_dst = wt.POINT(self.x, self.y)
        size = wt.SIZE(self.W, self.H)
        pt_src = wt.POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)  # AC_SRC_OVER, AC_SRC_ALPHA
        user32.UpdateLayeredWindow(self.hwnd, self.hdc_screen, ctypes.byref(pt_dst), ctypes.byref(size),
                                   self.hdc_mem, ctypes.byref(pt_src), 0, ctypes.byref(blend), 2)
        if int(now * 2) % 4 == 0:   # Taskleiste soll die Pille nicht überdecken
            self.attributes("-topmost", True)

    def _buttons(self, d, cx, cy, sc):
        white = (255, 255, 255, 255)
        # Mikrofon-Button
        x0, x1 = cx + self.MIC[0] * sc, cx + self.MIC[1] * sc
        fill = (66, 66, 66, 255) if self.hover_btn == "mic" else (40, 40, 40, 255)
        d.rounded_rectangle([x0, cy - 10 * sc, x1, cy + 10 * sc], radius=10 * sc, fill=fill)
        mx = (x0 + x1) / 2
        d.rounded_rectangle([mx - 2.5 * sc, cy - 6.3 * sc, mx + 2.5 * sc, cy + 2 * sc], radius=2.5 * sc, fill=white)
        d.arc([mx - 5 * sc, cy - 4.2 * sc, mx + 5 * sc, cy + 5 * sc], 0, 180, fill=white, width=int(1.2 * sc))
        d.line([mx, cy + 5 * sc, mx, cy + 7.2 * sc], fill=white, width=int(1.2 * sc))
        d.line([mx - 2.3 * sc, cy + 7.2 * sc, mx + 2.3 * sc, cy + 7.2 * sc], fill=white, width=int(1.2 * sc))
        # Menü-Button (drei Punkte)
        bx = cx + self.MORE_X * sc
        r = self.R * sc
        fill = (66, 66, 66, 255) if self.hover_btn == "more" else (40, 40, 40, 255)
        d.ellipse([bx - r, cy - r, bx + r, cy + r], fill=fill, outline=(85, 85, 85, 255), width=int(sc))
        for k in (-1, 0, 1):
            dx = bx + k * 4 * sc
            d.ellipse([dx - 1.3 * sc, cy - 1.3 * sc, dx + 1.3 * sc, cy + 1.3 * sc], fill=white)


# ======================================================================
# Menü (schwarz/weiß, öffnet über der Pille)
# ======================================================================
class PopupMenu(tk.Toplevel):
    W = 244

    def __init__(self, master, pill, cfg, actions):
        super().__init__(master)
        self.pill = pill
        sc = pill.scale
        px = lambda n: int(n * sc)
        font = lambda n, b=False: ("Segoe UI", -px(n), "bold" if b else "normal")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#2a2a2a")
        inner = tk.Frame(self, bg="#0f0f0f")
        inner.pack(padx=1, pady=1, fill="both", expand=True)

        def close_then(cmd):
            def run(_e=None):
                self.close()
                if cmd:
                    master.after(120, cmd)
            return run

        def item(text, cmd, right="", muted=False):
            f = tk.Frame(inner, bg="#0f0f0f", height=px(36))
            f.pack(fill="x", padx=px(6), pady=px(1))
            f.pack_propagate(False)
            l = tk.Label(f, text=text, bg="#0f0f0f", fg="#8a8a8a" if muted else "#f2f2f2",
                         font=font(13), anchor="w")
            l.pack(side="left", padx=px(10))
            r = tk.Label(f, text=right, bg="#0f0f0f", fg="#ffffff", font=font(13, True))
            r.pack(side="right", padx=px(10))
            widgets = (f, l, r)

            def enter(_e):
                for w in widgets:
                    w.configure(bg="#222222")

            def leave(_e):
                for w in widgets:
                    w.configure(bg="#0f0f0f")

            for w in widgets:
                w.bind("<Enter>", enter)
                w.bind("<Leave>", leave)
                w.bind("<Button-1>", close_then(cmd))

        def header(text):
            tk.Label(inner, text=text, bg="#0f0f0f", fg="#6b6b6b", font=font(10, True),
                     anchor="w").pack(fill="x", padx=px(16), pady=(px(10), px(2)))

        def sep():
            tk.Frame(inner, bg="#242424", height=1).pack(fill="x", padx=px(10), pady=px(6))

        header("SPRACHE")
        for lang in QUICK_LANGUAGES:
            item(lang, (lambda l=lang: actions["language"](l)), "✓" if cfg["language"] == lang else "")
        sep()
        item("Letzten Text einfügen", actions["paste_last"])
        item("Verlauf speichern", actions["history"], "✓" if cfg.get("history", True) else "")
        item("Verlauf & Einstellungen", actions["settings"])
        sep()
        item("WISP beenden", actions["quit"], muted=True)
        tk.Frame(inner, height=px(4), bg="#0f0f0f").pack()

        self.update_idletasks()
        w, h = px(self.W), self.winfo_reqheight()
        x = min(pill.menu_center_x - w // 2, self.winfo_screenwidth() - w - px(8))
        y = pill.top_screen - h - px(10)
        self.geometry(f"{w}x{h}+{x}+{max(0, y)}")
        try:  # Windows 11: runde Ecken
            hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2) or self.winfo_id()
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
        except Exception:
            pass
        self.focus_force()
        self.bind("<FocusOut>", lambda e: self.after(80, self._maybe_close))
        self.bind("<Escape>", lambda e: self.close())
        self.after(400, self._watch)
        self.outside = 0
        pill.menu_open = True
        pill.dirty = True

    def _maybe_close(self):
        try:
            if self.focus_displayof() is None:
                self.close()
        except Exception:
            pass

    def _watch(self):
        """Schließt das Menü, wenn die Maus länger weit weg ist."""
        try:
            px, py = self.winfo_pointerxy()
            x0, y0 = self.winfo_rootx(), self.winfo_rooty()
            near = (x0 - 60 <= px <= x0 + self.winfo_width() + 60 and
                    y0 - 40 <= py <= self.pill.y + self.pill.H + 10)
            self.outside = 0 if near else self.outside + 1
            if self.outside >= 4:
                return self.close()
            self.after(400, self._watch)
        except Exception:
            pass

    def close(self):
        self.pill.menu_open = False
        self.pill.dirty = True
        try:
            self.destroy()
        except Exception:
            pass


# ======================================================================
# Hauptprogramm (läuft unsichtbar, nur Pille)
# ======================================================================
class Wisp:
    def __init__(self):
        import sounddevice as sd
        from pynput import keyboard
        self.sd, self.keyboard = sd, keyboard
        K = keyboard.Key
        self.hotkeys = {
            "Rechte Strg": (K.ctrl_r,), "Rechte Alt (AltGr)": (K.alt_r, K.alt_gr),
            "Rechte Umschalt": (K.shift_r,), "F8": (K.f8,), "F9": (K.f9,),
        }
        self.ctrl = K.ctrl
        self.kb = keyboard.Controller()
        self.cfg = load_settings()
        self.started = time.time()
        self.loaded_for = None
        self.engine = Engine()
        self.events = queue.Queue()
        self.ready = False
        self.asleep = False
        self.last_source = "lokal"
        self.last_use = time.time()
        self.recording = False
        self.handsfree = False
        self.held = False
        self.chunks = []
        self.stream = None
        self.t0 = 0.0
        self.cfg_mtime = 0
        self.menu = None

        self.root = tk.Tk()
        self.root.withdraw()
        self.pill = Pill(self.root, self.mic_clicked, self.toggle_menu, self._stop_record)
        self.pill.hotkey_name = self.cfg["hotkey"]

        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()
        self._start_tray()
        self.root.after(30, self._poll)
        self.root.after(1000, self._watch_settings)
        self.reload_model()

    # ---- Menü & Aktionen ----
    def toggle_menu(self):
        if self.menu is not None:
            try:
                self.menu.close()
            except Exception:
                pass
            self.menu = None
            return
        actions = {
            "language": lambda l: update_setting("language", l),
            "paste_last": self.paste_last,
            "history": self.toggle_history,
            "settings": self.open_settings,
            "quit": self.quit,
        }
        self.menu = PopupMenu(self.root, self.pill, self.cfg, actions)
        self.menu.bind("<Destroy>", lambda e: setattr(self, "menu", None) if e.widget is self.menu else None)

    def mic_clicked(self):
        if self.recording:
            self._stop_record()
        elif self.ready or self.asleep:
            self._wake()
            self._start_record(handsfree=True)
        else:
            self.pill.flash_error()

    def _wake(self):
        """Lädt das entladene Modell neu (thread-sicher: die Arbeit läuft im Tk-Thread)."""
        self.last_use = time.time()
        if self.asleep:
            self.asleep = False
            self.events.put(("wake", None))

    def _idle_check(self):
        if (self.ready and not self.cfg.get("cloud") and not self.recording and self.pill.state == "idle"
                and time.time() - self.last_use > IDLE_UNLOAD_S):
            self.ready = False
            self.asleep = True
            self.engine.unload()
            log("Modell nach Leerlauf entladen")

    def toggle_history(self):
        update_setting("history", not self.cfg.get("history", True))

    def paste_last(self):
        h = load_history()
        if h:
            self._paste(h[0]["text"])

    def _start_tray(self):
        """Symbol im Infobereich der Taskleiste (zeigt, dass WISP läuft) mit Einstellungen/Beenden."""
        try:
            import pystray
            menu = pystray.Menu(
                pystray.MenuItem("Einstellungen", lambda: self.events.put(("settings", None)), default=True),
                pystray.MenuItem("WISP beenden", lambda: self.events.put(("quit", None))),
            )
            self.tray = pystray.Icon("WISP", Image.open(ICON_PNG), "WISP – halte die Diktier-Taste", menu)
            self.tray.run_detached()
        except Exception as e:
            self.tray = None
            log(f"Tray-Icon nicht verfügbar: {e}")

    def open_settings(self):
        pyw = os.path.join(APP_DIR, ".venv", "Scripts", "pythonw.exe")
        if not os.path.exists(pyw):
            pyw = sys.executable
        subprocess.Popen([pyw, os.path.join(APP_DIR, "wisp.py"), "--settings"], cwd=APP_DIR)

    def quit(self):
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        self.listener.stop()
        self.root.destroy()

    # ---- Einstellungen live übernehmen ----
    def _watch_settings(self):
        try:
            m = os.path.getmtime(SETTINGS_PATH)
            if m != self.cfg_mtime:
                self.cfg_mtime = m
                self.cfg = load_settings()
                self.pill.hotkey_name = self.cfg["hotkey"]
                self.pill.dirty = True
                if self.cfg.get("quit", 0) > self.started:
                    return self.quit()
                target = "cloud" if self.cfg.get("cloud") else (self.cfg["model"], self.cfg["device"])
                if target != self.loaded_for:
                    self.asleep = False
                    self.reload_model()
        except FileNotFoundError:
            pass
        self._idle_check()
        self.root.after(1000, self._watch_settings)

    def reload_model(self):
        if self.cfg.get("cloud"):          # Cloud: kein lokales Modell im Speicher
            self.engine.unload()
            self.asleep = False
            self.ready = True
            self.loaded_for = "cloud"
            self.pill.set_state("idle")
            return
        self.ready = False
        self.pill.set_state("loading")
        name, dev = self.cfg["model"], self.cfg["device"]
        self.loaded_for = (name, dev)

        def work():
            try:
                self.engine.load(name, dev)
                self.events.put(("ready", None))
            except Exception as e:
                log(f"Modell konnte nicht geladen werden: {e}")
                self.events.put(("error", None))

        threading.Thread(target=work, daemon=True).start()

    # ---- Hotkey / Aufnahme ----
    def _is_hotkey(self, key):
        return key in self.hotkeys.get(self.cfg["hotkey"], ())

    def _on_press(self, key):
        if self._is_hotkey(key) and not self.held:
            self.held = True
            if self.recording and self.handsfree:
                self._stop_record()
            elif (self.ready or self.asleep) and not self.recording:
                self._wake()
                self._start_record()

    def _on_release(self, key):
        if self._is_hotkey(key):
            self.held = False
            if self.recording and not self.handsfree:
                self._stop_record()

    def _audio_cb(self, data, frames, t, status):
        self.chunks.append(data[:, 0].copy())
        self.events.put(("level", float(np.sqrt(np.mean(data ** 2)))))

    def _start_record(self, handsfree=False):
        self.chunks = []
        try:
            self.stream = self.sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                              blocksize=800, callback=self._audio_cb)
            self.stream.start()
        except Exception as e:
            log(f"Mikrofon-Fehler: {e}")
            self.events.put(("error", None))
            return
        self.recording = True
        self.handsfree = handsfree
        self.t0 = time.time()
        self.events.put(("state", "rec"))

    def _stop_record(self):
        if not self.recording:
            return
        self.recording = False
        self.handsfree = False
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        self.last_use = time.time()
        chunks, self.chunks = self.chunks, []
        if not chunks or time.time() - self.t0 < 0.35:
            self.events.put(("state", "idle"))
            return
        audio = np.concatenate(chunks)
        if float(np.abs(audio).max()) < 0.01:
            self.events.put(("state", "idle"))
            return
        self.events.put(("state", "busy"))
        threading.Thread(target=self._final, args=(audio,), daemon=True).start()

    def _transcribe(self, audio, lang):
        """Cloud, wenn eingeschaltet; bei Fehler oder ohne Cloud das lokale Modell."""
        if self.cfg.get("cloud"):
            try:
                txt = cloud.transkribiere(audio, SAMPLE_RATE, lang, self.cfg.get("cloud_modell"))
                self.last_source = "cloud"
                return "" if any(h in txt.lower() for h in HALLUCINATIONS) else txt
            except Exception as e:
                log(f"Cloud fehlgeschlagen, lokal: {e}")
        if self.engine.model is None:      # Modell war entladen: jetzt nachladen
            self.engine.load(self.cfg["model"], self.cfg["device"])
        self.last_source = "lokal"
        return self.engine.transcribe(audio, lang)

    def _final(self, audio):
        t = time.time()
        ki_tokens = 0
        try:
            txt = ersetzungen.ersetze(self._transcribe(audio, LANGUAGES[self.cfg["language"]]))
            if txt and self.cfg.get("smart", True):
                raw, txt = txt, postprocess.process(txt)
                if txt != raw:
                    log(f"smart: {raw!r} -> {txt!r}")
                if self.cfg.get("ki") and ki.braucht_ki(txt):
                    ki_txt = ki.korrigiere(txt, self.cfg.get("ki_anbieter", "openrouter"))
                    ki_tokens = ki.letzte_tokens
                    log(f"ki: {txt!r} -> {ki_txt!r}" if ki_txt else "ki: keine Antwort, Regeltext bleibt")
                    txt = ki_txt or txt
            log(f"{len(audio) / SAMPLE_RATE:.1f}s Audio -> {time.time() - t:.2f}s ({self.last_source})")
            self.last_use = time.time()
            try:
                nutzung.schreibe({"quelle": self.last_source, "audio_s": round(len(audio) / SAMPLE_RATE, 1),
                                  "dauer_s": round(time.time() - t, 2), "ki_tokens": ki_tokens,
                                  "rl_limit": cloud.letzte_limits.get("limit") if self.last_source == "cloud" else None,
                                  "rl_rest": cloud.letzte_limits.get("rest") if self.last_source == "cloud" else None,
                                  "modell": self.cfg.get("cloud_modell") if self.last_source == "cloud"
                                  else self.cfg["model"]})
            except Exception as e:
                log(f"Nutzung nicht gespeichert: {e}")
            self.events.put(("result", txt))
        except Exception as e:
            log(f"Transkription fehlgeschlagen: {e}")
            self.events.put(("error", None))

    # ---- Tk-Thread ----
    def _poll(self):
        try:
            while True:
                kind, val = self.events.get_nowait()
                if kind == "level":
                    self.pill.push(val)
                elif kind == "state":
                    self.pill.set_state(val)
                elif kind == "wake":
                    self.reload_model()
                elif kind == "ready":
                    self.ready = True
                    if self.pill.state == "loading":   # nicht eine laufende Aufnahme überschreiben
                        self.pill.set_state("idle")
                elif kind == "result":
                    self.pill.set_state("idle")
                    if val:
                        if self.cfg.get("history", True):
                            add_history(val)
                        if self.cfg["paste"]:
                            self._paste(val)
                elif kind == "settings":
                    self.open_settings()
                elif kind == "quit":
                    return self.quit()
                elif kind == "error":
                    self.pill.set_state("idle" if self.ready else "loading")
                    self.pill.flash_error()
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    def _paste(self, txt):
        if not self.cfg.get("clipboard", False):
            return self._type(txt)
        try:
            old = self.root.clipboard_get()
        except Exception:
            old = None
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.root.update()
        self.kb.press(self.ctrl)
        self.kb.press("v")
        self.kb.release("v")
        self.kb.release(self.ctrl)
        if old is not None:
            def restore():
                self.root.clipboard_clear()
                self.root.clipboard_append(old)
            self.root.after(500, restore)


    def _type(self, txt):
        """Tippt den Text direkt ein (Unicode-Tastenanschläge) - die Zwischenablage bleibt unberührt."""
        Key = self.keyboard.Key
        for i, line in enumerate(txt.split("\n")):
            if i:   # Umschalt+Enter: neue Zeile, ohne in Chat-Fenstern abzusenden
                with self.kb.pressed(Key.shift):
                    self.kb.tap(Key.enter)
            if line:
                self.kb.type(line)


def single_instance():
    ctypes.windll.kernel32.CreateMutexW(None, False, "WISP_single_instance")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    if "--settings" in sys.argv:
        run_settings()
    elif single_instance():
        _register_cuda_dlls()
        try:
            Wisp().root.mainloop()
        except Exception as e:
            log(f"Abbruch: {e!r}")
            raise
    else:
        run_settings()      # läuft schon: Doppelklick öffnet das Einstellungsfenster
