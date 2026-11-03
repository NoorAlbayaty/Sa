import os
import sys
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from settings import Settings, SERVER_PORT
from manager import Manager
import server


def _post(path, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{SERVER_PORT}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Sahm-Client": "extension"})
    urllib.request.urlopen(req, timeout=3)


def sahm_already_running():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{SERVER_PORT}/ping", timeout=2) as r:
            return json.loads(r.read() or b"{}").get("app") == "Sahm"
    except Exception:
        return False


def hand_off_to_running_instance(url):
    """Sahm is already running: give it the link (Sahm.exe <url>), or just bring its window forward."""
    try:
        if url:
            _post("/add", {"url": url})
        _post("/show", {})
        return True
    except Exception:
        return False


def install_error_handler():
    """Log unexpected errors and show them instead of letting the app close."""
    import traceback
    from settings import data_dir
    log = os.path.join(data_dir(), "error.log")

    def hook(etype, value, tb):
        import datetime
        from settings import APP_VERSION
        text = "".join(traceback.format_exception(etype, value, tb))
        try:
            if os.path.exists(log) and os.path.getsize(log) > 500_000:
                os.replace(log, log + ".old")
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S}  Sahm {APP_VERSION}  {sys.platform}\n{text}\n")
        except OSError:
            pass
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Sahm – error", f"{value}\n\nDetails saved to:\n{log}")
        except Exception:
            pass
    sys.excepthook = hook


def main():
    install_error_handler()
    cli_url = next((a for a in sys.argv[1:] if a.startswith(("http://", "https://"))), None)
    srv = server.start_server()
    if srv is None and sahm_already_running() and hand_off_to_running_instance(cli_url):
        return 0          # only one Sahm at a time (two copies would fight over the same files)

    settings = Settings()

    app = QApplication(sys.argv)
    app.setApplicationName("Sahm")
    app.setQuitOnLastWindowClosed(False)
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))      # macOS keeps its own system font
    import theme
    theme.apply(settings.get("theme", "system"), app)
    theme.follow_system(app, lambda: settings.get("theme", "system"))

    from gui import MainWindow
    manager = Manager(settings)
    win = MainWindow(manager, settings, server_ok=srv is not None)
    app.aboutToQuit.connect(manager.shutdown)          # Cmd+Q / logout: save the list first
    if sys.platform == "darwin":                       # clicking the Dock icon brings the window back
        app.applicationStateChanged.connect(
            lambda st: win.show_normal() if st == Qt.ApplicationState.ApplicationActive and win.isHidden()
            and not win._quitting else None)
    if "--minimized" not in sys.argv:
        win.show()
    if cli_url:
        server.incoming.put({"type": "file", "url": cli_url, "filename": "", "headers": {}})
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
