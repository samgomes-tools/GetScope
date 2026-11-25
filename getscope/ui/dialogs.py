"""Diálogos: opções de download (vídeo e playlist) e Sobre."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QRadioButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget, QAbstractItemView)

from scopekit import theme
from scopekit.ui import ScopeDialog, btn

from ..app import APP_NAME, AUTHOR, TAGLINE, VERSION
from ..core import engine, formats
from .widgets import KeyVal, Thumb, logo_pixmap


class FormatOptions(QWidget):
    """Escolha de tipo, qualidade e extras; usada nos diálogos e nas Configurações."""
    changed = Signal()

    def __init__(self, choice, has_ffmpeg=True, compact=False, parent=None):
        super().__init__(parent)
        self.has_ffmpeg = has_ffmpeg
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(18)
        self.rb_video = QRadioButton("🎬  Vídeo")
        self.rb_audio = QRadioButton("🎵  Somente áudio")
        self.group = QButtonGroup(self)
        self.group.addButton(self.rb_video)
        self.group.addButton(self.rb_audio)
        row.addWidget(self._lbl("TIPO"))
        row.addWidget(self.rb_video)
        row.addWidget(self.rb_audio)
        row.addStretch(1)
        lay.addLayout(row)

        self.video_box = QWidget()
        vl = QHBoxLayout(self.video_box)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(10)
        self.cb_quality = QComboBox()
        self.cb_quality.setMinimumWidth(250)
        self.cb_container = QComboBox()
        for c in formats.CONTAINERS:
            self.cb_container.addItem(c.upper(), c)
        vl.addWidget(self._lbl("QUALIDADE"))
        vl.addWidget(self.cb_quality, 1)
        vl.addSpacing(8)
        vl.addWidget(self._lbl("FORMATO"))
        vl.addWidget(self.cb_container)
        lay.addWidget(self.video_box)

        self.audio_box = QWidget()
        al = QHBoxLayout(self.audio_box)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(10)
        self.cb_afmt = QComboBox()
        for k, v in formats.AUDIO_FORMATS:
            self.cb_afmt.addItem(v, k)
        self.cb_aq = QComboBox()
        for k, v in formats.AUDIO_QUALITIES:
            self.cb_aq.addItem(v, k)
        al.addWidget(self._lbl("FORMATO"))
        al.addWidget(self.cb_afmt, 1)
        al.addSpacing(8)
        al.addWidget(self._lbl("QUALIDADE"))
        al.addWidget(self.cb_aq)
        lay.addWidget(self.audio_box)

        ex = QHBoxLayout()
        ex.setSpacing(18)
        self.ck_thumb = QCheckBox("Embutir capa")
        self.ck_meta = QCheckBox("Embutir metadados e capítulos")
        ex.addWidget(self.ck_thumb)
        ex.addWidget(self.ck_meta)
        ex.addStretch(1)
        lay.addLayout(ex)
        sub = QHBoxLayout()
        sub.setSpacing(10)
        self.ck_subs = QCheckBox("Baixar legendas")
        self.ed_langs = QLineEdit()
        self.ed_langs.setPlaceholderText("idiomas, ex.: pt,en")
        self.ed_langs.setMaximumWidth(180)
        self.ed_langs.setToolTip("Códigos de idioma separados por vírgula (pt, en, es…).")
        sub.addWidget(self.ck_subs)
        sub.addWidget(self.ed_langs)
        sub.addStretch(1)
        lay.addLayout(sub)

        self.set_heights(None)
        self.set_choice(choice)
        for w in (self.rb_video, self.rb_audio):
            w.toggled.connect(self._sync)
        for w in (self.cb_quality, self.cb_container, self.cb_afmt, self.cb_aq):
            w.currentIndexChanged.connect(self._sync)
        for w in (self.ck_thumb, self.ck_meta, self.ck_subs):
            w.toggled.connect(self._sync)
        self.ed_langs.textChanged.connect(lambda *_: self.changed.emit())
        if not has_ffmpeg:
            for w in (self.ck_thumb, self.ck_meta, self.cb_container):
                w.setEnabled(False)
                w.setToolTip("Requer FFmpeg (instale pela aba Diagnóstico).")
            self.cb_afmt.setEnabled(False)
            self.cb_aq.setEnabled(False)
            self.cb_afmt.setToolTip("Sem FFmpeg o áudio é salvo no formato original (M4A/WEBM).")
        self._sync()

    @staticmethod
    def _lbl(t):
        lb = QLabel(t)
        lb.setObjectName("Key")
        lb.setStyleSheet("font-size:8pt; font-weight:700; letter-spacing:1px;")
        return lb

    def set_heights(self, heights):
        """heights: lista [(altura, tamanho)] do vídeo ou None para a lista genérica."""
        cur = self.cb_quality.currentData()
        self.cb_quality.blockSignals(True)
        self.cb_quality.clear()
        if heights:
            top = heights[0][0]
            tag = formats.height_label(top)
            self.cb_quality.addItem(f"Melhor disponível ({top}p{' ' + tag if tag else ''})", "best")
            for h, size in heights:
                tag = formats.height_label(h)
                txt = f"{h}p" + (f" {tag}" if tag else "")
                if size:
                    txt += f"  ·  ~{formats.human_size(size)}"
                if not self.has_ffmpeg and h > 360:
                    txt += "  (requer FFmpeg)"
                self.cb_quality.addItem(txt, h)
        else:
            self.cb_quality.addItem("Melhor disponível", "best")
            for h in formats.HEIGHTS[1:8]:
                tag = formats.height_label(h)
                self.cb_quality.addItem(f"Até {h}p" + (f" {tag}" if tag else ""), h)
        idx = self.cb_quality.findData(cur)
        self.cb_quality.setCurrentIndex(max(0, idx))
        self.cb_quality.blockSignals(False)

    def set_choice(self, c):
        (self.rb_audio if c.get("mode") == "audio" else self.rb_video).setChecked(True)
        q = c.get("quality", "best")
        q = q if q == "best" else int(q)
        i = self.cb_quality.findData(q)
        if i < 0 and q != "best":
            # quality não existe neste vídeo: escolhe a maior que não passa dela
            for j in range(self.cb_quality.count()):
                d = self.cb_quality.itemData(j)
                if d != "best" and d <= q:
                    i = j
                    break
        self.cb_quality.setCurrentIndex(max(0, i))
        self.cb_container.setCurrentIndex(max(0, self.cb_container.findData(c.get("container", "mp4"))))
        self.cb_afmt.setCurrentIndex(max(0, self.cb_afmt.findData(c.get("audio_format", "mp3"))))
        self.cb_aq.setCurrentIndex(max(0, self.cb_aq.findData(str(c.get("audio_quality", "192")))))
        self.ck_thumb.setChecked(bool(c.get("embed_thumbnail", True)))
        self.ck_meta.setChecked(bool(c.get("embed_metadata", True)))
        self.ck_subs.setChecked(bool(c.get("subtitles", False)))
        self.ed_langs.setText(c.get("subtitle_langs", "pt,en"))

    def choice(self):
        return {
            "mode": "audio" if self.rb_audio.isChecked() else "video",
            "quality": self.cb_quality.currentData(),
            "container": self.cb_container.currentData(),
            "audio_format": self.cb_afmt.currentData(),
            "audio_quality": self.cb_aq.currentData(),
            "embed_thumbnail": self.ck_thumb.isChecked(),
            "embed_metadata": self.ck_meta.isChecked(),
            "subtitles": self.ck_subs.isChecked(),
            "subtitle_langs": self.ed_langs.text().strip() or "pt,en",
        }

    def _sync(self, *_):
        audio = self.rb_audio.isChecked()
        self.video_box.setVisible(not audio)
        self.audio_box.setVisible(audio)
        lossless = self.cb_afmt.currentData() in ("flac", "wav")
        self.cb_aq.setEnabled(self.has_ffmpeg and not lossless)
        self.ed_langs.setEnabled(self.ck_subs.isChecked())
        self.changed.emit()


def _folder_row(dialog, path):
    row = QHBoxLayout()
    row.setSpacing(8)
    lb = QLabel("SALVAR EM")
    lb.setObjectName("Key")
    lb.setStyleSheet("font-size:8pt; font-weight:700; letter-spacing:1px;")
    ed = QLineEdit(path)

    def pick():
        d = QFileDialog.getExistingDirectory(dialog, "Escolher pasta", ed.text() or os.path.expanduser("~"))
        if d:
            ed.setText(d)
    row.addWidget(lb)
    row.addWidget(ed, 1)
    row.addWidget(btn("📁  Escolher…", None, pick))
    return row, ed


def _ffmpeg_note(parent_layout, on_diag):
    w = QWidget()
    w.setObjectName("Banner")
    w.setAttribute(Qt.WA_StyledBackground, True)
    l = QHBoxLayout(w)
    l.setContentsMargins(12, 8, 8, 8)
    t = QLabel("⚠  FFmpeg não encontrado: o vídeo fica limitado ao arquivo único (geralmente 360p) "
               "e o áudio não pode ser convertido.")
    t.setObjectName("BannerText")
    t.setWordWrap(True)
    l.addWidget(t, 1)
    if on_diag:
        l.addWidget(btn("INSTALAR", "green", on_diag))
    parent_layout.addWidget(w)


class VideoDialog(ScopeDialog):
    """Prévia de um vídeo e escolha do formato."""

    def __init__(self, parent, info, settings, env, on_diag=None):
        super().__init__(parent, "Baixar vídeo", info.get("extractor_key") or "", width=720)
        self.info = info
        has_ff = bool(env.ffmpeg)
        top = QHBoxLayout()
        top.setSpacing(18)
        th = Thumb(320, 180)
        th.load(formats.best_thumbnail(info))
        top.addWidget(th, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(6)
        t = QLabel(info.get("title") or "Sem título")
        t.setObjectName("Title")
        t.setWordWrap(True)
        t.setStyleSheet("font-size:14pt; font-weight:300;")
        col.addWidget(t)
        kv = KeyVal()
        kv.set("Canal", info.get("uploader") or info.get("channel") or info.get("uploader_id"))
        kv.set("Duração", formats.human_time(info.get("duration")) if info.get("duration") else None)
        kv.set("Site", info.get("extractor_key") or info.get("extractor"))
        if info.get("view_count"):
            kv.set("Visualizações", f"{info['view_count']:,}".replace(",", "."))
        if info.get("upload_date"):
            d = info["upload_date"]
            kv.set("Publicado", f"{d[6:8]}/{d[4:6]}/{d[0:4]}")
        if info.get("is_live"):
            kv.set("Ao vivo", "Sim — será gravado desde o início disponível", theme.WARN)
        col.addWidget(kv)
        col.addStretch(1)
        top.addLayout(col, 1)
        self.body.addLayout(top)
        if not has_ff:
            _ffmpeg_note(self.body, (lambda: (self.reject(), on_diag())) if on_diag else None)
        self.opts = FormatOptions(formats.choice_from_settings(settings), has_ff)
        heights = formats.video_heights(info)
        self.opts.set_heights(heights or None)
        self.opts.set_choice(formats.choice_from_settings(settings))
        no_video = not heights and all(f.get("vcodec") == "none" for f in info.get("formats") or [{}]) \
            and info.get("formats")
        if no_video:
            self.opts.rb_audio.setChecked(True)
            self.opts.rb_video.setEnabled(False)
        self.body.addWidget(self.opts)
        row, self.ed_folder = _folder_row(self, settings["download_dir"])
        self.body.addLayout(row)
        self.add_button("CANCELAR", "cancel", self.reject)
        self.ok = self.add_button("⬇  BAIXAR", "green", self.accept)
        self.ok.setDefault(True)

    def result_data(self):
        return self.opts.choice(), self.ed_folder.text().strip()


def playlist_entries(info):
    out = []
    for i, e in enumerate(info.get("entries") or [], 1):
        if not e:
            continue
        url = e.get("webpage_url") or e.get("url")
        if not url:
            continue
        if not url.startswith(("http://", "https://")) and e.get("ie_key") == "Youtube":
            url = "https://www.youtube.com/watch?v=" + url
        out.append({"n": e.get("playlist_index") or i, "url": url, "title": e.get("title") or url,
                    "duration": e.get("duration"), "uploader": e.get("uploader") or e.get("channel"),
                    "site": e.get("ie_key") or info.get("extractor_key"),
                    "thumb": formats.best_thumbnail(e) if e.get("thumbnails") else e.get("thumbnail")})
    return out


class PlaylistDialog(ScopeDialog):
    def __init__(self, parent, info, settings, env, on_diag=None):
        self.entries = playlist_entries(info)
        n = len(self.entries)
        title = info.get("title") or "Playlist"
        sub = f"{title}  ·  {n} {'item' if n == 1 else 'itens'}"
        if info.get("uploader") or info.get("channel"):
            sub += f"  ·  {info.get('uploader') or info.get('channel')}"
        super().__init__(parent, "Baixar playlist", sub, width=760)
        self.info = info
        has_ff = bool(env.ffmpeg)
        tools = QHBoxLayout()
        tools.addWidget(btn("☑  Marcar todos", "tool", lambda: self._mark(True)))
        tools.addWidget(btn("☐  Desmarcar todos", "tool", lambda: self._mark(False)))
        tools.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        tools.addWidget(self.count)
        self.body.addLayout(tools)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["#", "TÍTULO", "DURAÇÃO"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.tree.setMinimumHeight(240)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for e in self.entries:
            it = QTreeWidgetItem([str(e["n"]), e["title"], formats.human_time(e["duration"])
                                  if e["duration"] else "—"])
            it.setCheckState(0, Qt.Checked)
            it.setData(0, Qt.UserRole, e)
            self.tree.addTopLevelItem(it)
        self.tree.itemChanged.connect(lambda *_: self._update_count())
        self.body.addWidget(self.tree, 1)
        if not has_ff:
            _ffmpeg_note(self.body, (lambda: (self.reject(), on_diag())) if on_diag else None)
        self.opts = FormatOptions(formats.choice_from_settings(settings), has_ff)
        self.body.addWidget(self.opts)
        self.ck_sub = QCheckBox("Salvar numa subpasta com o nome da playlist")
        self.ck_sub.setChecked(bool(settings["playlist_subfolder"]))
        self.body.addWidget(self.ck_sub)
        row, self.ed_folder = _folder_row(self, settings["download_dir"])
        self.body.addLayout(row)
        self.add_button("CANCELAR", "cancel", self.reject)
        self.ok = self.add_button("⬇  BAIXAR", "green", self.accept)
        self.ok.setDefault(True)
        self.resize(780, 720)
        self._update_count()

    def _mark(self, on):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self.tree.blockSignals(False)
        self._update_count()

    def selected(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                out.append(it.data(0, Qt.UserRole))
        return out

    def _update_count(self):
        n = len(self.selected())
        self.count.setText(f"{n} de {len(self.entries)} selecionados")
        self.ok.setText(f"⬇  BAIXAR {n} {'ITEM' if n == 1 else 'ITENS'}")
        self.ok.setEnabled(n > 0)

    def result_data(self):
        return self.opts.choice(), self.ed_folder.text().strip(), self.ck_sub.isChecked()


class AboutDialog(ScopeDialog):
    def __init__(self, parent, env):
        super().__init__(parent, "Sobre", width=520)
        row = QHBoxLayout()
        row.setSpacing(18)
        lg = QLabel()
        lg.setPixmap(logo_pixmap(96))
        row.addWidget(lg, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        name = QLabel(APP_NAME.upper())
        name.setObjectName("AppName")
        name.setStyleSheet("font-size:20pt;")
        col.addWidget(name)
        v = QLabel(f"Versão {VERSION}")
        v.setObjectName("Muted")
        col.addWidget(v)
        tg = QLabel(TAGLINE + ".")
        tg.setWordWrap(True)
        col.addWidget(tg)
        col.addSpacing(6)
        by = QLabel(f"Desenvolvido por <b style='color:#ffffff'>{AUTHOR}</b>")
        col.addWidget(by)
        row.addLayout(col, 1)
        self.body.addLayout(row)
        sec = QLabel("COMPONENTES")
        sec.setObjectName("Section")
        self.body.addWidget(sec)
        kv = KeyVal()
        ei = engine.info()
        kv.set("yt-dlp", f"{ei['version']} ({'atualizado' if ei['source'] == 'updated' else 'embutido'}) — Unlicense")
        ff = env.ffmpeg
        kv.set("FFmpeg", f"{ff['version']} (do sistema)" if ff else "não encontrado")
        js = env.js[0] if env.js else None
        kv.set("JavaScript", f"{js['name'].capitalize()} {js['version']}" if js else "não encontrado")
        try:
            import PySide6
            kv.set("Interface", f"Qt / PySide6 {PySide6.__version__} — LGPL")
        except ImportError:
            pass
        self.body.addWidget(kv)
        note = QLabel("Baixe apenas conteúdo que você tem direito de baixar: seus próprios vídeos, "
                      "conteúdo livre ou para uso pessoal permitido. Os termos de cada site continuam valendo.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self.body.addWidget(note)
        self.add_button("FECHAR", "blue", self.accept).setDefault(True)
