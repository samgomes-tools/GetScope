"""Aba Downloads: campo do link, fila e painel de detalhes."""
import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMenu, QProgressBar, QSplitter, QStackedWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget, QScrollArea, QLayout)

from scopekit import theme
from scopekit.ui import btn, set_prop, vsep

from ..core import formats
from ..core.jobs import ACTIVE
from .widgets import KeyVal, Thumb

COLS = ["TÍTULO", "SITE", "FORMATO", "TAMANHO", "PROGRESSO", "VELOCIDADE", "RESTANTE", "STATUS"]
STATUS_COLOR = {"done": theme.GREEN, "error": theme.ERROR, "paused": theme.MUTED, "canceled": "#6e7a86",
                "queued": theme.MUTED, "processing": theme.WARN}


def speed_text(v):
    return f"{formats.human_size(v)}/s" if v else "—"


def open_path(path):
    if path:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def looks_like_url(t):
    t = (t or "").strip()
    return t.startswith(("http://", "https://")) or ("." in t and " " not in t and len(t) > 4
                                                     and not t.startswith("/"))


class ProgressCell(QWidget):
    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(8)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.lbl = QLabel("0%")
        self.lbl.setFixedWidth(44)
        self.lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl.setObjectName("Muted")
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.lbl)

    def set(self, pct, state):
        self.bar.setValue(int(pct * 10))
        self.lbl.setText(f"{pct:.0f}%")
        st = {"done": "done", "error": "error", "paused": "paused", "canceled": "paused"}.get(state, "")
        if self.bar.property("state") != st:
            set_prop(self.bar, "state", st)


class DownloadsPage(QWidget):
    analyze_requested = Signal(str)
    go_settings = Signal()

    def __init__(self, manager, settings):
        super().__init__()
        self.m = manager
        self.settings = settings
        self.items = {}
        self.cells = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- campo do link
        top = QWidget()
        top.setObjectName("Toolbar")
        top.setAttribute(Qt.WA_StyledBackground, True)
        tl = QVBoxLayout(top)
        tl.setContentsMargins(18, 16, 18, 12)
        tl.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.url = QLineEdit()
        self.url.setObjectName("BigUrl")
        self.url.setPlaceholderText("Cole aqui o link do vídeo, playlist ou canal…")
        self.url.setClearButtonEnabled(True)
        self.url.returnPressed.connect(self._analyze)
        row.addWidget(self.url, 1)
        self.b_paste = btn("📋  COLAR", None, self._paste, "Colar da área de transferência")
        self.b_paste.setMinimumHeight(40)
        row.addWidget(self.b_paste)
        self.b_go = btn("ANALISAR", "blue", self._analyze)
        self.b_go.setMinimumHeight(40)
        self.b_go.setMinimumWidth(150)
        row.addWidget(self.b_go)
        tl.addLayout(row)
        sub = QHBoxLayout()
        hint = QLabel("YouTube, Instagram, TikTok, X, Facebook, Vimeo, Twitch, SoundCloud e mais de 1.000 sites.")
        hint.setObjectName("Muted")
        sub.addWidget(hint, 1)
        self.ck_direct = QCheckBox("Baixar direto com o formato padrão")
        self.ck_direct.setToolTip("Pula a tela de opções e usa o formato definido em Configurações.")
        self.ck_direct.setChecked(settings["paste_action"] == "direct")
        self.ck_direct.toggled.connect(lambda v: settings.update({"paste_action": "direct" if v else "ask"}))
        sub.addWidget(self.ck_direct)
        tl.addLayout(sub)
        root.addWidget(top)

        # ---- barra de ferramentas
        tb = QWidget()
        tb.setObjectName("Toolbar")
        tb.setAttribute(Qt.WA_StyledBackground, True)
        tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(12, 4, 12, 4)
        tbl.setSpacing(4)
        tbl.addWidget(btn("⏸  Pausar tudo", "tool", self.m.pause_all))
        tbl.addWidget(btn("▶  Retomar tudo", "tool", self.m.resume_all))
        tbl.addWidget(vsep())
        tbl.addWidget(btn("✓  Limpar concluídos", "tool", self.m.clear_finished))
        tbl.addWidget(vsep())
        tbl.addWidget(btn("📁  Abrir pasta de downloads", "tool",
                          lambda: (os.makedirs(settings["download_dir"], exist_ok=True),
                                   open_path(settings["download_dir"]))))
        tbl.addStretch(1)
        self.summary = QLabel()
        self.summary.setObjectName("Muted")
        tbl.addWidget(self.summary)
        root.addWidget(tb)

        # ---- lista + painel lateral
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(1)
        self.stack = QStackedWidget()
        self.empty = self._empty_state()
        self.stack.addWidget(self.empty)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(COLS)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemSelectionChanged.connect(self._sel_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self._primary())
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, w in enumerate([0, 90, 110, 85, 170, 95, 80, 160]):
            if i:
                h.setSectionResizeMode(i, QHeaderView.Interactive)
                self.tree.setColumnWidth(i, w)
        self.stack.addWidget(self.tree)
        split.addWidget(self.stack)
        self.side = self._side_panel()
        split.addWidget(self.side)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([900, 400])
        root.addWidget(split, 1)

        QShortcut(QKeySequence.Delete, self.tree, activated=self._remove_selected)
        self.m.job_added.connect(self._on_added)
        self.m.job_changed.connect(self._on_changed)
        self.m.job_removed.connect(self._on_removed)
        self._refresh_side()
        self._update_summary()

    # ------------------------------------------------------------ montagem
    def _empty_state(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addStretch(1)
        ic = QLabel("⬇")
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet("font-size:44pt; color:#2a3f5a;")
        l.addWidget(ic)
        t = QLabel("Nenhum download por enquanto")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:15pt; color:#dcdedf; font-weight:300;")
        l.addWidget(t)
        s = QLabel("Copie o link de um vídeo e clique em COLAR, ou arraste o link para esta janela.")
        s.setObjectName("Muted")
        s.setAlignment(Qt.AlignCenter)
        l.addWidget(s)
        l.addStretch(2)
        return w

    def _side_panel(self):
        side = QWidget()
        side.setObjectName("Side")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setMinimumWidth(330)
        side.setMaximumWidth(440)
        outer = QVBoxLayout(side)
        outer.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        lay.setSizeConstraint(QLayout.SetMinimumSize)
        self.s_thumb = Thumb(360, 202)
        lay.addWidget(self.s_thumb, 0, Qt.AlignHCenter)
        self.s_title = QLabel()
        self.s_title.setWordWrap(True)
        self.s_title.setStyleSheet("font-size:15pt; color:#ffffff; font-weight:300;")
        self.s_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.s_title)
        self.s_sub = QLabel()
        self.s_sub.setObjectName("Muted")
        self.s_sub.setWordWrap(True)
        lay.addWidget(self.s_sub)
        self.s_bar = QProgressBar()
        self.s_bar.setRange(0, 1000)
        self.s_bar.setTextVisible(False)
        lay.addWidget(self.s_bar)
        self.s_main = btn("", "green", self._primary)
        self.s_main.setProperty("kind", "green")
        self.s_main.setMinimumHeight(46)
        self.s_main.setStyleSheet("font-size:11.5pt; font-weight:800; letter-spacing:1px;")
        lay.addWidget(self.s_main)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.s_btns = {}
        acts = [("cancel", "✕  Cancelar", self._cancel_selected), ("remove", "🗑  Remover", self._remove_selected),
                ("folder", "📁  Abrir pasta", self._open_folder), ("copy", "🔗  Copiar link", self._copy_link),
                ("web", "🌐  Abrir página", self._open_web), ("again", "↻  Baixar de novo", self._again)]
        for i, (k, t, fn) in enumerate(acts):
            b = btn(t, None, fn)
            b.setMinimumHeight(34)
            self.s_btns[k] = b
            grid.addWidget(b, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        self.s_err = QLabel()
        self.s_err.setWordWrap(True)
        self.s_err.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.s_err.setStyleSheet(f"background:#3a1c1c; color:{theme.ERROR}; padding:10px; border-radius:3px;")
        lay.addWidget(self.s_err)
        sec = QLabel("DETALHES")
        sec.setObjectName("Section")
        lay.addWidget(sec)
        self.s_kv = KeyVal()
        lay.addWidget(self.s_kv)
        lay.addStretch(1)
        self.s_none = QLabel("Selecione um download na lista para ver os detalhes.")
        self.s_none.setObjectName("Muted")
        self.s_none.setWordWrap(True)
        self.s_none.setAlignment(Qt.AlignCenter)
        self.s_content = inner
        self.s_scroll = sc
        sc.setWidget(inner)
        outer.addWidget(sc)
        outer.addWidget(self.s_none, 1)
        return side

    # ------------------------------------------------------------ link
    def _paste(self):
        t = QApplication.clipboard().text().strip()
        if t:
            self.url.setText(t)
            self._analyze()

    def _analyze(self):
        t = self.url.text().strip()
        if not t:
            self.url.setFocus()
            return
        if not t.startswith(("http://", "https://")):
            t = "https://" + t
            self.url.setText(t)
        self.analyze_requested.emit(t)

    def set_busy(self, busy):
        self.b_go.setEnabled(not busy)
        self.b_paste.setEnabled(not busy)
        self.url.setReadOnly(busy)
        self.b_go.setText("ANALISANDO…" if busy else "ANALISAR")

    # ------------------------------------------------------------ lista
    def _on_added(self, job):
        it = QTreeWidgetItem([job.title] + [""] * (len(COLS) - 1))
        it.setData(0, Qt.UserRole, job.id)
        self.tree.addTopLevelItem(it)
        cell = ProgressCell()
        self.tree.setItemWidget(it, 4, cell)
        self.items[job.id] = it
        self.cells[job.id] = cell
        self.stack.setCurrentWidget(self.tree)
        self._fill(job)
        if self.tree.topLevelItemCount() == 1 or not self.tree.selectedItems():
            self.tree.setCurrentItem(it)
        self._update_summary()

    def _fill(self, job):
        it = self.items.get(job.id)
        if not it:
            return
        it.setText(0, job.title)
        it.setToolTip(0, job.title)
        it.setText(1, job.site or "—")
        it.setText(2, formats.describe(job.choice))
        size = job.total or (job.downloaded if job.status == "done" else None)
        it.setText(3, formats.human_size(size) if size else "—")
        active = job.status in ACTIVE
        it.setText(5, speed_text(job.speed) if active else "—")
        it.setText(6, formats.human_time(job.eta) if active and job.eta is not None else "—")
        it.setText(7, job.status_text)
        it.setForeground(7, _qcolor("#ffffff" if job.status == "downloading" else STATUS_COLOR.get(job.status, theme.TEXT)))
        if job.status == "error":
            it.setToolTip(7, job.error or "")
        self.cells[job.id].set(job.progress, job.status)

    def _on_changed(self, jid):
        job = self.m.by_id.get(jid)
        if job:
            self._fill(job)
            if self._current() is job:
                self._refresh_side()
        self._update_summary()

    def _on_removed(self, jid):
        it = self.items.pop(jid, None)
        self.cells.pop(jid, None)
        if it:
            idx = self.tree.indexOfTopLevelItem(it)
            self.tree.takeTopLevelItem(idx)
        if not self.items:
            self.stack.setCurrentWidget(self.empty)
        self._refresh_side()
        self._update_summary()

    def _update_summary(self):
        jobs = self.m.jobs
        act = [j for j in jobs if j.status in ACTIVE]
        q = sum(1 for j in jobs if j.status == "queued")
        done = sum(1 for j in jobs if j.status == "done")
        sp = sum(j.speed or 0 for j in act)
        parts = []
        if act:
            parts.append(f"{len(act)} baixando")
        if q:
            parts.append(f"{q} na fila")
        if done:
            parts.append(f"{done} concluído{'s' if done > 1 else ''}")
        if sp:
            parts.append(speed_text(sp))
        self.summary.setText("  ·  ".join(parts))

    def _selected_jobs(self):
        out = []
        for it in self.tree.selectedItems():
            j = self.m.by_id.get(it.data(0, Qt.UserRole))
            if j:
                out.append(j)
        return out

    def _current(self):
        js = self._selected_jobs()
        return js[0] if js else None

    def _sel_changed(self):
        self._refresh_side()

    # ------------------------------------------------------------ painel lateral
    def _refresh_side(self):
        j = self._current()
        self.s_scroll.setVisible(j is not None)
        self.s_none.setVisible(j is None)
        if not j:
            return
        if getattr(self, "_side_job", None) != (j.id, j.thumb_url):
            self.s_thumb.load(j.thumb_url)
            self._side_job = (j.id, j.thumb_url)
        self.s_title.setText(j.title)
        sub = [x for x in (j.uploader, formats.human_time(j.duration) if j.duration else None, j.site) if x]
        self.s_sub.setText("  ·  ".join(sub))
        self.s_bar.setValue(int(j.progress * 10))
        st = {"done": "done", "error": "error", "paused": "paused", "canceled": "paused"}.get(j.status, "")
        if self.s_bar.property("state") != st:
            set_prop(self.s_bar, "state", st)
        text, kind = {
            "done": ("▶  ABRIR ARQUIVO", "green"), "paused": ("▶  RETOMAR", "green"),
            "error": ("↻  TENTAR NOVAMENTE", "green"), "canceled": ("↻  BAIXAR NOVAMENTE", "green"),
        }.get(j.status, ("⏸  PAUSAR", "blue"))
        self.s_main.setText(text)
        if self.s_main.property("kind") != kind:
            set_prop(self.s_main, "kind", kind)
        self.s_main.setEnabled(not j.stop)
        self.s_btns["cancel"].setEnabled(j.status not in ("done", "canceled") and j.stop != "cancel")
        self.s_btns["folder"].setEnabled(True)
        self.s_btns["again"].setEnabled(j.status in ("done", "canceled", "error"))
        if j.status == "error" and j.error:
            self.s_err.setText(f"<b>{j.error}</b>" + (f"<br><span style='color:#c7d5e0'>{j.error_hint}</span>"
                                                      if j.error_hint else ""))
            self.s_err.show()
        else:
            self.s_err.hide()
        kv = self.s_kv
        kv.set("Status", j.status_text, STATUS_COLOR.get(j.status))
        kv.set("Formato", formats.describe(j.choice))
        if j.total:
            kv.set("Tamanho", formats.human_size(j.total))
        else:
            kv.set("Tamanho", None)
        if j.status in ACTIVE:
            kv.set("Baixado", f"{formats.human_size(j.downloaded)}  ({j.progress:.1f}%)" if j.downloaded else None)
            kv.set("Velocidade", speed_text(j.speed))
            kv.set("Restante", formats.human_time(j.eta) if j.eta is not None else None)
        else:
            for k in ("Baixado", "Velocidade", "Restante"):
                kv.hide_row(k)
        kv.set("Pasta", self._folder_of(j))
        if j.filepath:
            kv.set("Arquivo", os.path.basename(j.filepath))
        else:
            kv.hide_row("Arquivo")
        kv.set("Link", j.url)

    def _folder_of(self, j):
        if j.filepath:
            return os.path.dirname(j.filepath)
        d = j.outdir or self.settings["download_dir"]
        return os.path.join(d, j.subdir) if j.subdir else d

    # ------------------------------------------------------------ ações
    def _primary(self):
        j = self._current()
        if not j:
            return
        if j.status == "done":
            if j.filepath and os.path.exists(j.filepath):
                open_path(j.filepath)
            else:
                open_path(self._folder_of(j))
        elif j.status in ("paused", "error", "canceled"):
            self.m.resume(j.id)
        else:
            self.m.pause(j.id)

    def _cancel_selected(self):
        for j in self._selected_jobs():
            self.m.cancel(j.id)

    def _remove_selected(self):
        for j in self._selected_jobs():
            self.m.remove(j.id)

    def _open_folder(self):
        j = self._current()
        if j:
            d = self._folder_of(j)
            os.makedirs(d, exist_ok=True)
            open_path(d)

    def _copy_link(self):
        js = self._selected_jobs()
        if js:
            QApplication.clipboard().setText("\n".join(j.url for j in js))

    def _open_web(self):
        j = self._current()
        if j:
            QDesktopServices.openUrl(QUrl(j.url))

    def _again(self):
        for j in self._selected_jobs():
            if j.status in ("done", "canceled", "error"):
                self.m.add(j.url, j.choice, j.title, site=j.site, uploader=j.uploader, duration=j.duration,
                           thumb_url=j.thumb_url, subdir=j.subdir, outdir=j.outdir)

    def _menu(self, pos):
        j = self._current()
        if not j:
            return
        m = QMenu(self)
        if j.status in ACTIVE or j.status == "queued":
            m.addAction("⏸  Pausar", lambda: [self.m.pause(x.id) for x in self._selected_jobs()])
        if j.status in ("paused", "error", "canceled"):
            m.addAction("▶  Retomar", lambda: [self.m.resume(x.id) for x in self._selected_jobs()])
        if j.status == "done":
            m.addAction("▶  Abrir arquivo", self._primary)
        m.addAction("📁  Abrir pasta", self._open_folder)
        m.addSeparator()
        m.addAction("🔗  Copiar link", self._copy_link)
        m.addAction("🌐  Abrir página", self._open_web)
        m.addSeparator()
        if j.status not in ("done", "canceled"):
            m.addAction("✕  Cancelar", self._cancel_selected)
        m.addAction("🗑  Remover da lista", self._remove_selected)
        m.exec(self.tree.viewport().mapToGlobal(pos))


def _qcolor(c):
    from PySide6.QtGui import QColor
    return QColor(c)
