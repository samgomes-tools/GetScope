"""Componentes reutilizáveis no padrão visual dos apps *Scope."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget, QLayout)

from . import theme


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def set_prop(w, name, value):
    w.setProperty(name, value)
    repolish(w)


def btn(text, kind=None, slot=None, tip=None, parent=None):
    b = QPushButton(text, parent)
    if kind:
        b.setProperty("kind", kind)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    return b


def vsep():
    f = QFrame()
    f.setObjectName("VSep")
    f.setFixedWidth(1)
    f.setFixedHeight(22)
    return f


def label(text="", obj=None, wrap=False, size=None, bold=False, color=None):
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    if wrap:
        lb.setWordWrap(True)
    css = []
    if size:
        css.append(f"font-size: {size}pt;")
    if bold:
        css.append("font-weight: 700;")
    if color:
        css.append(f"color: {color};")
    if css:
        lb.setStyleSheet(" ".join(css))
    return lb


def clear_layout(layout):
    """Remove widgets antigos sem deixá-los sobrepostos por um instante."""
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


class ScopeDialog(QDialog):
    """Diálogo com cabeçalho em gradiente, corpo com margens e rodapé à direita."""

    def __init__(self, parent, title, subtitle="", width=560):
        super().__init__(parent)
        self.setWindowTitle(title.title())
        self.setModal(True)
        self.setMinimumWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head = QWidget()
        head.setObjectName("DlgHead")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(22, 16, 22, 14)
        hl.setSpacing(2)
        t = QLabel(title.upper())
        t.setObjectName("DlgTitle")
        hl.addWidget(t)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("Muted")
        self.subtitle.setWordWrap(True)
        self.subtitle.setVisible(bool(subtitle))
        hl.addWidget(self.subtitle)
        outer.addWidget(head)
        body = QWidget()
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(22, 18, 22, 10)
        self.body.setSpacing(10)
        self.body.setSizeConstraint(QLayout.SetMinimumSize)
        outer.addWidget(body, 1)
        foot = QWidget()
        self.foot = QHBoxLayout(foot)
        self.foot.setContentsMargins(22, 10, 22, 18)
        self.foot.setSpacing(10)
        self.foot.addStretch(1)
        outer.addWidget(foot)

    def add_button(self, text, kind=None, slot=None):
        b = btn(text, kind, slot)
        b.setMinimumWidth(120)
        self.foot.addWidget(b)
        return b


_ICONS = {
    "info": ("ⓘ", theme.ACCENT, "#1d3a52"),
    "warn": ("⚠", theme.WARN, "#3a2f1c"),
    "error": ("✕", theme.ERROR, "#3a1c1c"),
    "ok": ("✓", theme.GREEN, "#1f3a20"),
}


def _icon(kind):
    ch, fg, bg = _ICONS.get(kind, _ICONS["info"])
    lb = QLabel(ch)
    lb.setFixedSize(44, 44)
    lb.setAlignment(Qt.AlignCenter)
    lb.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:22px; font-size:18pt; font-weight:800;")
    return lb


def _msg_dialog(parent, title, text, kind, details=None):
    d = ScopeDialog(parent, title, width=480)
    row = QHBoxLayout()
    row.setSpacing(16)
    row.addWidget(_icon(kind), 0, Qt.AlignTop)
    col = QVBoxLayout()
    t = QLabel(text)
    t.setWordWrap(True)
    t.setTextInteractionFlags(Qt.TextSelectableByMouse)
    col.addWidget(t)
    if details:
        dl = QLabel(details)
        dl.setObjectName("Muted")
        dl.setWordWrap(True)
        dl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(dl)
    row.addLayout(col, 1)
    d.body.addLayout(row)
    return d


def message(parent, title, text, kind="info", details=None):
    d = _msg_dialog(parent, title, text, kind, details)
    d.add_button("OK", "blue", d.accept).setDefault(True)
    d.exec()


def ask(parent, title, text, yes="CONFIRMAR", no="CANCELAR", kind="warn", yes_kind="green", details=None,
        confirm=None):
    """confirm: texto de um checkbox que precisa ser marcado (ações destrutivas)."""
    d = _msg_dialog(parent, title, text, kind, details)
    ck = None
    if confirm:
        from PySide6.QtWidgets import QCheckBox
        ck = QCheckBox(confirm)
        ck.setStyleSheet("color:#ff8a8a;")
        d.body.addWidget(ck)
    d.add_button(no, "cancel", d.reject)
    ok = d.add_button(yes, yes_kind, d.accept)
    if ck:
        ok.setEnabled(False)
        ck.toggled.connect(ok.setEnabled)
    else:
        ok.setDefault(True)
    return d.exec() == QDialog.Accepted
