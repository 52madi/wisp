# WISP – Instructions for AI Coding Assistants (Claude Code, Codex, ChatGPT, etc.)

When a user asks you to download, install, configure, or start **WISP**, follow these exact steps so the installation runs smoothly without hanging on interactive prompts.

## macOS installation
On macOS, use Python 3.10+ from python.org with Tk support. Run `bash INSTALLIEREN.command`, then `bash "WISP starten.command"` or `bash "WISP Einstellungen.command"`. Use `.venv/bin/python` for tests. Local inference uses CPU; NVIDIA packages are Windows-only. Ask the user to grant microphone, Accessibility and (if requested by macOS) Input Monitoring permissions to the launching Terminal/Python application and restart WISP. Store personal files in `~/Library/Application Support/WISP`, outside the checkout. macOS support still needs a real-device UI test.

The following installation commands apply to Windows only.

## 1. System Requirements
- **OS:** Windows 10 or Windows 11 (uses Win32 layered windows and Windows shortcuts).
- **Python:** Python 3.10+ (`python --version`).
  - If Python is not installed, install it via `winget install -e --id Python.Python.3.12 --scope machine` (or ask the user to install Python from python.org with "Add python.exe to PATH" checked).

## 2. Non-Interactive Installation (IMPORTANT!)
Do **NOT** run `INSTALLIEREN.bat` without arguments, because it uses interactive `choice` and `pause` commands that will block your terminal!

Instead, either run the batch installer with `--auto`:
```cmd
INSTALLIEREN.bat --auto
```
**OR** run the individual commands directly in PowerShell/CMD:
```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Install base dependencies
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Check for NVIDIA GPU; only install CUDA packages (~1 GB) if an NVIDIA GPU is present and the user wants local GPU inference
where.exe nvidia-smi
# If exit code is 0 (NVIDIA GPU present):
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt

# 4. Create Desktop and Start Menu shortcuts
.\.venv\Scripts\python.exe setup_app.py
# Optional: enable Windows autostart
# .\.venv\Scripts\python.exe setup_app.py --autostart
```

## 3. Configuring Online / Cloud Models (Groq & OpenRouter)
Users often prefer **Online Cloud Recognition (Groq)** instead of local Whisper because it requires almost no RAM (~40 MB), no GPU download, and transcribes in under 1 second.

All user configuration lives in `%APPDATA%\WISP\`:
- **`%APPDATA%\WISP\settings.json`**: JSON configuration file.
  - To enable Groq Cloud Speech-to-Text and KI fallback automatically for the user, merge/write:
    ```json
    {
      "cloud": true,
      "cloud_modell": "whisper-large-v3",
      "ki": true,
      "ki_anbieter": "groq"
    }
    ```
- **`%APPDATA%\WISP\schluessel.txt`**: Stores API keys (one `KEY=VALUE` per line):
  ```ini
  GROQ_API_KEY=gsk_...
  OPENROUTER_API_KEY=sk-or-...
  ```
  *(Note: The user can also enter and save these keys graphically inside the WISP settings window (`wisp.py --settings`) under "CLOUD & ONLINE-MODELLE", which also has a button to open https://console.groq.com/keys).*
- **`%APPDATA%\WISP\woerter.txt`**: Custom vocabulary/names (one word per line) passed as prompt to Whisper.
- **`%APPDATA%\WISP\ersetzungen.txt`**: Fixed post-processing replacements (`wrong = right`, one per line).

## 4. Starting WISP & Opening Settings
- **Start WISP background overlay (pill):**
  ```powershell
  Start-Process .\.venv\Scripts\pythonw.exe -ArgumentList "wisp.py"
  ```
- **Open WISP Settings UI (e.g., so the user can paste their Groq API key):**
  ```powershell
  Start-Process .\.venv\Scripts\pythonw.exe -ArgumentList "wisp.py --settings"
  ```

## 5. Running Unit Tests
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
