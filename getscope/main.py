"""Ponto de entrada do GetScope."""
import os
import sys


def _sanitize_env():
    """Depois que o Qt carregou, remove do ambiente as variáveis do empacotamento para que
    ffmpeg, pkexec, xdg-open e o gerenciador de arquivos usem só as bibliotecas do sistema."""
    from .core.paths import clean_env
    keep = clean_env()
    for k in list(os.environ):
        if k not in keep:
            del os.environ[k]
    os.environ.update(keep)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    from .core import engine
    engine.activate()  # antes de qualquer import do yt_dlp
    if "--engine-info" in argv:  # diagnóstico sem interface
        import json
        info = engine.info()
        import yt_dlp
        info["module"] = yt_dlp.__file__
        try:
            import yt_dlp_ejs
            info["ejs"] = yt_dlp_ejs.__file__
        except ImportError:
            info["ejs"] = None
        from .core import net
        info["ssl"] = bool(net.context())
        print(json.dumps(info))
        return 0

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication
    from scopekit import theme

    QCoreApplication.setApplicationName("GetScope")
    QCoreApplication.setOrganizationName("GetScope")
    app = QApplication(argv)
    app.setDesktopFileName("getscope")
    app.setStyle("Fusion")
    app.setStyleSheet(theme.build_qss())
    QCoreApplication.libraryPaths()  # fixa os caminhos de plugins antes de limpar o ambiente
    if getattr(sys, "frozen", False):
        _sanitize_env()

    if "--selftest" in argv:  # GetScope --selftest URL PASTA: baixa sem interface (diagnóstico)
        return _selftest(app, argv[argv.index("--selftest") + 1], argv[argv.index("--selftest") + 2])

    from .ui.window import MainWindow
    from .ui.widgets import app_icon
    app.setWindowIcon(app_icon())
    w = MainWindow()
    w.show()
    if len(argv) > 1 and argv[1].startswith(("http://", "https://")):
        w.p_down.url.setText(argv[1])
        w.analyze(argv[1])
    return app.exec()


def _selftest(app, url, outdir):
    from PySide6.QtCore import QTimer
    from .core import formats
    from .core.jobs import DownloadManager, Env, History
    from .core.settings import Settings
    s = Settings(path=os.path.join(outdir, ".selftest-settings.json"))
    s.data["download_dir"] = outdir
    m = DownloadManager(s, Env(), History(path=os.path.join(outdir, ".selftest-history.json")),
                        queue_path=os.path.join(outdir, ".selftest-queue.json"))
    c = formats.choice_from_settings(s)
    jobs = [m.add(url, dict(c, mode="video", quality=720, container="mp4"), "video"),
            m.add(url, dict(c, mode="audio", audio_format="mp3"), "audio")]
    result = {}

    def check():
        if all(j.status in ("done", "error") for j in jobs):
            for j in jobs:
                print(j.choice["mode"], j.status, j.filepath, j.error or "")
            result["ok"] = all(j.status == "done" for j in jobs)
            app.quit()
    t = QTimer()
    t.timeout.connect(check)
    t.start(300)
    QTimer.singleShot(120000, app.quit)
    app.exec()
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
