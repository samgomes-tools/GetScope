import json
import os
import subprocess
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from getscope.core import deps, engine, formats  # noqa: E402
from getscope.core.settings import Settings  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return tmp_path


def choice(**kw):
    c = {"mode": "video", "quality": "best", "container": "mp4", "audio_format": "mp3", "audio_quality": "192",
         "embed_thumbnail": True, "embed_metadata": True, "subtitles": False, "subtitle_langs": "pt,en"}
    c.update(kw)
    return c


def keys(o):
    return [p["key"] for p in o["postprocessors"]]


def test_video_1080_mp4_with_ffmpeg(home):
    s = Settings()
    o = formats.build_opts(choice(quality=1080), s, "/x", True)
    assert o["format"] == "bv*+ba/b"
    assert o["format_sort"][0] == "res:1080" and "ext:mp4:m4a" in o["format_sort"]
    assert o["merge_output_format"] == "mp4"
    assert "EmbedThumbnail" in keys(o) and "FFmpegMetadata" in keys(o)
    assert o["outtmpl"]["default"].startswith("/x/")


def test_video_without_ffmpeg_is_single_file(home):
    o = formats.build_opts(choice(quality=720), Settings(), "/x", False)
    assert o["format"] == "b[height<=720]/b"
    assert o["postprocessors"] == [] and "merge_output_format" not in o


def test_audio_mp3_and_lossless(home):
    o = formats.build_opts(choice(mode="audio", audio_format="mp3", audio_quality="320"), Settings(), "/x", True)
    ext = o["postprocessors"][0]
    assert ext["key"] == "FFmpegExtractAudio" and ext["preferredcodec"] == "mp3" and ext["preferredquality"] == "320"
    o = formats.build_opts(choice(mode="audio", audio_format="wav"), Settings(), "/x", True)
    assert "EmbedThumbnail" not in keys(o)
    assert formats.describe(choice(mode="audio", audio_format="flac")) == "FLAC"


def test_mkv_remux_subtitles_cookies_ratelimit(home):
    s = Settings()
    s.update({"cookies_browser": "firefox", "rate_limit_kb": 500})
    o = formats.build_opts(choice(container="mkv", subtitles=True, subtitle_langs="pt, en"), s, "/x", True,
                           js={"deno": {"path": "/d"}})
    assert "FFmpegVideoRemuxer" in keys(o) and "FFmpegEmbedSubtitle" in keys(o)
    assert o["subtitleslangs"] == ["pt.*", "en.*"]
    assert o["cookiesfrombrowser"] == ("firefox",) and o["ratelimit"] == 500 * 1024
    assert o["js_runtimes"] == {"deno": {"path": "/d"}}


def test_webm_no_thumbnail_embed(home):
    o = formats.build_opts(choice(container="webm"), Settings(), "/x", True)
    assert "EmbedThumbnail" not in keys(o)


def test_friendly_errors():
    m, hint, _ = formats.friendly_error("ERROR: [youtube] x: Sign in to confirm you're not a bot.")
    assert "robô" in m and "cookies" in hint
    m, _, _ = formats.friendly_error("ERROR: Private video. Sign in if you've been granted access")
    assert "privado" in m
    m, _, _ = formats.friendly_error("algo totalmente novo")
    assert m == "algo totalmente novo"


def test_video_heights_and_sizes():
    info = {"formats": [
        {"format_id": "a", "vcodec": "none", "acodec": "opus", "filesize": 1000},
        {"format_id": "v1", "height": 1080, "vcodec": "avc1", "acodec": "none", "filesize": 9000},
        {"format_id": "v2", "height": 720, "vcodec": "avc1", "acodec": "none", "filesize_approx": 5000},
        {"format_id": "v3", "height": 1072, "vcodec": "vp9", "acodec": "none"},
    ]}
    hs = formats.video_heights(info)
    assert hs[0] == (1080, 10000) and hs[1] == (720, 6000)


def test_human_formats():
    assert formats.human_size(1536) == "2 KB"
    assert formats.human_size(5 * 1024 ** 3) == "5,0 GB"
    assert formats.human_time(3725) == "1:02:05"
    assert formats.human_time(65) == "1:05"


@pytest.mark.parametrize("osrel,fam,pm", [
    ('ID=arch\nPRETTY_NAME="Arch Linux"', "arch", "pacman"),
    ('ID=cachyos\nID_LIKE=arch\nPRETTY_NAME="CachyOS"', "arch", "pacman"),
    ('ID=linuxmint\nID_LIKE="ubuntu debian"\nPRETTY_NAME="Linux Mint 22"', "debian", "apt"),
    ('ID=fedora\nPRETTY_NAME="Fedora Linux 41"', "fedora", "dnf"),
    ('ID=nobara\nID_LIKE="rhel centos fedora"', "fedora", "dnf"),
    ('ID=opensuse-tumbleweed\nID_LIKE="opensuse suse"', "suse", "zypper"),
    ('ID=gentoo', "outra", None),
])
def test_distro_detection(tmp_path, monkeypatch, osrel, fam, pm):
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "os-release").write_text(osrel)
    monkeypatch.setattr(deps, "ROOT", str(tmp_path))
    d = deps.distro()
    assert d["family"] == fam and d["pm"] == pm
    if pm:
        cmd = deps.ffmpeg_install_command(fam)
        assert cmd[:3] == ["pkexec", "sh", "-c"] and "ffmpeg" in cmd[3]


def test_clean_env():
    env = {"LD_LIBRARY_PATH": "/tmp/_MEI/x", "LD_LIBRARY_PATH_ORIG": "/usr/local/lib", "QT_PLUGIN_PATH": "/q",
           "PATH": "/usr/bin"}
    from getscope.core.paths import clean_env
    e = clean_env(env)
    assert e["LD_LIBRARY_PATH"] == "/usr/local/lib" and "QT_PLUGIN_PATH" not in e and e["PATH"] == "/usr/bin"
    assert "LD_LIBRARY_PATH" not in clean_env({"LD_LIBRARY_PATH": "/tmp/_MEI"})


def test_settings_persist_and_ignore_unknown(home):
    s = Settings()
    assert s["download_dir"].endswith("GetScope")
    s.update({"max_concurrent": 4, "bogus": 1})
    s2 = Settings()
    assert s2["max_concurrent"] == 4 and "bogus" not in s2.data


def _make_engine_zip(path, version):
    import yt_dlp
    import yt_dlp_ejs
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for pkg in (yt_dlp, yt_dlp_ejs):
            base = os.path.dirname(pkg.__file__)
            parent = os.path.dirname(base)
            for dp, _dn, fns in os.walk(base):
                if "__pycache__" in dp:
                    continue
                for fn in fns:
                    full = os.path.join(dp, fn)
                    arc = os.path.relpath(full, parent)
                    if arc == os.path.join("yt_dlp", "version.py"):
                        src = open(full).read()
                        import re
                        src = re.sub(r"__version__ = '[^']+'", f"__version__ = '{version}'", src)
                        z.writestr(arc, src)
                    else:
                        z.write(full, arc)


def _run_engine(home):
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from getscope.core import engine; st = engine.activate()\n"
            "import yt_dlp, yt_dlp.utils, yt_dlp_ejs\n"
            "print(st['source'], yt_dlp.version.__version__, yt_dlp.utils.__file__, yt_dlp_ejs.__file__)") % ROOT
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / "data"))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout.split()


def test_engine_update_takes_precedence(home):
    ed = home / "data" / "getscope" / "engine"
    ed.mkdir(parents=True)
    z = ed / "yt-dlp.zip"
    _make_engine_zip(z, "2099.01.01")
    assert engine.zip_version(str(z)) == "2099.01.01"
    src, ver, utils_file, ejs_file = _run_engine(home)
    assert src == "updated" and ver == "2099.01.01"
    assert "yt-dlp.zip" in utils_file and "yt-dlp.zip" in ejs_file  # submódulos também vêm do zip


def test_engine_older_zip_is_ignored(home):
    ed = home / "data" / "getscope" / "engine"
    ed.mkdir(parents=True)
    _make_engine_zip(ed / "yt-dlp.zip", "2000.01.01")
    src, ver, utils_file, _ = _run_engine(home)
    assert src == "bundled" and ver != "2000.01.01" and "yt-dlp.zip" not in utils_file


def test_invalid_zip_rejected(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"not a zip")
    assert engine.zip_version(str(p)) is None


def test_job_cleanup_only_temp_files(tmp_path):
    from getscope.core.jobs import DownloadManager, Job
    final = tmp_path / "Mr.frog.mp4"
    part = tmp_path / "Video.f137.mp4.part"
    stream = tmp_path / "Video.f251.webm"
    ytdl = tmp_path / "Video.f137.mp4.ytdl"
    for f in (final, part, stream, ytdl):
        f.write_text("x")
    j = Job("u", {})
    j.tmpfiles = {str(final), str(part), str(stream)}
    DownloadManager._cleanup(j)
    assert final.exists()
    assert not part.exists() and not stream.exists() and not ytdl.exists()


def test_history_and_queue_roundtrip(home, qapp):
    from getscope.core.jobs import DownloadManager, Env, History
    s = Settings()
    h = History()
    m = DownloadManager(s, Env(), h)
    m.add("https://example.com/v", choice(), "Um vídeo", start=False)
    m.save_queue()
    m2 = DownloadManager(s, Env(), History())
    assert m2.load_queue() == 1 and m2.jobs[0].title == "Um vídeo" and m2.jobs[0].status == "paused"
    j = m2.jobs[0]
    j.filepath, j.total = "/x/a.mp4", 10
    h.add(j)
    assert History().items[0]["format"] == "MP4 · melhor"
    data = json.load(open(m.queue_path))
    assert data[0]["url"] == "https://example.com/v"
