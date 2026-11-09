# WISP – Sprache zu Text für Windows und macOS

Mit WISP diktierst du Text direkt in das Programm, das du gerade benutzt. Taste gedrückt halten, sprechen, loslassen – fertig.

## Installation

### Windows

Du brauchst **Windows 10 oder 11**, ein Mikrofon und eine Internetverbindung für die Installation.

1. **Python installieren:** Lade [Python](https://www.python.org/downloads/) herunter (Version 3.10 oder neuer). Setze bei der Installation das Häkchen **„Add python.exe to PATH“**.
2. **WISP herunterladen:** Klicke auf dieser GitHub-Seite oben auf **Code → Download ZIP** und entpacke die ZIP-Datei.
3. **WISP installieren:** Öffne den entpackten Ordner und doppelklicke auf **INSTALLIEREN.bat**. Folge den Fragen im Fenster. Die NVIDIA-Unterstützung brauchst du nur, wenn du eine NVIDIA-Grafikkarte für die lokale Erkennung nutzen möchtest.
4. **WISP starten:** Doppelklicke auf **WISP starten.bat** oder verwende die Desktop-Verknüpfung, falls du sie angelegt hast.

Klicke jetzt in ein Textfeld, halte die **rechte Strg-Taste** gedrückt und sprich. Sobald du die Taste loslässt, fügt WISP den erkannten Text ein. Die Taste kannst du in den Einstellungen ändern.

Beim ersten lokalen Start muss das Sprachmodell gegebenenfalls heruntergeladen werden; das kann etwas dauern. Danach funktioniert die lokale Erkennung auch offline.

### macOS (neu, noch nicht auf einem Mac praktisch getestet)

1. Installiere **Python 3.10 oder neuer von python.org** (mit Tk-Unterstützung).
2. Lade WISP über **Code → Download ZIP** herunter und entpacke es.
3. Öffne ein Terminal im entpackten Ordner und führe `bash INSTALLIEREN.command` aus.
4. Starte WISP mit `bash "WISP starten.command"`. Die Einstellungen öffnest du mit `bash "WISP Einstellungen.command"`.

Erlaube dem verwendeten Terminal bzw. Python unter **Systemeinstellungen → Datenschutz & Sicherheit** den Zugriff auf **Mikrofon**, **Bedienungshilfen** und bei Bedarf **Eingabeüberwachung**. Starte WISP danach neu. Diese Freigaben musst du selbst erteilen.

Die lokale Erkennung verwendet auf dem Mac die CPU. Alternativ kannst du Groq aktivieren. Die Mac-Anzeige hat einen Aufnahme-Button und ein Menü; Windows-Autostart und Windows-Verknüpfungen gibt es dort nicht. Der erste lokale Start lädt das Sprachmodell herunter.

Zum Diktieren hältst du auf dem Mac standardmäßig die **rechte Umschalttaste** gedrückt und lässt sie anschließend los. Wähle bei langsamer lokaler Erkennung in den Einstellungen ein kleineres Modell, etwa `base`.

## Installation mit Codex oder Claude Code

Du kannst deinem KI-Assistenten stattdessen diesen Auftrag geben:

> Bitte lade https://github.com/52madi/wisp herunter, installiere WISP passend zu meinem Betriebssystem und öffne anschließend die Einstellungen. Frage mich, bevor du optionale NVIDIA-Pakete herunterlädst.

Die technischen Installationshinweise für Assistenten stehen in [AGENTS.md](AGENTS.md) und [CLAUDE.md](CLAUDE.md).

## Optional: Online-Erkennung mit Groq

Standardmäßig erkennt WISP Sprache lokal auf deinem PC. Alternativ kannst du Groq verwenden:

1. Öffne **WISP Einstellungen.bat**.
2. Erstelle einen API-Schlüssel bei [Groq](https://console.groq.com/keys).
3. Füge ihn in den Einstellungen bei **Groq API-Key** ein und speichere ihn.
4. Aktiviere **Cloud-Erkennung (Groq)**.

Bei aktivierter Cloud-Erkennung wird deine Sprachaufnahme zur Verarbeitung an Groq gesendet. Für die Nutzung gelten die Bedingungen und Limits von Groq. Deinen API-Schlüssel solltest du nicht weitergeben.

## Einstellungen und Hilfe

In den Einstellungen kannst du unter anderem die Diktier-Taste ändern, eigene Wörter und Ersetzungen hinterlegen und die optionale KI-Korrektur einschalten. Deine Einstellungen und Schlüssel liegen unter Windows in `%APPDATA%\WISP`, auf dem Mac in `~/Library/Application Support/WISP`.

Der Diktatverlauf ist bei neuen Installationen ausgeschaltet. Bereits gespeicherte Einstellungen bleiben erhalten. API-Schlüssel werden lokal in einer Datei gespeichert; auf dem Mac ist diese nur für deinen Benutzer lesbar. Die optionale KI-Korrektur sendet Text an den gewählten Anbieter.

Wenn die Installation fehlschlägt, prüfe deine Internetverbindung und ob Python mit **„Add python.exe to PATH“** installiert wurde. Starte das Installationsfenster danach erneut.
