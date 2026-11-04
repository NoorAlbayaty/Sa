import os
import sys
import json
import time
import uuid
import threading

APP_NAME = "Sahm"
<<<<<<< HEAD
APP_VERSION = "1.4.1"
=======
APP_VERSION = "1.4.2"
>>>>>>> bbc1fda (v1.4.2 fix mac version)
SERVER_PORT = 9614


def data_dir():
    """Windows: %APPDATA%\\Sahm   macOS: ~/Library/Application Support/Sahm   other: ~/.config/Sahm"""
    if os.environ.get("APPDATA"):
        base = os.environ["APPDATA"]
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


_write_lock = threading.Lock()


def write_json(path, data, indent=None):
    """Save a JSON file without ever leaving it half-written.
    Writes a uniquely named temp file, then swaps it in. On Windows the swap fails while another
    program (antivirus, backup, indexer) has the file open for a moment - so retry briefly, and as a
    last resort write in place. Returns True if saved; never raises."""
    payload = json.dumps(data, ensure_ascii=False, indent=indent)
    with _write_lock:
        tmp = f"{path}.{os.getpid()}-{uuid.uuid4().hex[:6]}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            for attempt in range(8):
                try:
                    os.replace(tmp, path)
                    return True
                except PermissionError:
                    time.sleep(0.02 * (attempt + 1))
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(payload)
                return True
            except OSError:
                return False
        except OSError:
            return False
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass


def clean_temp_files(folder):
    """Remove leftover *.tmp files from older versions / crashes."""
    try:
        for name in os.listdir(folder):
            if name.endswith(".tmp") and (name.startswith("downloads.json") or name.startswith("settings.json")):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass
    except OSError:
        pass


def default_download_dir():
    return os.path.join(os.path.expanduser("~"), "Downloads", APP_NAME)


DEFAULTS = {
    "download_dir": default_download_dir(),
    "connections": 8,
    "max_concurrent": 3,
    "speed_limit_kb": 0,          # 0 = unlimited
    "browser_show_dialog": True,  # show Add dialog for downloads caught by the extension
    "notify_on_complete": True,
    "close_to_tray": True,
    "start_at_login": False,
    "theme": "system",            # "system" | "light" | "dark"
    "sched_enabled": False,
    "sched_start": "02:00",
    "sched_stop": "",             # "" = don't stop automatically
    "sched_shutdown": False,      # placeholder for future: shut down when queue done
}


class Settings(dict):
    def __init__(self, path=None):
        super().__init__(DEFAULTS)
        self.path = path or os.path.join(data_dir(), "settings.json")
        try:
            with open(self.path, encoding="utf-8") as f:
                self.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        return write_json(self.path, dict(self), indent=2)
