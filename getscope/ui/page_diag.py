"""Aba Diagnóstico: motor, FFmpeg, runtime JavaScript, sistema e registro de erros."""
import os
import shlex
import time

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLayout, QPlainTextEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from scopekit import theme
from scopekit.ui import ask, btn, clear_layout, message

from ..core import deps, engine, formats, paths
from . import tasks
from .widgets import KeyVal, card, status_dot


class DiagPage(QWidget):
    changed = Signal()            # dependências mudaram (atualiza pill/status)
    engine_updated = Signal(str)  # nova versão instalada (pede reinício)

    def __init__(self, env, settings):
        super().__init__()
        self.env = env
        self.settings = settings
        self.proc = None
        self.busy = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        tb = QWidget()
        tb.setObjectName("Toolbar")
        tb.setAttribute(Qt.WA_StyledBackground, True)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(12, 4, 12, 4)
        tl.addWidget(btn("⟳  Verificar novamente", "tool", self.refresh))
        tl.addStretch(1)
        self.summary = QLabel()
        tl.addWidget(self.summary)
        root.addWidget(tb)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        inner = QWidget()
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(20, 18, 20, 18)
        self.lay.setSpacing(14)
        self.lay.setSizeConstraint(QLayout.SetMinimumSize)
        self.cards = QVBoxLayout()
        self.cards.setSpacing(14)
        self.lay.addLayout(self.cards)
        lc, ll = card("Registro")
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(190)
        self.console.setMaximumBlockCount(3000)
        ll.addWidget(self.console)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn("Copiar registro", None, lambda: QApplication.clipboard().setText(
            self.console.toPlainText())))
        row.addWidget(btn("Limpar", "cancel", self.console.clear))
        ll.addLayout(row)
        self.lay.addWidget(lc)
        self.lay.addStretch(1)
        sc.setWidget(inner)
        root.addWidget(sc, 1)
        self.refresh(log=False)

    # ------------------------------------------------------------ registro
    def log(self, level, msg):
        tag = {"error": "ERRO ", "warning": "AVISO", "info": "INFO "}.get(level, "INFO ")
        self.console.appendPlainText(f"{time.strftime('%H:%M:%S')}  {tag}  {msg}")

    # ------------------------------------------------------------ estado
    def problems(self):
        p = []
        if not self.env.ffmpeg:
            p.append("FFmpeg")
        if not self.env.js:
            p.append("JavaScript")
        if not deps.writable(self.settings["download_dir"]):
            p.append("Pasta")
        return p

    def refresh(self, *_, log=True):
        self.env.refresh()
        self._rebuild(log)

    def _rebuild(self, log=False):
        clear_layout(self.cards)
        self._engine_card()
        self._ffmpeg_card()
        self._js_card()
        self._system_card()
        pr = self.problems()
        if pr:
            self.summary.setText(f"⚠  {len(pr)} pendência{'s' if len(pr) > 1 else ''}: {', '.join(pr)}")
            self.summary.setStyleSheet(f"color:{theme.WARN}; font-weight:700;")
        else:
            self.summary.setText("✓  Tudo pronto para baixar")
            self.summary.setStyleSheet(f"color:{theme.GREEN}; font-weight:700;")
        if log:
            self.log("info", "Verificação concluída" + (f" — pendências: {', '.join(pr)}" if pr else ""))
        self.changed.emit()

    def _row(self, state, title, desc, kv_items, buttons):
        w, lay = card()
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(status_dot(state), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet("font-size:12.5pt; color:#ffffff; font-weight:600;")
        col.addWidget(t)
        d = QLabel(desc)
        d.setObjectName("Muted")
        d.setWordWrap(True)
        col.addWidget(d)
        if kv_items:
            kv = KeyVal()
            for k, v, *c in kv_items:
                kv.set(k, v, c[0] if c else None)
            col.addSpacing(4)
            col.addWidget(kv)
        top.addLayout(col, 1)
        bcol = QVBoxLayout()
        bcol.setSpacing(8)
        for b in buttons:
            b.setMinimumWidth(190)
            bcol.addWidget(b)
        bcol.addStretch(1)
        top.addLayout(bcol)
        lay.addLayout(top)
        self.cards.addWidget(w)

    def _engine_card(self):
        ei = engine.info()
        src = "Versão atualizada (baixada pelo GetScope)" if ei["source"] == "updated" else "Versão embutida no AppImage"
        items = [("Versão em uso", ei["version"] or "?"), ("Origem", src)]
        if ei["source"] == "updated" and ei["bundled"]:
            items.append(("Embutida", ei["bundled"]))
        elif ei["zip_version"] and ei["source"] != "updated":
            items.append(("Baixada", f"{ei['zip_version']} (mais antiga que a embutida, ignorada)"))
        if ei["error"]:
            items.append(("Aviso", ei["error"], theme.WARN))
        b1 = btn(self.busy.get("engine") or "⟳  VERIFICAR ATUALIZAÇÃO", "blue", self._check_engine)
        b1.setEnabled("engine" not in self.busy)
        bs = [b1]
        if ei["zip"]:
            bs.append(btn("Voltar para a embutida", "cancel", self._reset_engine))
        self._row("ok", "Motor de download (yt-dlp)",
                  "O YouTube muda com frequência. Se os downloads começarem a falhar, atualize o motor — "
                  "não é preciso baixar o GetScope de novo.", items, bs)

    def _ffmpeg_card(self):
        ff = self.env.ffmpeg
        fam = self.env.distro["family"]
        if ff:
            self._row("ok", "FFmpeg", "Junta vídeo e áudio nas qualidades altas, converte para MP3 e embute capas.",
                      [("Versão", ff["version"]), ("Local", ff["path"]),
                       ("FFprobe", "encontrado" if ff["ffprobe"] else "não encontrado",
                        None if ff["ffprobe"] else theme.WARN)], [])
            return
        cmd = deps.FFMPEG_INSTALL.get(fam)
        b = btn(self.busy.get("ffmpeg") or "⬇  INSTALAR FFMPEG", "green", self._install_ffmpeg)
        b.setEnabled(bool(cmd) and "ffmpeg" not in self.busy)
        items = [("Distro", self.env.distro["name"])]
        items.append(("Comando", cmd if cmd else "instale o pacote ffmpeg pelo gerenciador da sua distro"))
        self._row("error", "FFmpeg não encontrado",
                  "Sem ele, os vídeos ficam limitados a um arquivo único (geralmente 360p no YouTube) e o áudio "
                  "não pode ser convertido. A instalação pede a sua senha de administrador.", items, [b])

    def _js_card(self):
        js = self.env.js
        if js:
            main = js[0]
            others = ", ".join(f"{r['name']} {r['version']}" for r in js[1:])
            items = [("Em uso", f"{main['name'].capitalize()} {main['version']}"), ("Local", main["path"])]
            if others:
                items.append(("Também encontrados", others))
            bs = []
            if main["name"] != "deno":
                bs.append(btn(self.busy.get("deno") or "⬇  BAIXAR DENO", None, self._install_deno))
                bs[0].setEnabled("deno" not in self.busy)
            self._row("ok", "Runtime JavaScript", "O yt-dlp usa um runtime JavaScript para resolver os desafios do "
                      "YouTube. O Deno é o recomendado.", items, bs)
            return
        b = btn(self.busy.get("deno") or "⬇  BAIXAR DENO", "green", self._install_deno)
        b.setEnabled("deno" not in self.busy)
        self._row("warn", "Runtime JavaScript não encontrado",
                  "Necessário para o YouTube: sem ele vários formatos somem ou o download falha. O GetScope baixa "
                  "o Deno oficial para a sua pasta pessoal, sem pedir senha.",
                  [("Destino", os.path.join(paths.bin_dir(), "deno"))], [b])

    def _system_card(self):
        d = self.env.distro
        fam = {"arch": "Arch", "debian": "Debian/Ubuntu", "fedora": "Fedora", "suse": "openSUSE"}.get(
            d["family"], "não identificada")
        folder = self.settings["download_dir"]
        ok = deps.writable(folder)
        free = deps.disk_free(folder)
        self._row("ok" if ok else "error", "Sistema", "Distro detectada e pasta onde os downloads são salvos.", [
            ("Distro", d["name"]), ("Base", fam), ("Pacotes", d["pm"] or "—"),
            ("Pasta", folder), ("Gravação", "permitida" if ok else "sem permissão", None if ok else theme.ERROR),
            ("Espaço livre", formats.human_size(free) if free is not None else "—"),
            ("Dados do app", paths.data_dir()),
        ], [])

    # ------------------------------------------------------------ ações
    def _set_busy(self, key, text):
        if text:
            self.busy[key] = text
        else:
            self.busy.pop(key, None)
        if text:
            self._rebuild()
        else:
            self.refresh(log=False)

    def check_engine(self, silent=False):
        """Consulta a versão mais nova e, se houver, baixa e instala."""
        if "engine" in self.busy:
            return
        self._set_busy("engine", "VERIFICANDO…")
        cur = engine.current_version()

        def got(tag):
            if engine.parse_version(tag) <= engine.parse_version(cur):
                self._set_busy("engine", None)
                self.log("info", f"Motor yt-dlp {cur} já é a versão mais recente")
                if not silent:
                    message(self, "Motor atualizado", f"Você já está com a versão mais recente do yt-dlp ({cur}).",
                            "ok")
                return
            if not silent and not ask(self, "Atualizar motor", f"Há uma versão nova do yt-dlp: {tag}.",
                                      details=f"Versão atual: {cur}. O arquivo é conferido pela assinatura "
                                              "SHA-256 antes de ser instalado.", yes="ATUALIZAR"):
                self._set_busy("engine", None)
                return
            self.log("info", f"Baixando yt-dlp {tag}…")
            tasks.run(engine.download_update, tag, done=installed, failed=fail,
                      progress=lambda a, b: self._progress("engine", a, b))

        def installed(v):
            self._set_busy("engine", None)
            self.log("info", f"Motor yt-dlp {v} instalado; reinicie para usar")
            self.engine_updated.emit(v)

        def fail(err):
            self._set_busy("engine", None)
            self.log("error", f"Atualização do motor: {err}")
            if not silent:
                message(self, "Não foi possível atualizar", "A atualização do motor falhou.", "error", err)

        tasks.run(engine.latest_version, done=got, failed=fail)

    def _progress(self, key, a, b):
        # reconstrói a tela só a cada 5%, não a cada pedaço baixado
        pct = a * 100 // max(b, 1)
        if pct // 5 != getattr(self, "_last_pct", {}).get(key):
            self.__dict__.setdefault("_last_pct", {})[key] = pct // 5
            self._set_busy(key, f"BAIXANDO {pct}%")

    def _check_engine(self):
        self.check_engine(silent=False)

    def _reset_engine(self):
        if ask(self, "Voltar para a versão embutida",
               "Apagar o motor baixado e usar a versão que vem no AppImage?",
               details="Vale a pena só se a versão nova estiver com problema. É preciso reiniciar o GetScope.",
               yes="VOLTAR", yes_kind="danger", confirm="Sim, apagar o motor baixado"):
            engine.remove_update()
            self.log("info", "Motor baixado removido; reinicie para usar a versão embutida")
            self.engine_updated.emit(engine.bundled_version() or "embutida")
            self.refresh(log=False)

    def _install_ffmpeg(self):
        fam = self.env.distro["family"]
        cmd = deps.ffmpeg_install_command(fam)
        if not cmd:
            return
        if not ask(self, "Instalar FFmpeg",
                   f"O FFmpeg será instalado pelo gerenciador de pacotes do {self.env.distro['name']}.",
                   details="Comando: " + deps.FFMPEG_INSTALL[fam] + "\nO sistema vai pedir a sua senha.",
                   yes="INSTALAR"):
            return
        if not deps._which("pkexec"):
            message(self, "pkexec não encontrado",
                    "Não foi possível pedir a senha de administrador. Rode este comando no terminal:", "warn",
                    "sudo sh -c " + shlex.quote(deps.FFMPEG_INSTALL[fam]))
            return
        self.log("info", "Instalando FFmpeg: " + deps.FFMPEG_INSTALL[fam])
        self._set_busy("ffmpeg", "INSTALANDO…")
        p = QProcess(self)
        env = QProcessEnvironment()
        for k, v in paths.clean_env().items():
            env.insert(k, v)
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._proc_out(p))
        p.finished.connect(lambda code, _st: self._ffmpeg_done(code))
        p.errorOccurred.connect(lambda e: self._ffmpeg_done(-1) if e == QProcess.FailedToStart else None)
        self.proc = p
        p.start(cmd[0], cmd[1:])

    def _proc_out(self, p):
        data = bytes(p.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            if line.strip():
                self.console.appendPlainText("        " + line)

    def _ffmpeg_done(self, code):
        self.proc = None
        self._set_busy("ffmpeg", None)
        if self.env.ffmpeg:
            self.log("info", "FFmpeg instalado")
            message(self, "FFmpeg instalado", "Pronto! Agora você pode baixar em qualquer qualidade.", "ok")
        elif code in (126, 127):
            self.log("warning", "Instalação do FFmpeg cancelada")
        else:
            self.log("error", f"Instalação do FFmpeg terminou com código {code}")
            message(self, "Falha na instalação", "O FFmpeg não foi instalado. Veja o registro abaixo.", "error")

    def _install_deno(self):
        self._set_busy("deno", "BAIXANDO…")
        self.log("info", "Baixando Deno de github.com/denoland/deno…")

        def done(path):
            self._set_busy("deno", None)
            self.log("info", f"Deno instalado em {path}")
            message(self, "Deno instalado", "O runtime JavaScript está pronto para o YouTube.", "ok")

        def fail(err):
            self._set_busy("deno", None)
            self.log("error", f"Download do Deno: {err}")
            message(self, "Não foi possível baixar o Deno", "Verifique a conexão e tente novamente.", "error", err)

        tasks.run(deps.install_deno, done=done, failed=fail,
                  progress=lambda a, b: self._progress("deno", a, b))
