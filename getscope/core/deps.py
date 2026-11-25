"""Detecção da distro e das dependências externas (FFmpeg e runtime JavaScript)."""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

from . import net, paths

ROOT = os.environ.get("GETSCOPE_ROOT", "/")  # usado nos testes
DENO_ZIP = "deno-x86_64-unknown-linux-gnu.zip"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/" + DENO_ZIP


def _root(p):
    return os.path.join(ROOT, p.lstrip("/"))


def os_release():
    data = {}
    for p in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(_root(p), encoding="utf-8") as f:
                for line in f:
                    k, sep, v = line.strip().partition("=")
                    if sep:
                        data[k] = v.strip().strip('"').strip("'")
            break
        except OSError:
            continue
    return data


def distro():
    """Retorna dict com nome, família (arch/debian/fedora/suse/outra) e gerenciador de pacotes."""
    rel = os_release()
    ids = " ".join([rel.get("ID", ""), rel.get("ID_LIKE", "")]).lower().split()
    fam = "outra"
    for key, names in (("arch", ("arch", "manjaro", "endeavouros", "cachyos", "garuda", "artix")),
                       ("debian", ("debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "kali", "neon")),
                       ("fedora", ("fedora", "rhel", "centos", "nobara", "ultramarine", "rocky", "almalinux")),
                       ("suse", ("suse", "opensuse", "opensuse-tumbleweed", "opensuse-leap"))):
        if any(i in names or i.startswith(key) for i in ids):
            fam = key
            break
    pm = {"arch": "pacman", "debian": "apt", "fedora": "dnf", "suse": "zypper"}.get(fam)
    return {"name": rel.get("PRETTY_NAME") or rel.get("NAME") or "Linux", "family": fam,
            "pm": pm, "id": rel.get("ID", "")}


FFMPEG_INSTALL = {
    "arch": "pacman -S --needed --noconfirm ffmpeg",
    "debian": "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg",
    "fedora": "dnf install -y ffmpeg || dnf install -y ffmpeg-free",
    "suse": "zypper --non-interactive install ffmpeg",
}


def ffmpeg_install_command(fam):
    cmd = FFMPEG_INSTALL.get(fam)
    return ["pkexec", "sh", "-c", cmd] if cmd else None


def _which(name):
    for d in (paths.bin_dir(),):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which(name, path=paths.clean_env().get("PATH"))


def _version(cmd, pattern):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=8, env=paths.clean_env())
        m = re.search(pattern, out.stdout + out.stderr)
        return m.group(1) if m else "?"
    except (OSError, subprocess.SubprocessError):
        return None


def ffmpeg():
    ff = _which("ffmpeg")
    if not ff:
        return None
    probe = _which("ffprobe")
    return {"path": ff, "ffprobe": probe, "version": _version([ff, "-version"], r"ffmpeg version (\S+)")}


JS_ORDER = (("deno", r"deno (\S+)"), ("node", r"v?(\d+\.\d+\.\d+)"), ("bun", r"(\d+\.\d+\.\d+)"),
            ("qjs", r"version (\S+)"))


def js_runtimes():
    """Lista de runtimes JavaScript encontrados, na ordem de preferência do yt-dlp."""
    found = []
    extra = [os.path.expanduser("~/.deno/bin/deno")]
    for name, pat in JS_ORDER:
        p = _which(name)
        if not p and name == "deno":
            p = next((x for x in extra if os.path.isfile(x)), None)
        if not p:
            continue
        flag = "--version" if name != "qjs" else "-h"
        v = _version([p, flag], pat)
        if v is None:
            continue
        if name == "node":
            try:
                if int(v.split(".")[0]) < 20:
                    continue  # o yt-dlp exige Node 20 ou mais novo
            except ValueError:
                pass
        found.append({"name": "quickjs" if name == "qjs" else name, "path": p, "version": v})
    return found


def ytdlp_js_param(runtimes):
    return {r["name"]: {"path": r["path"]} for r in runtimes}


def install_deno(progress=None):
    """Baixa o Deno oficial para ~/.local/share/getscope/bin (sem precisar de senha)."""
    def get(url, timeout=60):
        return net.urlopen(url, timeout=timeout)
    expected = None
    try:
        with get(DENO_URL + ".sha256sum", 20) as r:
            m = re.search(r"\b([0-9a-fA-F]{64})\b", r.read().decode("utf-8", "replace"))
            expected = m.group(1).lower() if m else None
    except OSError:
        expected = None
    fd, tmp = tempfile.mkstemp(prefix="getscope-deno-", suffix=".zip")
    h = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as out, get(DENO_URL) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done, total)
        if expected and h.hexdigest() != expected:
            raise RuntimeError("O Deno baixado não confere com a assinatura SHA-256. Nada foi instalado.")
        dest = os.path.join(paths.bin_dir(), "deno")
        with zipfile.ZipFile(tmp) as z:
            if "deno" not in z.namelist():
                raise RuntimeError("Pacote do Deno inesperado.")
            with z.open("deno") as src, open(dest + ".new", "wb") as dst:
                shutil.copyfileobj(src, dst)
        os.chmod(dest + ".new", os.stat(dest + ".new").st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(dest + ".new", dest)
        return dest
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def disk_free(path):
    p = path
    while p and not os.path.exists(p):
        p = os.path.dirname(p)
    try:
        return shutil.disk_usage(p or "/").free
    except OSError:
        return None


def writable(path):
    p = path
    while p and not os.path.exists(p):
        p = os.path.dirname(p)
    return bool(p) and os.access(p, os.W_OK)
