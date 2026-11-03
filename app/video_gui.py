"""Video quality picker (like IDM's "Download this video") and the one-time tool installer."""
import os
import threading
import urllib.parse

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QLineEdit, QFileDialog)

import tools
import video
from settings import data_dir
from i18n import tr, human_size

VIDEO_SITES = ("youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com", "tiktok.com",
               "x.com", "twitter.com", "vimeo.com", "dailymotion.com", "twitch.tv", "reddit.com",
               "soundcloud.com", "aparat.com", "bilibili.com", "rumble.com", "streamable.com")
DIRECT_EXT = (".mp4", ".webm", ".mkv", ".mov", ".m4a", ".mp3", ".flv", ".avi")


def is_video_page(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in VIDEO_SITES)


GENERIC_NAMES = {"contents", "content", "download", "file", "video", "stream", "media", "raw", "blob", "index",
                 "play", "playback", "view", "get", "data", "source", "videoplayback"}


def is_playlist(m):
    return ".m3u8" in m["url"] or ".mpd" in m["url"] or "mpegurl" in m["type"] or "dash+xml" in m["type"]


def is_direct_media(m):
    """A real video/audio file the page loaded - judged by its type, not only by '.mp4' in the address
    (web apps serve videos from addresses like /api/files/abc123/contents)."""
    if is_playlist(m):
        return False
    path = urllib.parse.urlparse(m["url"]).path.lower()
    return path.endswith(DIRECT_EXT) or m["type"].startswith(("video/", "audio/")) or m["type"] == "element"


def cookie_header_for(url, cookies):
    """Browser cookies that the browser itself would send to this address."""
    p = urllib.parse.urlparse(url)
    host, path = (p.hostname or "").lower(), p.path or "/"
    out = []
    for c in cookies or []:
        d = c.get("domain", "").lower()
        bare = d.lstrip(".")
        if c.get("hostOnly") or not d.startswith("."):
            ok = host == bare
        else:
            ok = host == bare or host.endswith("." + bare)
        if ok and path.startswith(c.get("path") or "/") and (p.scheme == "https" or not c.get("secure")):
            out.append(f"{c['name']}={c.get('value', '')}")
    return "; ".join(out)


def cookie_file_for(url, cookies):
    if not cookies:
        return None
    import re
    import uuid
    host = re.sub(r"[^a-z0-9.-]", "_", (urllib.parse.urlparse(url).hostname or "site").lower())[:60]
    d = os.path.join(data_dir(), "cookies")
    os.makedirs(d, exist_ok=True)
    return tools.write_cookie_file(cookies, os.path.join(d, f"{host}-{uuid.uuid4().hex[:8]}.txt"))


# ------------------------------------------------------------------ quality picker
class VideoDialog(QDialog):
    def __init__(self, parent, settings, url, title="", media=None, cookies=None, limiter=None, user_agent=""):
        super().__init__(parent)
        self.setWindowTitle(tr("video_title"))
        self.setMinimumSize(560, 420)
        self.page_url = url
        self.media = [m if isinstance(m, dict) else {"url": m, "type": "", "size": None} for m in (media or [])]
        for m in self.media:
            m.setdefault("type", "")
            m.setdefault("size", None)
        self.cookies = cookies or []
        self.page_title = (title or "").strip()
        self.user_agent = user_agent
        self.cookie_file = cookie_file_for(url, cookies)
        self.result = None
        self._probe_result = None
        self._prep = None          # setup progress (only if the bundled tools are missing)
        self._stop = threading.Event()
        self.limiter = limiter

        v = QVBoxLayout(self)
        self.title_lbl = QLabel(f"<b>{title or url}</b>")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.title_lbl)
        self.info = QLabel(tr("video_searching"))
        self.info.setWordWrap(True)
        v.addWidget(self.info)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self._accept(True))
        v.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("save_to")))
        self.folder = QLineEdit(settings["download_dir"])
        b = QPushButton(tr("browse"))
        b.clicked.connect(lambda: self.folder.setText(
            QFileDialog.getExistingDirectory(self, tr("save_to"), self.folder.text()) or self.folder.text()))
        row.addWidget(self.folder, 1)
        row.addWidget(b)
        v.addLayout(row)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(tr("cancel"))
        self.later = QPushButton(tr("later"))
        self.now = QPushButton(tr("start_now"))
        self.now.setDefault(True)
        for w in (self.later, self.now):
            w.setEnabled(False)
        cancel.clicked.connect(self.reject)
        self.later.clicked.connect(lambda: self._accept(False))
        self.now.clicked.connect(lambda: self._accept(True))
        for w in (cancel, self.later, self.now):
            btns.addWidget(w)
        v.addLayout(btns)

        threading.Thread(target=self._probe, daemon=True).start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check)
        self.timer.start(200)

    def _probe(self):
        if tools.missing():
            self._prep = 0.0
            ok = tools.auto_install(self.limiter, lambda f: setattr(self, "_prep", f), self._stop)
            if not ok and (self._stop.is_set() or not tools.find("yt-dlp")):
                if not self._stop.is_set():
                    self._probe_result = ([], "", tr("video_tools_failed"), self.page_url)
                return
            self._prep = None
        options, title, err, used_url = [], "", "", self.page_url
        candidates = [self.page_url] + [m["url"] for m in self.media if is_playlist(m)]
        for u in candidates:
            try:
                info = video.probe(u, self.cookie_file)
                if info.get("_type") == "playlist" and info.get("entries"):
                    info = info["entries"][0]
                options = [dict(o, kind="video") for o in video.quality_options(info)]
                title, used_url = info.get("title") or "", u
                break
            except Exception as e:  # noqa
                err = err or str(e)
        for m in self.media:
            if m["type"] == "resource":
                m["type"] = self._check_resource(m["url"])
        # video/audio files the page itself loaded -> normal multi-connection engine, with the
        # browser's cookies + user agent so logged-in sites (web apps, course platforms…) work
        for m in self.media:
            if not is_direct_media(m) or any(o.get("url") == m["url"] for o in options):
                continue
            path = urllib.parse.urlparse(m["url"]).path
            name = urllib.parse.unquote(os.path.basename(path.rstrip("/"))) or "video"
            kind = m["type"] if m["type"] not in ("", "element") else tr("video_on_page")
            headers = {"Referer": self.page_url}
            ck = cookie_header_for(m["url"], self.cookies)
            if ck:
                headers["Cookie"] = ck
            if self.user_agent:
                headers["User-Agent"] = self.user_agent
            # addresses like /files/abc/contents or /download say nothing - use the page title instead
            generic = os.path.splitext(name)[0].lower() in GENERIC_NAMES or not os.path.splitext(name)[1]
            filename = None
            if generic and self.page_title:
                from engine import safe_filename
                filename = safe_filename(self.page_title)[:120]
            options.append({"label": f"{tr('direct_file')} – {(filename or name)[:50]}  ({kind})", "format": "",
                            "size": m["size"], "kind": "file", "url": m["url"], "mp3": False, "headers": headers,
                            "filename": filename})
        if not options and err and ("Unsupported URL" in err or "Unable to extract" in err or "No video formats" in err):
            err = tr("video_unsupported")
        self._probe_result = (options, title, err, used_url)

    def _headers_for(self, url):
        h = {"Referer": self.page_url}
        ck = cookie_header_for(url, self.cookies)
        if ck:
            h["Cookie"] = ck
        if self.user_agent:
            h["User-Agent"] = self.user_agent
        return h

    def _check_resource(self, url):
        """Fetch the first bytes of a file the page loaded: return its video/audio type, or '' if it isn't one."""
        import requests
        from engine import sniff_ext
        try:
            r = requests.get(url, headers=dict(self._headers_for(url), Range="bytes=0-63"),
                             stream=True, timeout=(10, 15))
            try:
                ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                head = next(r.iter_content(64), b"") if r.status_code < 400 else b""
            finally:
                r.close()
        except Exception:  # noqa
            return ""
        if ctype.startswith(("video/", "audio/")):
            return ctype
        ext = sniff_ext(head)
        return {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska", ".mov": "video/quicktime",
                ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".avi": "video/x-msvideo"}.get(ext, "")

    def _check(self):
        if self._probe_result is None:
            if self._prep is not None:
                self.info.setText(f"{tr('video_preparing')} {self._prep * 100:.0f}%")
            else:
                self.info.setText(tr("video_searching"))
            return
        self.timer.stop()
        options, title, err, used_url = self._probe_result
        self.used_url = used_url
        if title:
            self.title_lbl.setText(f"<b>{title}</b>")
        self.video_title = title
        if not options:
            msg = err or tr("video_none")
            if "Sign in" in msg or "bot" in msg:
                msg += "\n\n" + tr("video_signin")
            from theme import colors
            self.info.setText(f"<span style='color:{colors()['bad']}'>{msg}</span>")
            return
        self.info.setText(tr("video_pick"))
        for o in options:
            it = QListWidgetItem(f"{o['label']}" + (f"    ·    ~{human_size(o['size'])}" if o.get("size") else ""))
            it.setData(Qt.ItemDataRole.UserRole, o)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.later.setEnabled(True)
        self.now.setEnabled(True)

    def reject(self):
        self._stop.set()
        if self.cookie_file:          # cancelled: don't leave cookies on disk
            try:
                os.remove(self.cookie_file)
            except OSError:
                pass
        super().reject()

    def _accept(self, now):
        it = self.list.currentItem()
        if not it:
            return
        self.result = {"option": it.data(Qt.ItemDataRole.UserRole), "folder": self.folder.text(),
                       "start_now": now, "url": self.used_url, "title": self.video_title,
                       "cookie_file": self.cookie_file}
        self.accept()
