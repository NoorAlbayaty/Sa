import os
import datetime
import time
import sys
import subprocess

from PyQt6.QtCore import (Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
                          QTimer, QTime)
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QGuiApplication, QKeySequence, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QTableView, QStyledItemDelegate, QStyle,
    QApplication, QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QSpinBox, QFileDialog, QDialogButtonBox, QMessageBox, QCheckBox, QComboBox, QTimeEdit,
    QTabWidget, QWidget, QListWidget, QListWidgetItem, QLabel, QMenu,
    QSystemTrayIcon, QHeaderView, QAbstractItemView, QToolBar, QToolButton)

from engine import Status
from i18n import tr, human_size, human_speed, human_eta
import server
import theme
import autostart
import browsers
from manager import log_activity
import tools
from video_gui import VideoDialog, is_video_page

COLS = ["col_name", "col_size", "col_progress", "col_speed", "col_eta", "col_conn", "col_status"]
ASSETS = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "assets")

STYLE = theme.qss()          # light stylesheet (the live theme is applied app-wide by theme.apply)

STATUS_KEY = {Status.QUEUED: "st_queued", Status.CONNECTING: "st_connecting",
              Status.DOWNLOADING: "st_downloading", Status.PAUSED: "st_paused",
              Status.COMPLETED: "st_completed", Status.ERROR: "st_error"}


def app_icon():
    p = os.path.join(ASSETS, "icon.png")
    return QIcon(p) if os.path.exists(p) else QIcon()


def open_path(path, select=False):
    if sys.platform == "win32":
        if select:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path] if select else ["open", path])     # Finder
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path) if select else path])


# ---------------------------------------------------------------- model
class TaskModel(QAbstractTableModel):
    def __init__(self, manager):
        super().__init__()
        self.m = manager

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.m.tasks)

    def columnCount(self, parent=QModelIndex()):
        return len(COLS)

    def headerData(self, section, orient, role=Qt.ItemDataRole.DisplayRole):
        if orient == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr(COLS[section])

    def task(self, row):
        return self.m.tasks[row]

    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        if not idx.isValid() or idx.row() >= len(self.m.tasks):
            return None
        t = self.m.tasks[idx.row()]
        c = COLS[idx.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if c == "col_name":
                return t.filename or t.url
            if c == "col_size":
                return human_size(t.size)
            if c == "col_progress":
                return t.progress
            if c == "col_speed":
                return human_speed(t.speed) if t.status in Status.ACTIVE else ""
            if c == "col_eta":
                return human_eta(t.eta) if t.status in Status.ACTIVE else ""
            if c == "col_conn":
                return str(t.active_connections) if t.status in Status.ACTIVE else ""
            if c == "col_status":
                s = tr(STATUS_KEY.get(t.status, t.status))
                if getattr(t, "stage", "") == "merging" and t.status == Status.DOWNLOADING:
                    s = tr("st_merging")
                if t.status == Status.ERROR and getattr(t, "network_error", False):
                    s = tr("st_waiting_net")
                elif t.status == Status.ERROR and t.error:
                    s += f" – {t.error[:60]}"
                return s
        if role == Qt.ItemDataRole.ToolTipRole:
            src = {"browser": tr("src_browser"), "manual": tr("src_manual")}.get(getattr(t, "source", "manual"), "")
            tip = t.url + "\n" + tr("added_on") + " " + \
                datetime.datetime.fromtimestamp(t.added).strftime("%Y-%m-%d %H:%M") + " · " + src
            if t.probed and not t.resumable:
                tip += "\n" + tr("no_resume")
            if t.error:
                tip += "\n" + t.error
            return tip
        if role == Qt.ItemDataRole.ForegroundRole and c == "col_status":
            c = theme.colors()
            return QColor({Status.COMPLETED: c["ok"], Status.ERROR: c["bad"],
                           Status.DOWNLOADING: c["accent_text"]}.get(t.status, c["muted"]))
        return None

    def refresh(self):
        if self.m.tasks:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.m.tasks) - 1, len(COLS) - 1))


class FilterModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.mode = "flt_all"

    def set_mode(self, mode):
        self.mode = mode
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        t = self.sourceModel().task(row)
        if self.mode == "flt_active":
            return t.status in Status.ACTIVE or t.status == Status.QUEUED
        if self.mode == "flt_completed":
            return t.status == Status.COMPLETED
        if self.mode == "flt_unfinished":
            return t.status != Status.COMPLETED
        return True


class ProgressDelegate(QStyledItemDelegate):
    """Progress bar drawn in the current theme's colors (readable in light and dark mode)."""
    def paint(self, painter, option, index):
        from PyQt6.QtGui import QPainterPath
        from PyQt6.QtCore import QRectF
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(theme.colors()["selection"]))
        c = theme.colors()
        val = max(0.0, min(1.0, float(index.data() or 0.0)))
        r = QRectF(option.rect.adjusted(4, 8, -4, -8))
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        track = QPainterPath()
        track.addRoundedRect(r, 5, 5)
        painter.fillPath(track, QColor(c["progress_bg"]))
        done = QRectF(r)
        rtl = option.direction == Qt.LayoutDirection.RightToLeft
        done.setWidth(r.width() * val)
        if rtl:
            done.moveRight(r.right())
        if val > 0:
            painter.setClipPath(track)
            painter.fillRect(done, QColor(c["accent"]))
            painter.setClipping(False)
        text = f"{val * 100:.1f}%"
        painter.setPen(QColor(c["text"]))                       # text on the empty part
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        if val > 0:                                             # white text where it sits on the blue part
            painter.setClipRect(done)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


# ---------------------------------------------------------------- "download complete" pop-up
class CompletePopup(QWidget):
    """Small window in the corner of the screen when a download finishes (like IDM):
    Open the file, show it in its folder, or close. Disappears by itself after a while."""
    WIDTH, SECONDS = 360, 12
    _open = []                                         # pop-ups on screen (stacked upwards)

    def __init__(self, task):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("completePopup")
        c = theme.colors()
        self.setStyleSheet(f"#completePopup {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:10px; }}")
        self.path = task.path
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 12, 12)
        top = QHBoxLayout()
        title = QLabel(f"<b>✓ {tr('done_title')}</b>")
        title.setStyleSheet(f"color:{c['ok']}; font-size:13px;")
        close = QPushButton("×")
        close.setFixedSize(26, 26)
        close.setToolTip("Close")
        close.setStyleSheet(f"border:none; background:transparent; padding:0; font-size:18px; color:{c['muted']};")
        close.clicked.connect(self.close)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(close)
        v.addLayout(top)
        name = QLabel(task.filename)
        name.setStyleSheet("font-size:13px;")
        name.setToolTip(self.path)
        name.setMaximumWidth(self.WIDTH - 40)
        name.setText(name.fontMetrics().elidedText(task.filename, Qt.TextElideMode.ElideMiddle, self.WIDTH - 40))
        v.addWidget(name)
        size = QLabel(f"{human_size(task.size)}  ·  {os.path.dirname(self.path)}")
        size.setStyleSheet(f"color:{c['muted']}; font-size:11px;")
        size.setText(size.fontMetrics().elidedText(size.text(), Qt.TextElideMode.ElideMiddle, self.WIDTH - 40))
        v.addWidget(size)
        row = QHBoxLayout()
        row.addStretch()
        b_folder = QPushButton(tr("open_folder"))
        b_open = QPushButton(tr("open"))
        b_open.setObjectName("primary")
        b_folder.clicked.connect(lambda: self._act(select=True))
        b_open.clicked.connect(lambda: self._act(select=False))
        row.addWidget(b_folder)
        row.addWidget(b_open)
        v.addLayout(row)
        self.setFixedWidth(self.WIDTH)
        self.adjustSize()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(self.SECONDS * 1000)

    def _act(self, select):
        if os.path.exists(self.path):
            open_path(self.path, select=select)
        self.close()

    def enterEvent(self, e):                            # keep it while the mouse is over it
        self.timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.timer.start(4000)
        super().leaveEvent(e)

    def popup(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        y = screen.bottom() - 12
        for p in CompletePopup._open:
            y -= p.height() + 8
        self.move(screen.right() - self.width() - 12, y - self.height())
        CompletePopup._open.append(self)
        self.show()

    def closeEvent(self, e):
        if self in CompletePopup._open:
            CompletePopup._open.remove(self)
        super().closeEvent(e)


# ---------------------------------------------------------------- dialogs
class AddDialog(QDialog):
    def __init__(self, parent, settings, url="", filename=""):
        super().__init__(parent)
        self.setWindowTitle(tr("add_url"))
        self.setMinimumWidth(560)
        self.start_now = True
        f = QFormLayout(self)
        self.url = QLineEdit(url)
        if not url:
            clip = QGuiApplication.clipboard().text().strip()
            if clip.startswith(("http://", "https://")):
                self.url.setText(clip)
        self.url.setPlaceholderText("https://…")
        f.addRow(tr("url"), self.url)
        row = QHBoxLayout()
        self.folder = QLineEdit(settings["download_dir"])
        b = QPushButton(tr("browse"))
        b.clicked.connect(self._browse)
        row.addWidget(self.folder)
        row.addWidget(b)
        f.addRow(tr("save_to"), row)
        self.name = QLineEdit(filename)
        f.addRow(tr("filename"), self.name)
        self.conn = QSpinBox()
        self.conn.setRange(1, 32)
        self.conn.setValue(int(settings["connections"]))
        f.addRow(tr("connections"), self.conn)
        btns = QHBoxLayout()
        btns.addStretch()
        later = QPushButton(tr("later"))
        now = QPushButton(tr("start_now"))
        now.setDefault(True)
        cancel = QPushButton(tr("cancel"))
        later.clicked.connect(lambda: self._accept(False))
        now.clicked.connect(lambda: self._accept(True))
        cancel.clicked.connect(self.reject)
        for w in (cancel, later, now):
            btns.addWidget(w)
        f.addRow(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("save_to"), self.folder.text())
        if d:
            self.folder.setText(d)

    def _accept(self, now):
        if not self.url.text().strip().startswith(("http://", "https://")):
            QMessageBox.warning(self, tr("add_url"), tr("invalid_url"))
            return
        self.start_now = now
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent, s):
        super().__init__(parent)
        self.s = s
        self.setWindowTitle(tr("settings"))
        self.setMinimumWidth(520)
        tabs = QTabWidget()

        g = QWidget()
        gf = QFormLayout(g)
        row = QHBoxLayout()
        self.folder = QLineEdit(s["download_dir"])
        b = QPushButton(tr("browse"))
        b.clicked.connect(lambda: self.folder.setText(
            QFileDialog.getExistingDirectory(self, tr("save_to"), self.folder.text()) or self.folder.text()))
        row.addWidget(self.folder)
        row.addWidget(b)
        gf.addRow(tr("save_to"), row)
        self.theme = QComboBox()
        for mode in theme.MODES:
            self.theme.addItem(tr("theme_" + mode), mode)
        self.theme.setCurrentIndex(max(0, theme.MODES.index(s.get("theme", "system"))))
        gf.addRow(tr("theme"), self.theme)
        self.browser = QCheckBox(tr("browser_dialog"))
        self.browser.setChecked(s["browser_show_dialog"])
        self.notify = QCheckBox(tr("notify"))
        self.notify.setChecked(s["notify_on_complete"])
        self.login = QCheckBox(tr("start_login"))
        self.login.setChecked(autostart.is_enabled())
        self.login.setVisible(autostart.supported())
        self.tray = QCheckBox(tr("close_tray"))
        self.tray.setChecked(s["close_to_tray"])
        for w in (self.browser, self.notify, self.tray, self.login):
            gf.addRow(w)
        tabs.addTab(g, tr("general"))

        c = QWidget()
        cf = QFormLayout(c)
        self.conn = QSpinBox()
        self.conn.setRange(1, 32)
        self.conn.setValue(int(s["connections"]))
        self.maxc = QSpinBox()
        self.maxc.setRange(1, 20)
        self.maxc.setValue(int(s["max_concurrent"]))
        self.limit = QSpinBox()
        self.limit.setRange(0, 1_000_000)
        self.limit.setSingleStep(100)
        self.limit.setValue(int(s["speed_limit_kb"]))
        cf.addRow(tr("connections"), self.conn)
        cf.addRow(tr("max_concurrent"), self.maxc)
        cf.addRow(tr("speed_limit"), self.limit)
        tabs.addTab(c, tr("tab_conn"))

        sc = QWidget()
        sf = QFormLayout(sc)
        self.sched = QCheckBox(tr("sched_enable"))
        self.sched.setChecked(s["sched_enabled"])
        self.t_start = QTimeEdit(QTime.fromString(s["sched_start"] or "02:00", "HH:mm"))
        self.t_start.setDisplayFormat("HH:mm")
        self.stop_on = QCheckBox(tr("sched_stop"))
        self.stop_on.setChecked(bool(s["sched_stop"]))
        self.t_stop = QTimeEdit(QTime.fromString(s["sched_stop"] or "07:00", "HH:mm"))
        self.t_stop.setDisplayFormat("HH:mm")
        sf.addRow(self.sched, self.t_start)
        sf.addRow(self.stop_on, self.t_stop)
        tabs.addTab(sc, tr("scheduler"))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText(tr("ok"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        v.addWidget(tabs)
        v.addWidget(bb)

    def _save(self):
        s = self.s
        s["download_dir"] = self.folder.text()
        s["theme"] = self.theme.currentData()
        s["browser_show_dialog"] = self.browser.isChecked()
        s["notify_on_complete"] = self.notify.isChecked()
        s["close_to_tray"] = self.tray.isChecked()
        if autostart.supported() and self.login.isChecked() != autostart.is_enabled():
            try:
                autostart.set_enabled(self.login.isChecked())
            except OSError:
                pass
        s["connections"] = self.conn.value()
        s["max_concurrent"] = self.maxc.value()
        s["speed_limit_kb"] = self.limit.value()
        s["sched_enabled"] = self.sched.isChecked()
        s["sched_start"] = self.t_start.time().toString("HH:mm")
        s["sched_stop"] = self.t_stop.time().toString("HH:mm") if self.stop_on.isChecked() else ""
        s.save()
        self.accept()


# ---------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self, manager, settings, server_ok):
        super().__init__()
        self.m = manager
        self.s = settings
        self._quitting = False
        self._started_at = time.monotonic()
        self._asking = set()                    # links that currently have an open "add" window
        self._done_events = []
        self.m.on_complete = lambda t: self._done_events.append(t)

        self.setWindowTitle(tr("app_title"))
        self.setWindowIcon(app_icon())
        self.resize(1100, 620)

        # toolbar
        tb = QToolBar()
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        self.act_add = self._act(tb, "add_url", self.add_dialog, "Ctrl+N")
        tb.widgetForAction(self.act_add).setObjectName("primary")
        self._act(tb, "add_video", lambda: self.video_dialog(), "Ctrl+Shift+N")
        self._act(tb, "resume", self.resume_selected)
        self._act(tb, "pause", self.pause_selected)
        self._act(tb, "pause_all", self.m.pause_all)
        self._act(tb, "delete", self.delete_selected, "Delete")
        tb.addSeparator()
        self._act(tb, "start_queue", self.m.start_queue)
        self._act(tb, "stop_queue", self.m.stop_queue)
        tb.addSeparator()
        self._act(tb, "settings", self.settings_dialog)
        # appearance: follow the system, or force light / dark
        self.theme_menu = QMenu(self)
        group = QActionGroup(self)
        self.theme_actions = {}
        for mode in theme.MODES:
            a = QAction(tr("theme_" + mode), self, checkable=True)
            a.setChecked(self.s.get("theme", "system") == mode)
            a.triggered.connect(lambda checked=False, m=mode: self.set_theme(m))
            group.addAction(a)
            self.theme_menu.addAction(a)
            self.theme_actions[mode] = a
        self.act_theme = QAction(tr("theme"), self)
        self.act_theme.setMenu(self.theme_menu)
        tb.addAction(self.act_theme)
        tb.widgetForAction(self.act_theme).setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.update_theme_label()

        # sidebar
        self.side = QListWidget()
        self.side.setFixedWidth(170)
        for key in ("flt_all", "flt_active", "flt_unfinished", "flt_completed"):
            it = QListWidgetItem(tr(key))
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.side.addItem(it)
        self.side.setCurrentRow(0)
        self.side.currentItemChanged.connect(
            lambda cur, _: self.proxy.set_mode(cur.data(Qt.ItemDataRole.UserRole)) if cur else None)

        # table
        self.model = TaskModel(self.m)
        self.proxy = FilterModel()
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setItemDelegateForColumn(COLS.index("col_progress"), ProgressDelegate(self.view))
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setAlternatingRowColors(True)
        self.view.setShowGrid(False)
        self.view.verticalHeader().hide()
        self.view.verticalHeader().setDefaultSectionSize(34)
        h = self.view.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, w in enumerate([0, 90, 150, 95, 100, 65, 125]):
            if w:
                self.view.setColumnWidth(i, w)
        self.view.setWordWrap(False)                                  # one line per download
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)      # "ubuntu-24.04…amd64.iso"
        self.NAME_MIN = 220
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.context_menu)
        self.view.doubleClicked.connect(self.on_double_click)

        self.side.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.side)
        lay.addWidget(self.view, 1)
        self.setCentralWidget(central)

        self.lbl_speed = QLabel()
        self.btn_ext = QPushButton()
        self.btn_ext.setFlat(True)
        self.btn_ext.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ext.clicked.connect(self.add_to_browser)
        self.statusBar().addPermanentWidget(self.btn_ext)
        self.statusBar().addPermanentWidget(self.lbl_speed)
        try:
            for b in browsers.register_external():
                log_activity(f"registered the extension with {b} (it will offer it on next start)")
        except Exception:  # noqa
            pass
        self.update_ext_status()
        self.statusBar().showMessage(tr("server_ok") if server_ok else tr("server_busy"))

        # tray
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        menu.addAction(tr("show"), lambda: self.show_normal())
        menu.addAction(tr("add_url"), lambda: self.add_dialog())
        menu.addAction(tr("add_video"), lambda: self.video_dialog())
        menu.addSeparator()
        menu.addAction(tr("quit"), lambda: self.quit_app())
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_normal()
                                    if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.setToolTip(tr("app_title"))
        self.last_done = None
        self.tray.messageClicked.connect(
            lambda: open_path(self.last_done.path, select=True)
            if self.last_done and os.path.exists(self.last_done.path) else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        cols = sum(self.view.columnWidth(i) for i in range(1, len(COLS)))
        min_w = max(tb.sizeHint().width() + 16, self.side.width() + self.NAME_MIN + cols + 24)
        self.setMinimumSize(min_w, 460)      # smaller than this the toolbar and list stop being usable
        if self.width() < min_w:
            self.resize(min_w, self.height())

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)
        tools.prepare()

    def _act(self, tb, key, fn, shortcut=None):
        a = QAction(tr(key), self)
        a.triggered.connect(lambda checked=False, f=fn: f())
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        tb.addAction(a)
        return a

    # ---- periodic
    def tick(self):
        self.m.tick()
        rows_before = self.model.rowCount()
        if rows_before != len(self.m.tasks):
            self.model.layoutChanged.emit()
        self.model.refresh()
        self.proxy.invalidateFilter() if self.proxy.mode != "flt_all" else None
        info = f"{tr('total_speed')}: {human_speed(self.m.total_speed()) or '0 B/s'}   ·   " \
               f"{tr('active')}: {self.m.active_count()}"
        if self.m.queue_running:
            info += f"   ·   {tr('queue_on')}"
        self.lbl_speed.setText(info + "  ")
        while not server.incoming.empty():
            item = server.incoming.get()
            if item.get("type") == "show":
                self.show_normal()
                continue
            if item.get("type") == "hello":
                seen = dict(self.s.get("ext_seen", {}))
                seen[item["browser"]] = time.time()
                self.s["ext_seen"] = seen
                self.s.save()
                self.update_ext_status()
                continue
            self.handle_browser(item)
        while self._done_events:
            t = self._done_events.pop(0)
            if self.s["notify_on_complete"]:
                self.last_done = t
                if len(CompletePopup._open) < 4:            # never cover the whole screen
                    CompletePopup(t).popup()
                elif self.tray.isVisible():                  # many at once: the system notification instead
                    self.tray.showMessage(tr("done_title"), t.filename, app_icon(), 4000)

    # ---- actions
    def selected_tasks(self):
        rows = {self.proxy.mapToSource(i).row() for i in self.view.selectionModel().selectedRows()}
        return [self.m.tasks[r] for r in sorted(rows) if r < len(self.m.tasks)]

    def add_dialog(self, url="", filename="", headers=None, source="manual"):
        self.show_normal()
        d = AddDialog(self, self.s, url, filename)
        if d.exec():
            if is_video_page(d.url.text().strip()) and not headers:
                return self.video_dialog(d.url.text().strip())
            if source == "manual" and self.is_repeat(d.url.text().strip()):
                return                          # already in the list / user chose not to download again
            self._add(d.url.text().strip(), d.folder.text(), d.name.text().strip() or None,
                      d.conn.value(), headers, d.start_now, source)

    def _add(self, url, folder, name, conn, headers, start_now, source="manual"):
        self.model.beginInsertRows(QModelIndex(), len(self.m.tasks), len(self.m.tasks))
        self.m.add(url, folder, name, conn, headers, start_now, source)
        self.model.endInsertRows()

    def set_theme(self, mode):
        self.s["theme"] = mode
        self.s.save()
        theme.apply(mode)
        for m, a in self.theme_actions.items():
            a.setChecked(m == mode)
        self.update_theme_label()
        self.update_ext_status()
        self.view.viewport().update()

    def update_theme_label(self):
        icon = "◐" if self.s.get("theme", "system") == "system" else ("☾" if theme.is_dark() else "☀")
        self.act_theme.setText(f"{icon}  {tr('theme')}")

    def connected_browsers(self):
        month = 30 * 86400
        return sorted(b for b, t in self.s.get("ext_seen", {}).items() if time.time() - t < month)

    def update_ext_status(self):
        found = self.connected_browsers()
        if found:
            self.btn_ext.setText("✓ " + tr("ext_ok") + ": " + ", ".join(found))
            self.btn_ext.setStyleSheet(f"color:{theme.colors()['ok']}; border:none; padding:2px 8px; background:transparent;")
        else:
            self.btn_ext.setText("⚠ " + tr("ext_add"))
            self.btn_ext.setStyleSheet(f"color:{theme.colors()['bad']}; border:none; padding:2px 8px; "
                                       "font-weight:600; background:transparent;")

    def add_to_browser(self):
        """Open the store page so the user can add the extension (or explain how, before it's published)."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        stores = browsers.configured()
        if not stores:
            folder = os.path.join(os.path.dirname(sys.executable), "extension") if getattr(sys, "frozen", False) \
                else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension")
            QMessageBox.information(self, tr("ext_add"), tr("ext_manual").format(folder=folder))
            return
        menu = QMenu(self)
        for b in stores:
            menu.addAction(tr("ext_open_store").format(browser=b),
                           lambda b=b: QDesktopServices.openUrl(QUrl(browsers.store_url(b))))
        menu.exec(self.btn_ext.mapToGlobal(self.btn_ext.rect().topLeft()))

    def video_dialog(self, url="", title="", media=None, cookies=None, user_agent=""):
        self.show_normal()
        if not url:
            from PyQt6.QtWidgets import QInputDialog
            clip = QGuiApplication.clipboard().text().strip()
            url, ok = QInputDialog.getText(self, tr("add_video"), tr("video_url"),
                                           text=clip if clip.startswith("http") else "")
            url = url.strip()
            if not ok or not url.startswith(("http://", "https://")):
                return
        d = VideoDialog(self, self.s, url, title, media, cookies, self.m.limiter, user_agent)
        if not d.exec() or not d.result:
            return
        r = d.result
        o = r["option"]
        self.model.beginInsertRows(QModelIndex(), len(self.m.tasks), len(self.m.tasks))
        if o.get("kind") == "file":
            self.m.add(o["url"], r["folder"], o.get("filename"), None, o.get("headers") or {"Referer": url}, r["start_now"],
                       source="browser" if cookies is not None else "manual")
        else:
            self.m.add_video(r["url"], r["folder"], o["format"], r["title"], o.get("mp3", False),
                             r["cookie_file"], o.get("size"), r["start_now"], source="browser" if cookies is not None else "manual")
        self.model.endInsertRows()

    def is_repeat(self, url):
        """True if this link is already in the list. Finished files ask 'download again?' (default No)."""
        t = self.m.find_existing(url)
        if t is None:
            return False
        if t.status != Status.COMPLETED:
            log_activity(f"ignored browser request - already in the list: {url}")
            self.statusBar().showMessage(f"{tr('already_listed')}: {t.filename}", 8000)
            return True
        when = datetime.datetime.fromtimestamp(t.finished or t.added).strftime("%Y-%m-%d %H:%M")
        self.show_normal()
        box = QMessageBox(QMessageBox.Icon.Question, tr("dup_title"),
                          tr("dup_text").format(name=t.filename, when=when), parent=self)
        yes = box.addButton(tr("download_again"), QMessageBox.ButtonRole.YesRole)
        no = box.addButton(tr("cancel"), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no)
        box.exec()
        if box.clickedButton() is yes:
            log_activity(f"user chose to download again: {url}")
            return False
        log_activity(f"skipped repeated browser download: {url}")
        return True

    def handle_browser(self, item):
        url = item["url"]
        if url in self._asking:                 # a window for this link is already open
            return
        if self.is_repeat(url):
            return
        self._asking.add(url)
        try:
            self._handle_browser(item)
        finally:
            self._asking.discard(url)

    def _handle_browser(self, item):
        if item.get("type") == "video":
            return self.video_dialog(item["url"], item.get("title", ""), item.get("media"), item.get("cookies"),
                                     item.get("user_agent", ""))
        just_started = time.monotonic() - self._started_at < 120
        if self.s["browser_show_dialog"] or just_started:
            self.add_dialog(item["url"], item["filename"], item["headers"], source="browser")
        else:
            self._add(item["url"], None, item["filename"] or None, None, item["headers"], True, "browser")

    def resume_selected(self):
        for t in self.selected_tasks():
            self.m.start(t)

    def pause_selected(self):
        for t in self.selected_tasks():
            self.m.pause(t)

    def delete_selected(self, with_file=False):
        tasks = self.selected_tasks()
        if not tasks:
            return
        if QMessageBox.question(self, tr("delete"), tr("confirm_delete")) != QMessageBox.StandardButton.Yes:
            return
        self.model.beginResetModel()
        for t in tasks:
            self.m.remove(t, delete_file=with_file)
        self.model.endResetModel()

    def settings_dialog(self):
        if SettingsDialog(self, self.s).exec():
            self.m.apply_settings()
            self.set_theme(self.s.get("theme", "system"))

    def on_double_click(self, idx):
        t = self.m.tasks[self.proxy.mapToSource(idx).row()]
        if t.status == Status.COMPLETED and os.path.exists(t.path):
            open_path(t.path)
        elif t.status != Status.COMPLETED:
            self.m.start(t) if t.status not in Status.ACTIVE else self.m.pause(t)

    def context_menu(self, pos):
        tasks = self.selected_tasks()
        if not tasks:
            return
        t = tasks[0]
        menu = QMenu(self)
        if t.status == Status.COMPLETED:
            menu.addAction(tr("open"), lambda: open_path(t.path))
            menu.addAction(tr("open_folder"), lambda: open_path(t.path, select=True))
            menu.addAction(tr("redownload"), lambda: self.m.redownload(t))
        else:
            menu.addAction(tr("resume"), self.resume_selected)
            menu.addAction(tr("pause"), self.pause_selected)
            menu.addAction(tr("move_to_queue"),
                           lambda: [setattr(x, "status", Status.QUEUED) for x in tasks
                                    if x.status in (Status.PAUSED, Status.ERROR)])
            menu.addAction(tr("redownload"), lambda: self.m.redownload(t))
        menu.addSeparator()
        menu.addAction(tr("copy_url"), lambda: QGuiApplication.clipboard().setText(t.url))
        menu.addAction(tr("delete"), lambda: self.delete_selected(False))
        menu.addAction(tr("delete_with_file"), lambda: self.delete_selected(True))
        menu.exec(self.view.viewport().mapToGlobal(pos))

    # ---- window / tray
    def show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if not self._quitting and self.s["close_to_tray"] and self.tray.isVisible():
            e.ignore()
            self.hide()
            return
        self.quit_app()

    def quit_app(self):
        self._quitting = True
        self.timer.stop()
        self.m.shutdown()
        self.tray.hide()
        QApplication.quit()
