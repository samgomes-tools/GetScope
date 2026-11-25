"""Gera capturas das telas com dados simulados: python3 tools/screenshots.py PASTA [MINIATURAS]"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile  # noqa: E402
_tmp = tempfile.mkdtemp(prefix="getscope-shots-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_tmp, "cfg")  # não mexe nas configurações reais
os.environ["XDG_DATA_HOME"] = os.path.join(_tmp, "data")

from getscope.core import engine  # noqa: E402
engine.activate()
from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from scopekit import theme  # noqa: E402

out = sys.argv[1]
thumbs = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(out, exist_ok=True)
app = QApplication(["x"])
app.setStyle("Fusion")
app.setStyleSheet(theme.build_qss())

from getscope.core import formats  # noqa: E402
from getscope.ui import widgets  # noqa: E402
from getscope.ui.window import MainWindow  # noqa: E402
from getscope.ui import dialogs  # noqa: E402
from scopekit import ui as sk  # noqa: E402

if thumbs:
    for i in range(1, 6):
        widgets._THUMBS[f"t{i}"] = QPixmap(os.path.join(thumbs, f"thumb{i}.jpg"))

w = MainWindow(startup_checks=False)
w.settings.update({"download_dir": os.path.expanduser("~/Vídeos/GetScope")})
w.resize(1360, 820)
w.show()
s = w.settings
c = formats.choice_from_settings(s)
demo = [
    ("Como montar um PC gamer em 2026 — guia completo", "Youtube", "Canal Hardware", dict(c, quality=1080),
     dict(status="downloading", progress=63.4, speed=4.2e6, eta=48, total=412e6, downloaded=261e6,
          stage="Baixando vídeo (1/2)")),
    ("Lofi para estudar — 2 horas", "Youtube", "Lofi Café", dict(c, mode="audio", audio_format="mp3"),
     dict(status="processing", progress=100, stage="Convertendo áudio", total=165e6)),
    ("Receita de pão caseiro rápido", "Instagram", "cozinha.da.vo", dict(c, quality="best"),
     dict(status="done", progress=100, total=38e6, filepath="/home/samuel/Vídeos/GetScope/Receita.mp4")),
    ("Trailer oficial 4K", "Vimeo", "Estúdio", dict(c, quality=2160, container="mkv"),
     dict(status="paused", progress=27.0, total=1.9e9, downloaded=0.51e9)),
    ("Vídeo privado", "Youtube", "", dict(c, quality=720),
     dict(status="error", progress=0, error="Este vídeo é privado.",
          error_hint="Só é possível baixar se você tiver acesso e usar os cookies do navegador logado.")),
    ("Dancinha do momento", "TikTok", "@alguem", dict(c), dict(status="queued")),
]
for i, (title, site, up, ch, st) in enumerate(demo, 1):
    j = w.m.add(f"https://exemplo.com/{i}", ch, title, start=False, site=site, uploader=up, duration=600 + i * 73,
                thumb_url=f"t{(i - 1) % 5 + 1}" if thumbs else None)
    for k, v in st.items():
        setattr(j, k, v)
    w.m.job_changed.emit(j.id)
for x in w.m.jobs[2:3]:
    x.finished = time.time()
    w.history.add(x)
w.history.items.append({"id": "h2", "title": "Podcast episódio 42", "url": "https://exemplo.com/p", "site": "Youtube",
                        "format": "MP3 · 192 kbps", "filepath": "/nao/existe.mp3", "size": 54e6,
                        "date": time.time() - 86400})

shots = []


def shot(name, widget=None):
    (widget or w).grab().save(os.path.join(out, name + ".png"))
    shots.append(name)


def step1():
    w.go("downloads")
    w.p_down.tree.setCurrentItem(w.p_down.tree.topLevelItem(0))


def step2():
    shot("1-downloads")
    w.p_down.tree.setCurrentItem(w.p_down.tree.topLevelItem(4))


def step3():
    shot("2-downloads-erro")
    w.go("history")


def step4():
    shot("3-historico")
    w.env.ffmpeg = None
    w.env.js = []
    w.p_diag._rebuild()
    w._update_status()
    w._first_run_hint()
    w.go("diag")


def step5():
    shot("4-diagnostico-pendencias")
    w.hide_banner()
    w.env.refresh()
    w.p_diag._rebuild()
    w._update_status()
    w.go("settings")


def step6():
    shot("5-configuracoes")
    info = {"title": "Como montar um PC gamer em 2026 — guia completo", "uploader": "Canal Hardware",
            "duration": 1834, "extractor_key": "Youtube", "view_count": 1284033, "upload_date": "20261110",
            "thumbnails": [{"url": "t1"}] if thumbs else [],
            "formats": [{"vcodec": "none", "acodec": "opus", "filesize": 28e6}] +
                       [{"height": h, "vcodec": "avc1", "acodec": "none", "filesize": sz}
                        for h, sz in ((2160, 1.6e9), (1440, 780e6), (1080, 384e6), (720, 190e6), (480, 96e6),
                                      (360, 61e6))]}
    d = dialogs.VideoDialog(w, info, s, w.env)
    d.adjustSize()
    d.show()
    QTimer.singleShot(400, lambda: (shot("6-dialogo-video", d), d.close()))
    pl = {"_type": "playlist", "title": "Aulas de violão para iniciantes", "uploader": "Prof. Música",
          "entries": [{"url": f"https://www.youtube.com/watch?v=a{i}", "title": f"Aula {i:02d} — "
                       + ["Postura e afinação", "Primeiros acordes", "Ritmo básico", "Trocando acordes",
                          "Dedilhado", "Pestana", "Escalas", "Primeira música"][i % 8], "duration": 400 + i * 37,
                       "ie_key": "Youtube"} for i in range(1, 15)]}
    p = dialogs.PlaylistDialog(w, pl, s, w.env)
    p.tree.topLevelItem(3).setCheckState(0, Qt.Unchecked)
    QTimer.singleShot(500, lambda: p.show())
    QTimer.singleShot(900, lambda: (shot("7-dialogo-playlist", p), p.close()))
    a = dialogs.AboutDialog(w, w.env)
    QTimer.singleShot(1000, lambda: (a.adjustSize(), a.show()))
    QTimer.singleShot(1300, lambda: (shot("8-sobre", a), a.close()))
    m = sk._msg_dialog(w, "Não foi possível abrir o link", "O YouTube pediu para confirmar que você não é um robô.",
                       "error", "Em Configurações › Acesso, escolha o navegador em que você está logado no YouTube "
                                "para usar os cookies dele, e tente de novo.")
    m.add_button("OK", "blue", m.accept)
    QTimer.singleShot(1400, lambda: (m.adjustSize(), m.show()))
    QTimer.singleShot(1700, lambda: (shot("9-mensagem-erro", m), m.close()))
    QTimer.singleShot(1900, finish)


def finish():
    for j in w.m.jobs:
        j.status = "done"
    w.hide()
    app.quit()


for i, f in enumerate([step1, step2, step3, step4, step5, step6]):
    QTimer.singleShot(400 + i * 500, f)
app.exec()
print("capturas:", ", ".join(shots))
