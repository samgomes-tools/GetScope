"""Aba Configurações."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from scopekit.ui import ask, btn

from ..core import formats, paths
from ..core.settings import COOKIE_BROWSERS, NAME_TEMPLATES
from .dialogs import FormatOptions
from .widgets import card


def _form():
    f = QFormLayout()
    f.setHorizontalSpacing(18)
    f.setVerticalSpacing(10)
    f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    f.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    return f


def _key(t):
    lb = QLabel(t)
    lb.setObjectName("Key")
    lb.setMinimumWidth(190)
    return lb


def _hint(t):
    lb = QLabel(t)
    lb.setObjectName("Muted")
    lb.setWordWrap(True)
    lb.setStyleSheet("font-size:9pt;")
    return lb


class SettingsPage(QWidget):
    saved = Signal()

    def __init__(self, settings):
        super().__init__()
        self.s = settings
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)
        lay.setSizeConstraint(QLayout.SetMinimumSize)

        c, cl = card("Downloads")
        f = _form()
        self.ed_dir = QLineEdit()
        pick = btn("📁  Escolher…", None, self._pick)
        row = QHBoxLayout()
        row.addWidget(self.ed_dir, 1)
        row.addWidget(pick)
        f.addRow(_key("Pasta padrão"), row)
        self.sp_conc = QSpinBox()
        self.sp_conc.setRange(1, 5)
        self.sp_conc.setMaximumWidth(120)
        f.addRow(_key("Downloads ao mesmo tempo"), self.sp_conc)
        self.sp_rate = QSpinBox()
        self.sp_rate.setRange(0, 1000000)
        self.sp_rate.setSingleStep(256)
        self.sp_rate.setSuffix(" KB/s")
        self.sp_rate.setSpecialValueText("Sem limite")
        self.sp_rate.setMaximumWidth(170)
        f.addRow(_key("Limite de velocidade"), self.sp_rate)
        self.cb_name = QComboBox()
        for k, (label, _t) in NAME_TEMPLATES.items():
            self.cb_name.addItem(label, k)
        self.cb_name.setMaximumWidth(260)
        f.addRow(_key("Nome do arquivo"), self.cb_name)
        self.ck_sub = QCheckBox("Salvar playlists numa subpasta com o nome da playlist")
        f.addRow(_key(""), self.ck_sub)
        self.ck_notify = QCheckBox("Avisar quando um download terminar (notificação do sistema)")
        f.addRow(_key(""), self.ck_notify)
        cl.addLayout(f)
        lay.addWidget(c)

        c, cl = card("Formato padrão")
        cl.addWidget(_hint("Usado ao abrir a tela de opções e quando “Baixar direto com o formato padrão” está marcado."))
        self.fmt = FormatOptions(formats.choice_from_settings(settings))
        cl.addWidget(self.fmt)
        lay.addWidget(c)

        c, cl = card("Acesso")
        f = _form()
        self.cb_cookies = QComboBox()
        for k, label in COOKIE_BROWSERS:
            self.cb_cookies.addItem(label, k)
        self.cb_cookies.setMaximumWidth(260)
        f.addRow(_key("Usar cookies do navegador"), self.cb_cookies)
        cl.addLayout(f)
        cl.addWidget(_hint("Ajuda com vídeos com restrição de idade, conteúdo de membros ou quando o YouTube pede para "
                           "confirmar que você não é um robô. Os cookies são lidos direto do navegador escolhido, "
                           "na hora do download, e não são guardados pelo GetScope."))
        lay.addWidget(c)

        c, cl = card("Motor")
        self.ck_engine = QCheckBox("Procurar e instalar atualizações do motor (yt-dlp) ao abrir o GetScope")
        cl.addWidget(self.ck_engine)
        cl.addWidget(_hint(f"O motor atualizado fica em {paths.engine_dir()}."))
        lay.addWidget(c)

        foot = QHBoxLayout()
        foot.addStretch(1)
        b = btn("RESTAURAR PADRÕES", "cancel", self._reset)
        b.setMinimumWidth(170)
        foot.addWidget(b)
        b = btn("✓  SALVAR", "green", self._save)
        b.setMinimumWidth(150)
        foot.addWidget(b)
        lay.addLayout(foot)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setAlignment(Qt.AlignRight)
        lay.addWidget(self.status)
        lay.addStretch(1)
        sc.setWidget(inner)
        root.addWidget(sc, 1)
        self.load()

    def load(self):
        s = self.s
        self.ed_dir.setText(s["download_dir"])
        self.sp_conc.setValue(int(s["max_concurrent"]))
        self.sp_rate.setValue(int(s["rate_limit_kb"]))
        self.cb_name.setCurrentIndex(max(0, self.cb_name.findData(s["name_template"])))
        self.ck_sub.setChecked(bool(s["playlist_subfolder"]))
        self.ck_notify.setChecked(bool(s["notify_done"]))
        self.fmt.set_choice(formats.choice_from_settings(s))
        self.cb_cookies.setCurrentIndex(max(0, self.cb_cookies.findData(s["cookies_browser"])))
        self.ck_engine.setChecked(bool(s["check_engine_on_start"]))
        self.status.setText("")

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Pasta padrão", self.ed_dir.text() or os.path.expanduser("~"))
        if d:
            self.ed_dir.setText(d)

    def _save(self):
        vals = {
            "download_dir": os.path.expanduser(self.ed_dir.text().strip()) or paths.default_download_dir(),
            "max_concurrent": self.sp_conc.value(),
            "rate_limit_kb": self.sp_rate.value(),
            "name_template": self.cb_name.currentData(),
            "playlist_subfolder": self.ck_sub.isChecked(),
            "notify_done": self.ck_notify.isChecked(),
            "cookies_browser": self.cb_cookies.currentData(),
            "check_engine_on_start": self.ck_engine.isChecked(),
        }
        vals.update(self.fmt.choice())
        self.s.update(vals)
        self.status.setText("✓  Configurações salvas")
        self.saved.emit()

    def _reset(self):
        if ask(self, "Restaurar padrões", "Voltar todas as configurações para o padrão?", yes="RESTAURAR"):
            self.s.reset()
            self.load()
            self.status.setText("✓  Padrões restaurados")
            self.saved.emit()
