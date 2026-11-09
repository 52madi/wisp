# WISP 🎙️

**Push-to-Talk-Diktat für Windows** – Halte eine Taste gedrückt, sprich einfach drauflos, lass los und der Text steht sofort dort, wo dein Cursor gerade ist.

WISP läuft wahlweise **100 % lokal & offline** (über `faster-whisper` auf deiner Grafikkarte oder CPU) oder **ultraschnell über die Cloud** (kostenloser Groq-Tarif mit `whisper-large-v3` / `turbo`) inklusive intelligenter Selbstkorrektur („*Am Dienstag, nein, ich meinte Mittwoch*“ → „*Am Mittwoch*“).

---

## ✨ Funktionen auf einen Blick

* **Überall diktieren:** Funktioniert in jedem Programm (Browser, Word, WhatsApp, VS Code, ChatGPT, Slack …).
* **Minimale Pille am unteren Bildschirmrand:** Schwebt dezent über der Taskleiste (wie *Wispr Flow*), zeigt deinen Mikrofonpegel beim Sprechen und lässt sich auch per Mausklick bedienen.
* **Lokal ODER Cloud (Groq):**
  * **Lokal (Offline):** Nutzt OpenAI Whisper (`faster-whisper`) direkt auf deinem PC. Nach 5 Minuten Leerlauf wird das Modell automatisch aus dem RAM/VRAM entladen.
  * **Cloud (Online über Groq):** Blitzschnelle Erkennung (< 1 Sekunde), verbraucht fast keinen Arbeitsspeicher (~40 MB RAM) und fällt bei fehlendem Internet automatisch auf das lokale Modell zurück.
* **Intelligente Nachbearbeitung:**
  * **Selbstkorrekturen:** *„Treffen um 14 Uhr, nein, ich meinte 15 Uhr“* wird automatisch zu *„Treffen um 15 Uhr“*.
  * **Diktierbefehle:** *„neuer Stichpunkt“*, *„nummerierte Liste anfangen“*, *„neue Zeile“*, *„neuer Absatz“*.
  * **Füllwörter:** Streicht automatisch *„äh“*, *„ähm“*, *„hmm“* und Wortdopplungen.
  * **Optionaler KI-Fallback:** Wenn ein Versprecher mal zu verschachtelt für die Offline-Regeln ist, kann optional ein kostenloses Online-Sprachmodell (über **Groq** oder **OpenRouter**) den Satz glattziehen.
* **Eigenes Wörterbuch & feste Ersetzungen:**
  * Eigennamen und Fachbegriffe (`woerter.txt`) sowie automatische Wort-Ersetzungen (`ersetzungen.txt`, z. B. `cloud code = Claude Code`) lassen sich direkt über die Einstellungen bearbeiten.

---

## 🚀 Schnellstart: Installation mit KI-Assistent (Claude Code, Codex, ChatGPT)

Wenn du **Claude Code**, **OpenAI Codex** oder einen anderen KI-Agenten nutzt, kopiere einfach diesen Satz in deinen KI-Assistenten:

> **„Bitte lade https://github.com/52madi/wisp herunter, installiere alle Abhängigkeiten (nutze `INSTALLIEREN.bat --auto`) und starte danach die WISP-Einstellungen.“**

*(Für KI-Agenten liegt im Repository eine fertige [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md) mit allen technischen Befehlen bereit).*

---

## 🛠️ Klassische Installation (ohne KI-Assistent)

### Voraussetzungen
* **Windows 10 oder Windows 11**
* **Python 3.10 oder neuer** ([Hier von python.org herunterladen](https://www.python.org/downloads/))
  * ⚠️ **Wichtig bei der Python-Installation:** Unten im Installer unbedingt das Häkchen bei **`[X] Add python.exe to PATH`** setzen!

### Schritt-für-Schritt
1. **Herunterladen:**
   * Klicke oben auf dieser GitHub-Seite auf den grünen Button **`<> Code`** → **`Download ZIP`** und entpacke den Ordner (z. B. nach `C:\WISP` oder `Dokumente\WISP`), **oder** klone das Repo per Git:
     ```powershell
     git clone https://github.com/52madi/wisp.git
     cd wisp
     ```
2. **Installieren:**
   * Doppelklicke im Ordner auf **`INSTALLIEREN.bat`**.
   * Das Skript legt automatisch die Python-Umgebung (`.venv`) an, installiert alle Pakete, fragt dich ob du eine NVIDIA-Grafikkarte hast und legt auf Wunsch Desktop- und Startmenü-Verknüpfungen an.
3. **Starten:**
   * Doppelklicke auf **`WISP starten.bat`** (oder auf das neue **WISP**-Symbol auf deinem Desktop).
   * Unten am Bildschirmrand erscheint die kleine schwarze Pille. Halte **`Rechte Strg`** gedrückt, sprich und lass wieder los!

---

## ☁️ Online-Modelle einrichten (Groq Cloud & KI-Korrektur)

Du musst Whisper **nicht** lokal auf deiner eigenen Grafikkarte/CPU laufen lassen! Gerade auf Laptops oder PCs ohne starke NVIDIA-Grafikkarte ist der **Online-Modus über Groq** viel schneller und schont deinen PC.

### So richtest du den kostenlosen Online-Modus in 1 Minute ein:

1. **Einstellungen öffnen:**
   * Doppelklicke auf **`WISP Einstellungen.bat`** (oder klicke mit der rechten Maustaste auf die WISP-Pille bzw. das Symbol unten rechts in der Windows-Taskleiste → *Einstellungen*).
2. **Kostenlosen Groq API-Key holen:**
   * Scrolle im Einstellungsfenster zum Bereich **„CLOUD & ONLINE-MODELLE (OPTIONAL)“**.
   * Klicke neben **Groq API-Key** auf den Button **`Key holen ↗`** (öffnet [console.groq.com/keys](https://console.groq.com/keys)).
   * Melde dich dort kostenlos an, klicke auf **Create API Key**, kopiere den Schlüssel (beginnt mit `gsk_...`).
3. **Schlüssel in WISP einfügen:**
   * Füge den Schlüssel in das Feld **Groq API-Key** in den WISP-Einstellungen ein und klicke auf **`Speichern`**.
4. **Schalter aktivieren:**
   * Schalte **„Cloud-Erkennung (Groq)“** auf **An**.
   * *(Optional)* Schalte **„KI-Korrektur (Online-Fallback)“** auf **An** und wähle als **KI-Anbieter** einfach **`groq`** (nutzt denselben Schlüssel!) oder **`openrouter`** (mit einem Key von [openrouter.ai/keys](https://openrouter.ai/keys)).

> **Gut zu wissen:** Im kostenlosen Groq-Tarif (0 €) sind bis zu **2.000 Diktate bzw. 8 Stunden Audio pro Tag** enthalten. Im Reiter **„Nutzung“** in den WISP-Einstellungen siehst du jederzeit live, wie viel du heute verbraucht hast. Sollte dein Internet einmal ausfallen, schaltet WISP automatisch auf das lokale Modell um.

---

## 📖 Eigene Wörter & Ersetzungen anpassen

In den Einstellungen findest du ganz unten den Bereich **„WÖRTERBUCH & ERSETZUNGEN“**:

* **Eigene Wörter & Namen (`woerter.txt`):** Klicke auf `Bearbeiten` und schreibe Namen, Firmen oder Fachbegriffe untereinander (ein Wort pro Zeile). Die Cloud-Erkennung nutzt diese Liste als Hinweis, damit ungewöhnliche Wörter richtig geschrieben werden.
* **Feste Ersetzungen (`ersetzungen.txt`):** Klicke auf `Bearbeiten` und trage typische Hörfehler im Format `falsch = richtig` ein (z. B. `cloud code = Claude Code`). WISP korrigiert diese Begriffe nach jedem Diktat automatisch.

Alle persönlichen Einstellungen und Schlüssel werden sicher außerhalb des Programmordners unter `%APPDATA%\WISP` gespeichert.

---

## 🧪 Tests ausführen (für Entwickler)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
