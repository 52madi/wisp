# WISP – Stand (22.10.2026)

Push-to-Talk-Diktat für Windows: Hotkey halten, sprechen, Text wird am Cursor eingetippt.

## Module
| Datei | Aufgabe |
|---|---|
| `wisp.py` | Hauptprogramm (Pille, Hotkey, Aufnahme), Einstellungsfenster (`--settings`), Engine |
| `cloud.py` | Cloud-Erkennung über Groq (`whisper-large-v3`, wählbar auch `-turbo`), Wörterliste als Prompt |
| `ersetzungen.py` | feste Ersetzungen nach der Erkennung (`ersetzungen.txt`) |
| `postprocess.py` | Selbstkorrekturen, Stichpunkte, Füllwörter |
| `ki.py` | optionale KI-Korrektur (OpenRouter/Groq), zählt Tokens |
| `nutzung.py` | Nutzungsstatistik (`nutzung.jsonl`), Groq-Limits, Rate-Limit-Header |

Daten in `%APPDATA%\WISP`: `settings.json`, `schluessel.txt` (GROQ_API_KEY, OPENROUTER_API_KEY), `woerter.txt`, `ersetzungen.txt`, `nutzung.jsonl`, `wisp.log`.

## Entscheidungen
- **Lokal:** `faster-whisper`, GPU mit **`float16`**. `int8_float16` war probiert und hat das lokale `large-v3` stark verschlechtert (Buchstabenfehler) – nicht wieder einsetzen.
- **Modell nach 5 Min Leerlauf entladen** (`IDLE_UNLOAD_S`), lädt beim nächsten Diktat neu (10–20 s).
- **Cloud (Groq)** ist ein Schalter in den Einstellungen, Standard aus; bei Fehler Fallback auf lokal. RAM mit Cloud ~43 MB, lokal ~700 MB.
- Groq Free-Tarif (0 $): Whisper 20 Anfragen/min, 2.000/Tag, 7.200 s Audio/Std., 28.800 s/Tag je Modell. Mindestabrechnung 10 s pro Anfrage. Konsole zeigt UTC, bis 15 min verzögert.
- Cloudflare Workers AI (Whisper) ist die Reserve, falls Groq Probleme macht (Account-ID + API-Token nötig).

## Nutzung (zuletzt gebaut)
- Seite „Nutzung“ im Einstellungsfenster: Balken Audio heute/Stunde, Anfragen heute, Groq-gemeldete Restanfragen, Tabelle der letzten Tage (Diktate, Audio, Cloud/Lokal, KI-Tokens).
- Zählung von WISP stimmt mit der Groq-Konsole ungefähr überein (geprüft am 22.10.: ca. 27 Anfragen, ca. 450 s).
- Zählung läuft erst seit 22.10. 11:08; frühere Diktate nur in `wisp.log`.

## Offen / mögliche nächste Schritte
- Heutige Diktate aus `wisp.log` in `nutzung.jsonl` nachtragen (optional).
- Lokale Erkennung in eigenen Prozess auslagern, der im Leerlauf komplett beendet wird (RAM lokal im Leerlauf fast null).
- Cloudflare als zweiter Cloud-Anbieter, falls nötig.
- Hinweis: Neuer Code wirkt erst nach komplettem Neustart von WISP (vorher alte Instanz beenden, sonst startet nur ein zweites Fenster).

## Andere PCs / USB-Stick
- `WISP USB-Stick erstellen.bat` kopiert das Projekt (ohne `.venv`) auf einen Stick: Ziel als Parameter (`"WISP USB-Stick erstellen.bat" E:\WISP`) oder Abfrage.
- Auf dem neuen PC: Ordner von Stick auf Festplatte kopieren, dann `INSTALLIEREN.bat` (prüft Python, baut `.venv`, installiert requirements, fragt nach NVIDIA-GPU -> `requirements-gpu.txt`, legt optional Verknüpfungen + Autostart an).
- `WISP starten.bat` bietet die Installation automatisch an, wenn noch kein `.venv` existiert; beide Bats brechen mit Meldung ab, wenn Python fehlt bzw. Installation unvollständig ist.
- CUDA-Pakete (~1 GB) sind in `requirements-gpu.txt` ausgelagert, Basis-Paket läuft ohne GPU.
- Tests nicht vergessen: `tests\test_ki.py` mockt jetzt auch `SCHLUESSEL_DATEI`, sonst schlagen sie auf jedem PC mit eingetragenem Groq-Key fehl.

## Tests
`.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
