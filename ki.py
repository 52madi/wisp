"""Optionaler KI-Fallback für schwierige Diktate (kostenlose OpenAI-kompatible Dienste).

Ablauf: Die Regeln in postprocess.py laufen immer zuerst. Nur wenn danach noch ein
Korrektur-Hinweis im Text steht, wird die KI gefragt. Bei Fehler, Timeout oder
unplausibler Antwort bleibt der Regeltext.

Der API-Schlüssel kommt ausschließlich aus einer Umgebungsvariable (siehe ANBIETER).
"""
import json
import os
import re
import urllib.request

ANBIETER = {
    "groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "key_env": "GROQ_API_KEY",
             "modell": "llama-3.3-70b-versatile"},
    "openrouter": {"url": "https://openrouter.ai/api/v1/chat/completions", "key_env": "OPENROUTER_API_KEY",
                   "modell": "openai/gpt-oss-20b"},
}

# Wörter, die nach den Regeln noch auf eine ungelöste Korrektur hindeuten
_HINWEIS = re.compile(
    # "ich meinte" nur als Korrektur, nicht in "ich meinte, dass ..."
    r"\bich\s+meinte\b(?!\s*,?\s*(?:dass|daß|ob|wie|das|es)\b)"
    r"|\bich\s+meine\s+nicht\b|\bbesser\s+gesagt\b|\boder\s+vielmehr\b"
    r"|\bsondern\b(?!\s+auch\b)|\bvergiss\s+das\b|\bkorrektur\b|\bno\s+wait\b|\bi\s+meant\b"
    r"|,\s*(?:nein|nee)\s*,", re.I)     # ", nein," mitten im Satz; "Nein, ich ..." nach "?" nicht
# "eigentlich" steht bewusst nicht drin: es ist im normalen Sprechen zu häufig.

# Korrektur-Wörter, die nicht zum Inhalt gehören und den Vergleich verzerren würden
_KORREKTUR_WOERTER = {"nein", "nee", "meinte", "meine", "sondern", "eigentlich", "besser", "gesagt",
                      "vergiss", "korrektur", "wirklich", "nicht"}

SYSTEM = (
    "Du bearbeitest ein diktiertes Transkript. Regeln:\n"
    "1. Wenn der Sprecher sich korrigiert (\"nein, ich meinte ...\", \"besser gesagt\", \"sondern\", "
    "\"no wait\"), entferne den verworfenen Teil und behalte nur die Korrektur.\n"
    "2. \"Neuer Stichpunkt\" beginnt einen Listenpunkt mit \"- \", \"neue Zeile\" eine neue Zeile, "
    "\"neuer Absatz\" einen Absatz. Füllwörter wie äh/ähm streichst du.\n"
    "3. Füge keine Inhalte hinzu, erkläre nichts, ändere keine Fakten.\n"
    "4. Ist nichts zu korrigieren, gib den Text unverändert zurück.\n"
    "Beispiele:\n"
    "- \"Am Montag, nein, Dienstag.\" -> \"Am Dienstag.\"\n"
    "- \"Ich komme morgen, besser gesagt Freitag.\" -> \"Ich komme Freitag.\"\n"
    "Antworte NUR mit dem bearbeiteten Text, ohne Anführungszeichen oder Kommentar."
)


letzte_tokens = 0       # Tokens des letzten korrigiere()-Aufrufs (für die Nutzungsstatistik)

SCHLUESSEL_DATEI = os.path.join(os.environ.get("APPDATA", ""), "WISP", "schluessel.txt")


def schluessel(key_env):
    """Schlüssel aus der Umgebungsvariable oder aus schluessel.txt (Zeile: NAME=WERT)."""
    if os.environ.get(key_env):
        return os.environ[key_env]
    try:
        with open(SCHLUESSEL_DATEI, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if zeile and not zeile.startswith("#") and "=" in zeile:
                    name, wert = zeile.split("=", 1)
                    if name.strip() == key_env:
                        return wert.strip()
    except OSError:
        pass
    return ""


def speichere_schluessel(key_env, wert):
    """Speichert oder aktualisiert einen API-Schlüssel in schluessel.txt."""
    wert = (wert or "").strip()
    zeilen = []
    gefunden = False
    try:
        with open(SCHLUESSEL_DATEI, encoding="utf-8") as f:
            for z in f.read().splitlines():
                s = z.strip()
                if s and not s.startswith("#") and "=" in s and s.split("=", 1)[0].strip() == key_env:
                    if wert:
                        zeilen.append(f"{key_env}={wert}")
                    gefunden = True
                else:
                    zeilen.append(z)
    except OSError:
        pass
    if not gefunden and wert:
        zeilen.append(f"{key_env}={wert}")
    os.makedirs(os.path.dirname(SCHLUESSEL_DATEI), exist_ok=True)
    with open(SCHLUESSEL_DATEI, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + ("\n" if zeilen else ""))


def zusatz(modell):
    """Modellspezifische Parameter. gpt-oss denkt standardmäßig lange, 'low' hält es schnell."""
    if modell.startswith("openai/gpt-oss"):
        return {"reasoning": {"effort": "low"}}
    return {}


def braucht_ki(text):
    """True, wenn nach den Regeln noch ein Korrektur-Hinweis im Text steht."""
    return bool(_HINWEIS.search(text or ""))


def plausibel(roh, antwort):
    """Verwirft Antworten, die deutlich länger sind oder kaum Wörter des Originals enthalten."""
    if not antwort or len(antwort) > 1.3 * len(roh) + 20:
        return False
    woerter = {w for w in re.findall(r"\w{4,}", roh.lower())} - _KORREKTUR_WOERTER
    if not woerter:
        return True
    gemeinsam = sum(1 for w in woerter if w in antwort.lower())
    return gemeinsam / len(woerter) >= 0.5


def korrigiere(text, anbieter, modell=None, timeout=6.0):
    """Gibt den KI-Text zurück oder None (bei fehlendem Schlüssel, Fehler, Timeout, Unplausibilität)."""
    global letzte_tokens
    letzte_tokens = 0
    cfg = ANBIETER.get(anbieter)
    if not cfg:
        return None
    key = schluessel(cfg["key_env"])
    if not key:
        return None
    body = json.dumps({
        "model": modell or cfg["modell"],
        "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        **zusatz(modell or cfg["modell"]),
    }).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            antwort = json.load(r)
        out = antwort["choices"][0]["message"]["content"].strip()
        letzte_tokens = int((antwort.get("usage") or {}).get("total_tokens") or 0)
    except Exception:
        return None
    return out if plausibel(text, out) else None
