"""Pastas do usuário usadas pelo GetScope (XDG)."""
import os
import subprocess


def _xdg(var, default):
    return os.environ.get(var) or os.path.expanduser(default)


def config_dir():
    d = os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), "getscope")
    os.makedirs(d, exist_ok=True)
    return d


def data_dir():
    d = os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"), "getscope")
    os.makedirs(d, exist_ok=True)
    return d


def engine_dir():
    d = os.path.join(data_dir(), "engine")
    os.makedirs(d, exist_ok=True)
    return d


def bin_dir():
    d = os.path.join(data_dir(), "bin")
    os.makedirs(d, exist_ok=True)
    return d


def default_download_dir():
    videos = None
    try:
        out = subprocess.run(["xdg-user-dir", "VIDEOS"], capture_output=True, text=True, timeout=3)
        p = out.stdout.strip()
        if out.returncode == 0 and p and p != os.path.expanduser("~"):
            videos = p
    except (OSError, subprocess.SubprocessError):
        pass
    if not videos:
        for name in ("Vídeos", "Videos"):
            cand = os.path.expanduser(f"~/{name}")
            if os.path.isdir(cand):
                videos = cand
                break
    if not videos:
        videos = os.path.expanduser("~/Vídeos")
    return os.path.join(videos, "GetScope")


def clean_env(env=None):
    """Ambiente sem as variáveis do empacotamento, para programas do sistema
    (ffmpeg, pkexec, gerenciador de arquivos) não carregarem as bibliotecas do app."""
    env = dict(os.environ if env is None else env)
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig:
        env["LD_LIBRARY_PATH"] = orig
    else:
        env.pop("LD_LIBRARY_PATH", None)
    for k in ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "PYTHONHOME",
              "PYTHONPATH"):
        env.pop(k, None)
    return env
