"""Nutzungsstatistik: WISP zählt jedes Diktat (Dauer, Quelle, KI-Tokens) in nutzung.jsonl.

Die Zählung ist von WISP selbst (nicht aus der Groq-Konsole) und deshalb eine Schätzung:
Nutzung außerhalb von WISP (z. B. Playground) taucht hier nicht auf.
Pro Diktat wird eine Zeile angehängt; die Statistik-Seite liest die Datei nur beim Öffnen.
"""
import json
import os
import time

PFAD = os.path.join(os.environ.get("APPDATA", ""), "WISP", "nutzung.jsonl")

# Groq-Limits für Whisper im Free-Tarif (siehe Groq-Konsole: Organization -> Limits)
LIMIT_AUDIO_TAG = 28800
LIMIT_AUDIO_STUNDE = 7200
LIMIT_ANFRAGEN_TAG = 2000
MIN_ABRECHNUNG = 10     # Groq rechnet pro Anfrage mindestens 10 s


def schreibe(eintrag, pfad=PFAD):
    eintrag = {"t": time.time(), **eintrag}
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def lade(pfad=PFAD):
    """Alle gültigen Einträge; fehlende Datei oder kaputte Zeilen werden übersprungen."""
    out = []
    try:
        with open(pfad, encoding="utf-8") as f:
            for zeile in f:
                try:
                    e = json.loads(zeile)
                except ValueError:
                    continue
                if isinstance(e, dict) and isinstance(e.get("t"), (int, float)):
                    out.append(e)
    except OSError:
        pass
    return out


def _cloud_s(e):
    return max(e.get("audio_s", 0), MIN_ABRECHNUNG) if e.get("quelle") == "cloud" else 0


def _tag(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def pro_tag(eintraege, max_tage=14):
    """Je Tag eine Summenzeile, neueste zuerst."""
    tage = {}
    for e in eintraege:
        d = _tag(e["t"])
        z = tage.setdefault(d, {"datum": d, "diktate": 0, "audio_s": 0.0, "cloud": 0, "lokal": 0,
                                "cloud_s": 0.0, "ki": 0, "ki_tokens": 0})
        z["diktate"] += 1
        z["audio_s"] += e.get("audio_s", 0)
        if e.get("quelle") == "cloud":
            z["cloud"] += 1
            z["cloud_s"] += _cloud_s(e)
        else:
            z["lokal"] += 1
        if e.get("ki_tokens"):
            z["ki"] += 1
            z["ki_tokens"] += e["ki_tokens"]
    return sorted(tage.values(), key=lambda z: z["datum"], reverse=True)[:max_tage]


def heute(eintraege, jetzt=None):
    """Cloud-Verbrauch heute und in der letzten Stunde (gegen die Groq-Limits)."""
    jetzt = time.time() if jetzt is None else jetzt
    tag = _tag(jetzt)
    cloud = [e for e in eintraege if e.get("quelle") == "cloud"]
    heute_ = [e for e in cloud if _tag(e["t"]) == tag]
    stunde = [e for e in cloud if jetzt - 3600 < e["t"] <= jetzt]
    return {"anfragen": len(heute_),
            "audio_s": sum(_cloud_s(e) for e in heute_),
            "stunde_s": sum(_cloud_s(e) for e in stunde)}


def groq_stand(eintraege):
    """Letzte von Groq gemeldete Anfrage-Restmenge: {'limit', 'rest', 't'} oder None."""
    for e in reversed(eintraege):
        if e.get("rl_rest") is not None and e.get("rl_limit"):
            return {"limit": e["rl_limit"], "rest": e["rl_rest"], "t": e["t"]}
    return None


def dauer(s):
    """Sekunden als kurzer Text: '45 s', '12 min 05 s', '1 h 05 min'."""
    s = int(round(s))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"
