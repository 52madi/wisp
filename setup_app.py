"""Richtet WISP als normale Windows-App ein: Verknüpfungen (Desktop + Startmenü) mit Icon.

python setup_app.py              -> Verknüpfungen anlegen
python setup_app.py --autostart  -> zusätzlich beim Windows-Start automatisch starten
python setup_app.py --remove     -> Verknüpfungen und Autostart wieder entfernen
"""
import os
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PYW = os.path.join(APP_DIR, ".venv", "Scripts", "pythonw.exe")
SCRIPT = os.path.join(APP_DIR, "wisp.py")
ICON = os.path.join(APP_DIR, "assets", "wisp.ico")
APPDATA = os.environ["APPDATA"]
START_MENU = os.path.join(APPDATA, "Microsoft", "Windows", "Start Menu", "Programs")
STARTUP = os.path.join(START_MENU, "Startup")


def desktop():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                         capture_output=True, text=True).stdout.strip()
    return out or os.path.join(os.path.expanduser("~"), "Desktop")


def shortcut(path, args, description):
    def quote(value):
        return str(value).replace("'", "''")
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath='%s';$s.Arguments='%s';$s.WorkingDirectory='%s';"
        "$s.IconLocation='%s';$s.Description='%s';$s.Save()"
    ) % tuple(quote(v) for v in (path, PYW, args, APP_DIR, ICON, description))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def main():
    targets = {
        os.path.join(START_MENU, "WISP.lnk"): ('"%s"' % SCRIPT, "WISP Diktat"),
        os.path.join(START_MENU, "WISP Einstellungen.lnk"): ('"%s" --settings' % SCRIPT, "WISP Einstellungen"),
        os.path.join(desktop(), "WISP.lnk"): ('"%s"' % SCRIPT, "WISP Diktat"),
    }
    autostart = os.path.join(STARTUP, "WISP.lnk")
    old_vbs = os.path.join(STARTUP, "WISP.vbs")

    if "--remove" in sys.argv:
        for p in list(targets) + [autostart, old_vbs]:
            if os.path.exists(p):
                os.remove(p)
                print("entfernt:", p)
        return

    for p, (args, desc) in targets.items():
        shortcut(p, args, desc)
        print("angelegt:", p)
    if "--autostart" in sys.argv:
        if os.path.exists(old_vbs):
            os.remove(old_vbs)
        shortcut(autostart, '"%s"' % SCRIPT, "WISP Diktat")
        print("Autostart aktiv:", autostart)


if __name__ == "__main__":
    main()
