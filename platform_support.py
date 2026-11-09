"""Small OS boundary; personal files never default to the source directory."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys

IS_MAC = sys.platform == "darwin"
_instance_handle = None


def data_dir():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "WISP"
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / "WISP"
    return Path.home() / ".local" / "share" / "WISP"


def open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["/usr/bin/open", str(Path(path).resolve())])


def single_instance():
    global _instance_handle
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        _instance_handle = kernel.CreateMutexW(None, False, "WISP_single_instance")
        return bool(_instance_handle) and ctypes.get_last_error() != 183
    import fcntl
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    _instance_handle = open(folder / "instance.lock", "a")
    try:
        fcntl.flock(_instance_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        _instance_handle.close()
        return False
