"""Feste Ersetzungen nach der Erkennung (gilt für lokal und Cloud).

Datei: WISP-Datenordner (APPDATA/WISP/ersetzungen.txt), eine Regel pro Zeile:  falsch = richtig
Zeilen mit # sind Kommentare. Es wird ohne Beachtung der Groß-/Kleinschreibung und nur an
Wortgrenzen ersetzt; Leerzeichen und Bindestrich im Suchtext passen auf beides.
"""
from platform_support import data_dir
import os
import re

DATEI = str(data_dir() / "ersetzungen.txt")


def lade(pfad=DATEI):
    """Liest die Regeln als Liste (Muster, Ersatz); fehlende Datei oder kaputte Zeilen werden übersprungen."""
    regeln = []
    try:
        with open(pfad, encoding="utf-8") as f:
            zeilen = f.read().splitlines()
    except OSError:
        return regeln
    for z in zeilen:
        z = z.strip()
        if not z or z.startswith("#") or "=" not in z:
            continue
        von, nach = (t.strip() for t in z.split("=", 1))
        woerter = von.split()
        if not woerter:
            continue
        muster = r"(?<!\w)" + r"[\s-]+".join(re.escape(w) for w in woerter) + r"(?!\w)"
        regeln.append((re.compile(muster, re.I), nach))
    return regeln


def ersetze(text, regeln=None):
    for muster, nach in (lade() if regeln is None else regeln):
        text = muster.sub(lambda m, n=nach: n, text)
    return text
