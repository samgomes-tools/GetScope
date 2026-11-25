"""Widgets de apoio: logo, miniaturas, linhas chave/valor e cartões."""
from PySide6.QtCore import QPointF, QRectF, Qt, QThreadPool
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap, QPolygonF, QIcon
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from scopekit import theme

from ..core.jobs import FetchWorker

_THUMBS = {}


def paint_logo(p, size):
    """Logo do GetScope: quadrado arredondado azul com seta de download sobre uma 'tela'."""
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor("#47bfff"))
    g.setColorAt(1, QColor("#1a44c2"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(s * 0.04, s * 0.04, s * 0.92, s * 0.92), s * 0.2, s * 0.2)
    p.fillPath(path, g)
    # tela
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 60))
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.2, s * 0.64, s * 0.42), s * 0.06, s * 0.06)
    # play
    p.setBrush(QColor("#ffffff"))
    p.drawPolygon(QPolygonF([QPointF(s * 0.45, s * 0.29), QPointF(s * 0.45, s * 0.53), QPointF(s * 0.6, s * 0.41)]))
    # seta de download
    p.setBrush(QColor("#a4d007"))
    p.drawRect(QRectF(s * 0.45, s * 0.6, s * 0.1, s * 0.12))
    p.drawPolygon(QPolygonF([QPointF(s * 0.34, s * 0.7), QPointF(s * 0.66, s * 0.7), QPointF(s * 0.5, s * 0.84)]))


def logo_pixmap(size):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    paint_logo(p, size)
    p.end()
    return pm


def app_icon():
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(logo_pixmap(s))
    return ic


def placeholder_thumb(w, h, text="▶"):
    pm = QPixmap(w, h)
    pm.fill(QColor("#0f1620"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#22374d"))
    g.setColorAt(1, QColor("#121b26"))
    p.fillRect(0, 0, w, h, g)
    p.setPen(QColor("#4b6477"))
    f = p.font()
    f.setPointSizeF(max(10, h / 5))
    p.setFont(f)
    p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, text)
    p.end()
    return pm


def cover(pm, w, h):
    """Redimensiona preenchendo (corta as bordas), como object-fit: cover."""
    sc = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (sc.width() - w) // 2
    y = (sc.height() - h) // 2
    return sc.copy(x, y, w, h)


class Thumb(QLabel):
    """Miniatura carregada em segundo plano, com cache."""

    def __init__(self, w, h, parent=None):
        super().__init__(parent)
        self.w, self.h = w, h
        self.setFixedSize(w, h)
        self.setStyleSheet("background:#0f1620; border:1px solid #0e141b;")
        self._url = None
        self.setPixmap(placeholder_thumb(w, h))

    def load(self, url, fallback="▶"):
        self._url = url
        if not url:
            self.setPixmap(placeholder_thumb(self.w, self.h, fallback))
            return
        if url in _THUMBS:
            self._apply(url, _THUMBS[url])
            return
        self.setPixmap(placeholder_thumb(self.w, self.h, "…"))
        wk = FetchWorker(url)
        wk.sig.done.connect(self._fetched)
        QThreadPool.globalInstance().start(wk)

    def _fetched(self, url, data):
        pm = QPixmap()
        if data and pm.loadFromData(data):
            _THUMBS[url] = pm
        else:
            _THUMBS[url] = None
        if url == self._url:
            self._apply(url, _THUMBS[url])

    def _apply(self, url, pm):
        if pm is None or pm.isNull():
            self.setPixmap(placeholder_thumb(self.w, self.h))
        else:
            self.setPixmap(cover(pm, self.w, self.h))


class KeyVal(QWidget):
    """Grade de pares chave (cinza) / valor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(6)
        self.grid.setColumnStretch(1, 1)
        self.rows = {}

    def set(self, key, value, color=None):
        if key not in self.rows:
            k = QLabel(key)
            k.setObjectName("Key")
            v = QLabel()
            v.setObjectName("Val")
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            r = len(self.rows)
            self.grid.addWidget(k, r, 0, Qt.AlignTop)
            self.grid.addWidget(v, r, 1)
            self.rows[key] = (k, v)
        k, v = self.rows[key]
        v.setText(str(value) if value not in (None, "") else "—")
        v.setStyleSheet(f"color:{color};" if color else "")
        k.setVisible(True)
        v.setVisible(True)

    def hide_row(self, key):
        if key in self.rows:
            for w in self.rows[key]:
                w.setVisible(False)


def card(title=None):
    """Cartão com fundo de painel e título opcional em azul."""
    w = QWidget()
    w.setObjectName("Card")
    w.setAttribute(Qt.WA_StyledBackground, True)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(18, 14, 18, 16)
    lay.setSpacing(10)
    if title:
        t = QLabel(title.upper())
        t.setObjectName("Section")
        lay.addWidget(t)
    return w, lay


def status_dot(state):
    colors = {"ok": theme.GREEN, "warn": theme.WARN, "error": theme.ERROR, "info": theme.ACCENT}
    ch = {"ok": "✓", "warn": "!", "error": "✕", "info": "ⓘ"}[state]
    bg = {"ok": "#1f3a20", "warn": "#3a2f1c", "error": "#3a1c1c", "info": "#1d3a52"}[state]
    lb = QLabel(ch)
    lb.setFixedSize(40, 40)
    lb.setAlignment(Qt.AlignCenter)
    lb.setStyleSheet(f"background:{bg}; color:{colors[state]}; border-radius:20px; font-size:15pt; font-weight:800;")
    return lb


def hbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    lay = QHBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for it in items:
        if it is None:
            lay.addStretch(1)
        elif isinstance(it, int):
            lay.addSpacing(it)
        elif isinstance(it, QWidget):
            lay.addWidget(it)
        else:
            lay.addLayout(it)
    return lay
