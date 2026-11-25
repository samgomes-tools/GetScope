"""Aba Histórico: downloads concluídos."""
import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
                               QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from scopekit import theme
from scopekit.ui import ask, btn, vsep

from ..core import formats
from .page_downloads import open_path


class HistoryPage(QWidget):
    redownload = Signal(dict)

    def __init__(self, history):
        super().__init__()
        self.h = history
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        tb = QWidget()
        tb.setObjectName("Toolbar")
        tb.setAttribute(Qt.WA_StyledBackground, True)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Buscar no histórico…")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(320)
        self.search.textChanged.connect(self.reload)
        tl.addWidget(self.search)
        tl.addSpacing(8)
        self.b_open = btn("▶  Abrir arquivo", "tool", self._open)
        self.b_folder = btn("📁  Abrir pasta", "tool", self._folder)
        self.b_again = btn("↻  Baixar de novo", "tool", self._again)
        self.b_rm = btn("✕  Remover do histórico", "tool", self._remove)
        for b in (self.b_open, self.b_folder, self.b_again):
            tl.addWidget(b)
        tl.addWidget(vsep())
        tl.addWidget(self.b_rm)
        tl.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        tl.addWidget(self.count)
        tl.addSpacing(10)
        tl.addWidget(btn("LIMPAR HISTÓRICO", "danger", self._clear))
        root.addWidget(tb)

        self.stack = QStackedWidget()
        empty = QLabel("Os downloads concluídos aparecem aqui.")
        empty.setAlignment(Qt.AlignCenter)
        empty.setObjectName("Muted")
        empty.setStyleSheet("font-size:12pt;")
        self.empty = empty
        self.stack.addWidget(empty)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["DATA", "TÍTULO", "SITE", "FORMATO", "TAMANHO", "ARQUIVO"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemDoubleClicked.connect(lambda *_: self._open())
        self.tree.itemSelectionChanged.connect(self._sync)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        hd = self.tree.header()
        hd.setStretchLastSection(False)
        hd.setSectionResizeMode(1, QHeaderView.Stretch)
        for i, w in ((0, 130), (2, 100), (3, 120), (4, 90), (5, 260)):
            self.tree.setColumnWidth(i, w)
        self.stack.addWidget(self.tree)
        root.addWidget(self.stack, 1)
        self.reload()

    def reload(self, *_):
        q = self.search.text().strip().lower()
        self.tree.clear()
        n = 0
        for x in self.h.items:
            if q and q not in (x.get("title", "") + " " + x.get("site", "") + " " + (x.get("uploader") or "")).lower():
                continue
            path = x.get("filepath") or ""
            exists = bool(path) and os.path.exists(path)
            it = QTreeWidgetItem([
                time.strftime("%d/%m/%Y %H:%M", time.localtime(x.get("date") or 0)),
                x.get("title") or x.get("url"), x.get("site") or "—", x.get("format") or "—",
                formats.human_size(x.get("size")), os.path.basename(path) if exists else "(arquivo não encontrado)"])
            it.setData(0, Qt.UserRole, x)
            it.setToolTip(1, x.get("title") or "")
            it.setToolTip(5, path)
            if not exists:
                for c in range(6):
                    it.setForeground(c, QColor("#6e7a86"))
            self.tree.addTopLevelItem(it)
            n += 1
        total = len(self.h.items)
        self.count.setText(f"{n} de {total}" if q else f"{total} {'item' if total == 1 else 'itens'}")
        self.stack.setCurrentWidget(self.tree if total else self.empty)
        self._sync()

    def _sel(self):
        return [it.data(0, Qt.UserRole) for it in self.tree.selectedItems()]

    def _sync(self):
        has = bool(self._sel())
        for b in (self.b_open, self.b_folder, self.b_again, self.b_rm):
            b.setEnabled(has)

    def _open(self):
        for x in self._sel()[:1]:
            p = x.get("filepath")
            if p and os.path.exists(p):
                open_path(p)
            else:
                self._folder()

    def _folder(self):
        for x in self._sel()[:1]:
            p = x.get("filepath")
            d = os.path.dirname(p) if p else None
            if d and os.path.isdir(d):
                open_path(d)

    def _again(self):
        for x in self._sel():
            self.redownload.emit(x)

    def _remove(self):
        ids = [x.get("id") for x in self._sel()]
        if ids:
            self.h.remove(ids)
            self.reload()

    def _clear(self):
        if not self.h.items:
            return
        if ask(self, "Limpar histórico",
               "Apagar todo o histórico de downloads?",
               details="Só a lista é apagada. Os arquivos baixados continuam na pasta.",
               yes="LIMPAR", yes_kind="danger", kind="error",
               confirm=f"Sim, apagar os {len(self.h.items)} itens do histórico"):
            self.h.clear()
            self.reload()

    def _menu(self, pos):
        if not self._sel():
            return
        m = QMenu(self)
        m.addAction("▶  Abrir arquivo", self._open)
        m.addAction("📁  Abrir pasta", self._folder)
        m.addAction("↻  Baixar de novo", self._again)
        m.addSeparator()
        m.addAction("✕  Remover do histórico", self._remove)
        m.exec(self.tree.viewport().mapToGlobal(pos))


_ = theme
