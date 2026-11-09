"""Windows overlay implementation."""
import ctypes
import ctypes.wintypes as wt
import math
import time
import tkinter as tk
import numpy as np
from collections import deque
from PIL import Image, ImageDraw, ImageFont

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


