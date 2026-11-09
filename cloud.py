"""Optionale Cloud-Spracherkennung über Groq (Whisper large-v3-turbo).

Nur aktiv, wenn der Schalter "Cloud-Erkennung" in den Einstellungen an ist. Das Audio wird
als WAV an Groq geschickt, der Text kommt zurück. Bei Fehler wirft die Funktion eine
Exception, der Aufrufer fällt dann auf das lokale Modell zurück.

Der API-Schlüssel kommt wie bei ki.py aus GROQ_API_KEY oder schluessel.txt.
"""
from platform_support import data_dir
import io
import os
import re
import urllib.request
import uuid
import wave

import numpy as np

import ki

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODELL = "whisper-large-v3"        # wie lokal; "whisper-large-v3-turbo" ist schneller und billiger
MODELLE = ["whisper-large-v3", "whisper-large-v3-turbo"]
WOERTER_DATEI = str(data_dir() / "woerter.txt")
KEY_ENV = "GROQ_API_KEY"
letzte_limits = {}      # Rate-Limit-Angaben aus der letzten Groq-Antwort: {"limit": 2000, "rest": 1998}


def wav_bytes(audio, sample_rate):
    """Mono-Float-Audio als 16-Bit-WAV."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def woerter_prompt():
    """Namen/Fachbegriffe aus woerter.txt (ein Wort pro Zeile) als Whisper-Prompt; sie werden eher richtig erkannt."""
    try:
        with open(WOERTER_DATEI, encoding="utf-8") as f:
            w = [z.strip() for z in f if z.strip() and not z.lstrip().startswith("#")]
    except OSError:
        return ""
    return ("Begriffe: " + ", ".join(w))[:600] if w else ""


def _nur_prompt(text, prompt):
    """Bei Stille/Rauschen gibt Whisper manchmal nur den Prompt zurück - das verwerfen wir."""
    if not prompt:
        return False
    erlaubt = set(re.findall(r"\w+", prompt.lower()))
    gesagt = re.findall(r"\w+", text.lower())
    return bool(gesagt) and all(w in erlaubt for w in gesagt)


def _multipart(felder, datei, dateiname):
    """Baut einen multipart/form-data-Body ohne externe Pakete."""
    grenze = uuid.uuid4().hex
    teile = []
    for name, wert in felder.items():
        teile.append(f"--{grenze}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{wert}\r\n".encode("utf-8"))
    teile.append((f"--{grenze}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{dateiname}\"\r\n"
                  "Content-Type: audio/wav\r\n\r\n").encode("utf-8"))
    teile.append(datei)
    teile.append(f"\r\n--{grenze}--\r\n".encode("utf-8"))
    return b"".join(teile), grenze


def transkribiere(audio, sample_rate, language, modell=MODELL, timeout=15.0):
    """Gibt den erkannten Text zurück. Wirft eine Exception bei fehlendem Schlüssel oder Fehler."""
    key = ki.schluessel(KEY_ENV)
    if not key:
        raise RuntimeError("kein GROQ_API_KEY (Umgebungsvariable oder schluessel.txt)")
    felder = {"model": modell or MODELL, "response_format": "text", "temperature": "0"}
    if language:
        felder["language"] = language
    prompt = woerter_prompt()
    if prompt:
        felder["prompt"] = prompt
    body, grenze = _multipart(felder, wav_bytes(audio, sample_rate), "audio.wav")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={grenze}",
        "User-Agent": "WISP/1.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode("utf-8").strip()
        letzte_limits.clear()
        for name, feld in (("x-ratelimit-limit-requests", "limit"), ("x-ratelimit-remaining-requests", "rest")):
            try:
                letzte_limits[feld] = int(r.headers.get(name))
            except (TypeError, ValueError):
                pass
    return "" if _nur_prompt(text, prompt) else text
