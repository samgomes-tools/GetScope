"""Motor de download (yt-dlp).

O AppImage traz uma versão embutida do yt-dlp. Como o YouTube muda com frequência,
o usuário pode baixar a versão mais nova para ~/.local/share/getscope/engine/yt-dlp.zip
(o executável oficial "zipimport" do yt-dlp, que já inclui o yt-dlp-ejs). Na abertura,
se essa cópia for mais nova que a embutida, ela é usada no lugar.
"""
import hashlib
import importlib.machinery
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import zipfile

from . import net, paths

RELEASES = "https://github.com/yt-dlp/yt-dlp/releases"
_PKGS = ("yt_dlp", "yt_dlp_ejs")

state = {"source": "bundled", "zip": None, "zip_version": None, "error": None}


def engine_zip():
    return os.path.join(paths.engine_dir(), "yt-dlp.zip")


def parse_version(v):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", v or ""))
    except ValueError:
        return ()


def zip_version(path):
    """Lê a versão de um yt-dlp zipimport sem importá-lo; None se o arquivo não for válido."""
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "yt_dlp/__init__.py" not in names or "yt_dlp/version.py" not in names:
                return None
            src = z.read("yt_dlp/version.py").decode("utf-8", "replace")
    except (OSError, zipfile.BadZipFile):
        return None
    m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", src)
    return m.group(1) if m else None


def bundled_version():
    try:
        from .. import _bundled  # gerado pelo build.sh
        return _bundled.YTDLP_VERSION
    except ImportError:
        pass
    try:
        from importlib.metadata import version
        return version("yt-dlp")
    except Exception:
        return None


class _ZipFinder:
    """Faz os pacotes yt_dlp* virem do zip do usuário, antes da cópia embutida."""

    def __init__(self, zpath):
        self.zpath = zpath

    def find_spec(self, name, path=None, target=None):
        top = name.partition(".")[0]
        if top not in _PKGS:
            return None
        if "." not in name:
            return importlib.machinery.PathFinder.find_spec(name, [self.zpath])
        parent = sys.modules.get(name.rpartition(".")[0])
        ppath = getattr(parent, "__path__", None)
        if not ppath:
            return None
        return importlib.machinery.PathFinder.find_spec(name, list(ppath))

    def invalidate_caches(self):
        pass


def activate():
    """Chamar antes de qualquer import do yt_dlp."""
    z = engine_zip()
    if os.environ.get("GETSCOPE_BUNDLED_ENGINE") == "1" or not os.path.isfile(z):
        return state
    zv = zip_version(z)
    state.update(zip=z, zip_version=zv)
    bv = bundled_version()
    if zv and (not bv or parse_version(zv) > parse_version(bv)):
        if any(n == p or n.startswith(p + ".") for n in sys.modules for p in _PKGS):
            state["error"] = "yt-dlp já carregado; reinicie para usar a versão atualizada"
            return state
        sys.meta_path.insert(0, _ZipFinder(z))
        state["source"] = "updated"
    return state


def ytdlp():
    import yt_dlp
    return yt_dlp


def current_version():
    try:
        return ytdlp().version.__version__
    except Exception:
        return bundled_version()


def info():
    return {
        "version": current_version(),
        "source": state["source"],
        "bundled": bundled_version(),
        "zip_version": state["zip_version"],
        "zip": state["zip"],
        "error": state["error"],
    }


# ---------------------------------------------------------------- atualização

def _open(url, timeout=20):
    return net.urlopen(url, timeout=timeout)


def _location(url):
    try:
        r = net.urlopen(url, timeout=20, method="HEAD", follow=False)
        return r.headers.get("Location") or r.geturl()
    except urllib.error.HTTPError as e:
        return e.headers.get("Location")
    except OSError:
        return None


def latest_version():
    """Versão mais recente publicada (pelos redirecionamentos do GitHub, com a API como reserva)."""
    loc = _location(RELEASES + "/latest") or ""
    m = re.search(r"/tag/([^/?#]+)", loc)
    if not m:
        loc = _location(RELEASES + "/latest/download/yt-dlp") or ""
        m = re.search(r"/download/([^/?#]+)/yt-dlp", loc)
    if m:
        return m.group(1)
    try:
        import json
        with net.urlopen("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", timeout=20) as r:
            tag = json.load(r).get("tag_name")
        if tag:
            return tag
    except (OSError, ValueError):
        pass
    raise RuntimeError("Não foi possível consultar a versão mais recente do yt-dlp. Verifique a conexão.")


def download_update(tag, progress=None):
    """Baixa o yt-dlp zipimport da versão `tag`, confere o SHA-256 e instala."""
    base = f"{RELEASES}/download/{tag}"
    with _open(base + "/SHA2-256SUMS") as r:
        sums = r.read().decode("utf-8", "replace")
    expected = None
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == "yt-dlp":
            expected = parts[0].lower()
    if not expected:
        raise RuntimeError("Lista de verificação (SHA2-256SUMS) sem o arquivo yt-dlp.")
    fd, tmp = tempfile.mkstemp(prefix="getscope-engine-", dir=paths.engine_dir())
    h = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as out, _open(base + "/yt-dlp", timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done, total)
        if h.hexdigest() != expected:
            raise RuntimeError("O arquivo baixado não confere com a assinatura SHA-256. Nada foi alterado.")
        v = zip_version(tmp)
        if not v:
            raise RuntimeError("O arquivo baixado não é um yt-dlp válido. Nada foi alterado.")
        os.replace(tmp, engine_zip())
        return v
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def remove_update():
    z = engine_zip()
    if os.path.exists(z):
        os.unlink(z)


def copy_zip_into_place(src):
    """Usado nos testes: instala um zip local como motor atualizado."""
    shutil.copy(src, engine_zip())
