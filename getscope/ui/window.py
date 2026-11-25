"""Janela principal do GetScope."""
import os
import subprocess
import sys

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QStatusBar,
                               QVBoxLayout, QWidget)

from scopekit.ui import ask, btn, message, set_prop

from ..app import APP_NAME, VERSION
from ..core import engine, formats, paths
from ..core.jobs import ACTIVE, AnalyzeWorker, DownloadManager, Env, History, safe_folder
from ..core.settings import Settings
from .dialogs import AboutDialog, PlaylistDialog, VideoDialog
from .page_diag import DiagPage
from .page_downloads import DownloadsPage, looks_like_url
from .page_history import HistoryPage
from .page_settings import SettingsPage
from .widgets import app_icon, logo_pixmap

NAV = [("downloads", "DOWNLOADS"), ("history", "HISTÓRICO"), ("diag", "DIAGNÓSTICO"), ("settings", "CONFIGURAÇÕES")]


class MainWindow(QMainWindow):
    def __init__(self, settings=None, env=None, history=None, manager=None, startup_checks=True):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1320, 820)
        self.setMinimumSize(1000, 640)
        self.setAcceptDrops(True)
        self.settings = settings or Settings()
        self.env = env or Env()
        self.history = history or History()
        self.m = manager or DownloadManager(self.settings, self.env, self.history)
        self._analyzing = None
        self._last_clip = None
        self._restart_ready = None

        root = QWidget()
        root.setObjectName("Root")
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._header())
        self.banner = self._banner()
        rl.addWidget(self.banner)
        self.stack = QStackedWidget()
        self.p_down = DownloadsPage(self.m, self.settings)
        self.p_hist = HistoryPage(self.history)
        self.p_diag = DiagPage(self.env, self.settings)
        self.p_set = SettingsPage(self.settings)
        self.pages = {"downloads": self.p_down, "history": self.p_hist, "diag": self.p_diag, "settings": self.p_set}
        for p in self.pages.values():
            self.stack.addWidget(p)
        rl.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.status = QLabel()
        sb.addWidget(self.status, 1)
        self.ver = QLabel(f"v{VERSION}")
        sb.addPermanentWidget(self.ver)
        self.setStatusBar(sb)

        self.p_down.analyze_requested.connect(self.analyze)
        self.p_hist.redownload.connect(self._redownload)
        self.p_diag.changed.connect(self._update_status)
        self.p_diag.engine_updated.connect(self._engine_updated)
        self.p_set.saved.connect(self._settings_saved)
        self.m.log.connect(self.p_diag.log)
        self.m.job_finished.connect(self._job_finished)
        self.m.job_changed.connect(lambda *_: self._update_title())
        QGuiApplication.instance().applicationStateChanged.connect(self._app_state)

        self.go("downloads")
        self._update_status()
        restored = self.m.load_queue()
        if restored:
            self.show_banner(f"{restored} download{'s' if restored > 1 else ''} da última sessão "
                             f"{'ficaram' if restored > 1 else 'ficou'} pausado{'s' if restored > 1 else ''}.",
                             "▶  RETOMAR TODOS", lambda: (self.m.resume_all(), self.hide_banner()))
        if startup_checks:
            if self.settings["check_engine_on_start"]:
                QTimer.singleShot(2500, lambda: self.p_diag.check_engine(silent=True))
            QTimer.singleShot(400, self._first_run_hint)

    # ------------------------------------------------------------ montagem
    def _header(self):
        h = QWidget()
        h.setObjectName("Header")
        h.setAttribute(Qt.WA_StyledBackground, True)
        h.setFixedHeight(58)
        l = QHBoxLayout(h)
        l.setContentsMargins(16, 0, 16, 0)
        l.setSpacing(6)
        lg = QLabel()
        lg.setPixmap(logo_pixmap(34))
        l.addWidget(lg)
        l.addSpacing(6)
        name = QLabel(APP_NAME.upper())
        name.setObjectName("AppName")
        l.addWidget(name)
        l.addSpacing(22)
        self.nav = {}
        for key, text in NAV:
            b = btn(text, "nav", lambda _=False, k=key: self.go(k))
            self.nav[key] = b
            l.addWidget(b)
        l.addStretch(1)
        self.pill = btn("", "pill", lambda: self.go("diag"))
        l.addWidget(self.pill)
        l.addSpacing(8)
        l.addWidget(btn("⟳  ATUALIZAR", None, self.refresh_all, "Verificar de novo FFmpeg, runtime JavaScript e pasta"))
        l.addWidget(btn("ⓘ  SOBRE", None, self.about))
        return h

    def _banner(self):
        w = QWidget()
        w.setObjectName("Banner")
        w.setAttribute(Qt.WA_StyledBackground, True)
        l = QHBoxLayout(w)
        l.setContentsMargins(18, 8, 12, 8)
        self.banner_text = QLabel()
        self.banner_text.setObjectName("BannerText")
        self.banner_text.setWordWrap(True)
        l.addWidget(self.banner_text, 1)
        self.banner_btn = btn("", "green", lambda: self._banner_action and self._banner_action())
        self._banner_action = None
        l.addWidget(self.banner_btn)
        l.addWidget(btn("✕", "tool", self.hide_banner, "Fechar aviso"))
        w.hide()
        return w

    def show_banner(self, text, button=None, action=None):
        self.banner_text.setText("⚠  " + text if not text.startswith(("✓", "⚠")) else text)
        self._banner_action = action
        self.banner_btn.setVisible(bool(button))
        if button:
            self.banner_btn.setText(button)
        self.banner.show()

    def hide_banner(self):
        self.banner.hide()

    def go(self, key):
        self.stack.setCurrentWidget(self.pages[key])
        for k, b in self.nav.items():
            set_prop(b, "active", "true" if k == key else "false")
        if key == "history":
            self.p_hist.reload()
        if key == "settings":
            self.p_set.load()

    # ------------------------------------------------------------ estado
    def _update_status(self):
        pr = self.p_diag.problems()
        if pr:
            self.pill.setText(f"⚠  {len(pr)} PENDÊNCIA{'S' if len(pr) > 1 else ''}")
            set_prop(self.pill, "state", "warn")
            self.pill.setToolTip("Falta: " + ", ".join(pr) + ". Clique para ver o Diagnóstico.")
        else:
            self.pill.setText("●  PRONTO")
            set_prop(self.pill, "state", "ok")
            self.pill.setToolTip("Motor, FFmpeg e runtime JavaScript encontrados.")
        ei = engine.info()
        ff = "✓" if self.env.ffmpeg else "✕"
        js = self.env.js[0]["name"].capitalize() + " ✓" if self.env.js else "JavaScript ✕"
        self.status.setText(f"Pasta: {self.settings['download_dir']}    ·    Motor yt-dlp {ei['version']}"
                            f"{' (atualizado)' if ei['source'] == 'updated' else ''}    ·    FFmpeg {ff}    ·    {js}")

    def _update_title(self):
        act = [j for j in self.m.jobs if j.status in ACTIVE]
        if act:
            pct = sum(j.progress for j in act) / len(act)
            self.setWindowTitle(f"{pct:.0f}% · {len(act)} baixando — {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)

    def _settings_saved(self):
        self._update_status()
        self.p_down.ck_direct.setChecked(self.settings["paste_action"] == "direct")
        self.p_diag.refresh(log=False)
        self.m.schedule()

    def _first_run_hint(self):
        pr = self.p_diag.problems()
        if pr and not self.banner.isVisible():
            what = " e ".join(", ".join(pr).rsplit(", ", 1))
            self.show_banner(f"Falta {what} para baixar em todas as qualidades. Dá para resolver em um clique.",
                             "ABRIR DIAGNÓSTICO", lambda: (self.go("diag"), self.hide_banner()))

    # ------------------------------------------------------------ análise
    def analyze(self, url):
        if self._analyzing:
            return
        self.p_down.set_busy(True)
        self.status.setText(f"Analisando {url} …")
        w = AnalyzeWorker(url, self.settings, self.env)
        w.sig.done.connect(lambda info: self._analyzed(url, info))
        w.sig.failed.connect(self._analyze_failed)
        self._analyzing = w
        QThreadPool.globalInstance().start(w)

    def _analyze_failed(self, msg, hint, raw):
        self._analyzing = None
        self.p_down.set_busy(False)
        self._update_status()
        self.p_diag.log("error", f"Análise: {raw}")
        message(self, "Não foi possível abrir o link", msg, "error", hint or None)

    def _analyzed(self, url, info):
        self._analyzing = None
        self.p_down.set_busy(False)
        self._update_status()
        direct = self.settings["paste_action"] == "direct"
        is_list = info.get("_type") in ("playlist", "multi_video") or (info.get("entries") is not None)
        if is_list:
            dlg = PlaylistDialog(self, info, self.settings, self.env, on_diag=lambda: self.go("diag"))
            if not dlg.entries:
                message(self, "Playlist vazia", "Não foram encontrados vídeos neste link.", "warn")
                return
            if not dlg.exec():
                return
            choice, folder, sub = dlg.result_data()
            subdir = safe_folder(info.get("title")) if sub else ""
            for e in dlg.selected():
                self.m.add(e["url"], choice, e["title"], site=e["site"], duration=e["duration"],
                           uploader=e["uploader"], thumb_url=e["thumb"], subdir=subdir, outdir=self._outdir(folder))
            self.p_down.url.clear()
            return
        if direct:
            choice = formats.choice_from_settings(self.settings)
            folder = self.settings["download_dir"]
        else:
            dlg = VideoDialog(self, info, self.settings, self.env, on_diag=lambda: self.go("diag"))
            if not dlg.exec():
                return
            choice, folder = dlg.result_data()
        self.m.add(info.get("webpage_url") or url, choice, info.get("title"), site=info.get("extractor_key"),
                   duration=info.get("duration"), uploader=info.get("uploader") or info.get("channel"),
                   thumb_url=formats.best_thumbnail(info), outdir=self._outdir(folder))
        self.p_down.url.clear()

    def _outdir(self, folder):
        folder = os.path.expanduser(folder or "")
        return "" if not folder or folder == self.settings["download_dir"] else folder

    def _redownload(self, x):
        self.m.add(x.get("url"), x.get("choice") or formats.choice_from_settings(self.settings), x.get("title"),
                   site=x.get("site"), uploader=x.get("uploader"), duration=x.get("duration"),
                   thumb_url=x.get("thumb_url"))
        self.go("downloads")

    # ------------------------------------------------------------ eventos
    def _job_finished(self, job):
        self.p_hist.reload()
        if not self.settings["notify_done"] or self.isActiveWindow():
            return
        title = "Download concluído" if job.status == "done" else "Falha no download"
        body = job.title if job.status == "done" else f"{job.title}\n{job.error or ''}"
        icon = os.path.join(paths.data_dir(), "getscope.png")
        if not os.path.exists(icon):
            logo_pixmap(128).save(icon)
        try:
            subprocess.Popen(["notify-send", "-a", APP_NAME, "-i", icon, title, body], env=paths.clean_env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _engine_updated(self, v):
        self._restart_ready = v
        self._update_status()
        self.show_banner(f"✓  Motor do yt-dlp pronto: {v}. Reinicie o GetScope para usar a nova versão.",
                         "⟳  REINICIAR AGORA", self.restart)

    def restart(self):
        if [j for j in self.m.jobs if j.status in ACTIVE]:
            if not ask(self, "Reiniciar", "Há downloads em andamento.",
                       details="Eles serão pausados e continuam de onde pararam depois de reiniciar.",
                       yes="REINICIAR"):
                return
        if os.environ.get("APPIMAGE"):
            cmd = [os.environ["APPIMAGE"]]
        elif getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            cmd = [sys.executable, os.path.abspath(sys.argv[0])]
        self._shutdown()
        subprocess.Popen(cmd, env=paths.clean_env(), start_new_session=True)
        QApplication.instance().quit()

    def _app_state(self, state):
        if state != Qt.ApplicationActive or self.p_down.url.text().strip() or self._analyzing:
            return
        t = (QApplication.clipboard().text() or "").strip()
        if t and t != self._last_clip and t.startswith(("http://", "https://")) and "\n" not in t:
            self._last_clip = t
            self.p_down.url.setText(t)
            self.p_down.url.selectAll()
            self.status.setText("Link da área de transferência colado — clique em ANALISAR.")

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or (md.hasText() and looks_like_url(md.text())):
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        url = md.urls()[0].toString() if md.hasUrls() else md.text().strip()
        if url.startswith("file:"):
            return
        self.go("downloads")
        self.p_down.url.setText(url)
        self.analyze(url)

    def refresh_all(self):
        self.p_diag.refresh()
        self.p_hist.reload()
        self._update_status()
        self.status.setText(self.status.text() + "    ·    verificado agora")

    def about(self):
        AboutDialog(self, self.env).exec()

    def _shutdown(self):
        self.m.pause_all()
        self.m.pool.waitForDone(4000)
        self.m.save_queue()

    def closeEvent(self, e):
        act = [j for j in self.m.jobs if j.status in ACTIVE]
        if act and not ask(self, "Sair do GetScope",
                           f"Há {len(act)} download{'s' if len(act) > 1 else ''} em andamento.",
                           details="Eles serão pausados e você pode retomar na próxima vez que abrir o GetScope.",
                           yes="SAIR", yes_kind="danger"):
            e.ignore()
            return
        self._shutdown()
        e.accept()
        if self.m.pool.activeThreadCount():
            os._exit(0)
