"""Fila de downloads, histórico e workers (threads) que chamam o yt-dlp."""
import json
import os
import re
import threading
import time
import uuid

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from . import deps, engine, formats, paths

ACTIVE = ("downloading", "processing", "starting")
STATUS_TEXT = {
    "queued": "Na fila", "starting": "Iniciando", "downloading": "Baixando", "processing": "Processando",
    "paused": "Pausado", "done": "Concluído", "error": "Erro", "canceled": "Cancelado",
}
PP_TEXT = {
    "Merger": "Juntando vídeo e áudio", "ExtractAudio": "Convertendo áudio", "EmbedThumbnail": "Embutindo capa",
    "Metadata": "Gravando metadados", "EmbedSubtitle": "Embutindo legendas", "ThumbnailsConvertor": "Preparando capa",
    "VideoConvertor": "Convertendo vídeo", "VideoRemuxer": "Ajustando contêiner", "FixupM3u8": "Corrigindo arquivo",
    "FixupM4a": "Corrigindo arquivo", "FixupStretched": "Corrigindo arquivo", "FixupDuplicateMoov": "Corrigindo arquivo",
    "MoveFiles": "Finalizando",
}

_STREAM = re.compile(r"\.f(?:[0-9][\w-]*|(?:hls|dash|http)[\w-]*)\.\w+$")
_FIELDS = ("id", "url", "title", "site", "uploader", "duration", "thumb_url", "choice", "subdir", "outdir", "status",
           "progress", "total", "downloaded", "filepath", "error", "error_hint", "created", "finished")


class Job:
    def __init__(self, url, choice, title=None, **kw):
        self.id = kw.get("id") or uuid.uuid4().hex[:12]
        self.url = url
        self.title = title or url
        self.site = kw.get("site") or ""
        self.uploader = kw.get("uploader") or ""
        self.duration = kw.get("duration")
        self.thumb_url = kw.get("thumb_url")
        self.choice = dict(choice)
        self.subdir = kw.get("subdir") or ""
        self.outdir = kw.get("outdir") or ""
        self.status = kw.get("status") or "queued"
        self.progress = float(kw.get("progress") or 0)
        self.total = kw.get("total")
        self.downloaded = kw.get("downloaded")
        self.filepath = kw.get("filepath")
        self.error = kw.get("error")
        self.error_hint = kw.get("error_hint")
        self.created = kw.get("created") or time.time()
        self.finished = kw.get("finished")
        self.speed = None
        self.eta = None
        self.stage = ""
        self.log = []
        self.tmpfiles = set()
        self.stop = None  # None | "pause" | "cancel"

    def to_dict(self):
        return {k: getattr(self, k) for k in _FIELDS}

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        return cls(d.pop("url"), d.pop("choice", {}), d.pop("title", None), **d)

    @property
    def status_text(self):
        if self.status == "processing" and self.stage:
            return self.stage
        if self.status == "downloading" and self.stage:
            return self.stage
        return STATUS_TEXT.get(self.status, self.status)


class _Stop(Exception):
    pass


def _stop_exc():
    """Exceção que o yt-dlp reconhece como interrupção pedida pelo usuário."""
    try:
        from yt_dlp.utils import DownloadCancelled

        class StopRequested(DownloadCancelled):
            msg = "Interrompido pelo usuário"
        return StopRequested
    except Exception:
        return _Stop


class _Logger:
    def __init__(self, sink):
        self.sink = sink

    def debug(self, msg):
        if msg.startswith("[debug]"):
            return
        self.sink("info", msg)

    def info(self, msg):
        self.sink("info", msg)

    def warning(self, msg):
        self.sink("warning", msg)

    def error(self, msg):
        self.sink("error", msg)


class Env:
    """Dependências detectadas, compartilhadas pelos workers."""

    def __init__(self):
        self.refresh()

    def refresh(self):
        self.ffmpeg = deps.ffmpeg()
        self.js = deps.js_runtimes()
        self.distro = deps.distro()

    @property
    def js_param(self):
        return deps.ytdlp_js_param(self.js) or None


class WorkerSignals(QObject):
    update = Signal(str, dict)
    finished = Signal(str, str, dict)  # id, status, extras
    log = Signal(str, str, str)  # id, level, msg


class DownloadWorker(QRunnable):
    def __init__(self, job, settings, env):
        super().__init__()
        self.job = job
        self.settings = settings
        self.env = env
        self.sig = WorkerSignals()
        self.setAutoDelete(True)
        self._last_emit = 0
        self._streams = 1
        self._stream_files = []

    def _sink(self, level, msg):
        if level == "info" and not msg.startswith(("[download] Destination", "[Merger]", "[ExtractAudio]")):
            return
        self.sig.log.emit(self.job.id, level, msg)

    def _hook(self, d):
        job = self.job
        if job.stop:
            raise self.Stop()
        for fn in (d.get("tmpfilename"), d.get("filename")):
            if fn:
                job.tmpfiles.add(fn)
        base = d.get("filename")
        if base and base not in self._stream_files:
            self._stream_files.append(base)
        st = d.get("status")
        if st == "downloading":
            now = time.monotonic()
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            frac = (done / total) if total else 0.0
            idx = max(0, len(self._stream_files) - 1)
            n = max(self._streams, idx + 1)
            overall = min(99.9, (idx + frac) / n * 100)
            if now - self._last_emit < 0.25:
                return
            self._last_emit = now
            info = d.get("info_dict") or {}
            if n > 1:
                kind = "áudio" if info.get("vcodec") == "none" else "vídeo"
                stage = f"Baixando {kind} ({idx + 1}/{n})"
            else:
                stage = "Baixando"
            self.sig.update.emit(job.id, {"status": "downloading", "progress": overall, "speed": d.get("speed"),
                                          "eta": d.get("eta"), "downloaded": done, "total": total, "stage": stage})
        elif st == "finished":
            pass

    def _pp_hook(self, d):
        if self.job.stop == "cancel":
            raise self.Stop()
        if d.get("status") == "started":
            name = d.get("postprocessor", "")
            text = next((v for k, v in PP_TEXT.items() if k in name), "Processando")
            self.sig.update.emit(self.job.id, {"status": "processing", "stage": text, "progress": 100,
                                               "speed": None, "eta": None})

    @Slot()
    def run(self):
        job = self.job
        self.Stop = _stop_exc()
        outdir = job.outdir or self.settings["download_dir"]
        if job.subdir:
            outdir = os.path.join(outdir, job.subdir)
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as e:
            msg, hint, raw = formats.friendly_error(str(e))
            self.sig.finished.emit(job.id, "error", {"error": msg, "error_hint": hint, "raw": raw})
            return
        ff = self.env.ffmpeg
        opts = formats.build_opts(job.choice, self.settings, outdir, bool(ff), self.env.js_param,
                                  ff["path"] if ff and ff["path"].startswith(paths.data_dir()) else None)
        opts["logger"] = _Logger(self._sink)
        opts["progress_hooks"] = [self._hook]
        opts["postprocessor_hooks"] = [self._pp_hook]
        self.sig.update.emit(job.id, {"status": "starting", "stage": "Iniciando", "error": None,
                                      "error_hint": None})
        try:
            yt = engine.ytdlp()
            with yt.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(job.url, download=False)
                if info is None:
                    raise RuntimeError("O site não retornou informações do vídeo.")
                if info.get("_type") in ("playlist", "multi_video") and info.get("entries"):
                    entries = [e for e in info["entries"] if e]
                    info = ydl.process_ie_result(entries[0], download=False) if entries else info
                self._streams = len(info.get("requested_formats") or []) or 1
                meta = {"title": info.get("title") or job.title, "site": info.get("extractor_key") or job.site,
                        "uploader": info.get("uploader") or info.get("channel") or job.uploader,
                        "duration": info.get("duration") or job.duration}
                if not job.thumb_url:
                    meta["thumb_url"] = formats.best_thumbnail(info)
                self.sig.update.emit(job.id, meta)
                if job.stop:
                    raise self.Stop()
                info = ydl.process_info(info) or info
            path = None
            for rd in info.get("requested_downloads") or []:
                path = rd.get("filepath") or path
            path = path or info.get("filepath") or info.get("_filename")
            size = None
            if path and os.path.exists(path):
                size = os.path.getsize(path)
            self.sig.finished.emit(job.id, "done", {"filepath": path, "total": size, "downloaded": size})
        except Exception as e:  # noqa: BLE001 - qualquer falha do yt-dlp vira status de erro
            if job.stop or isinstance(e, self.Stop) or "Interrompido pelo usuário" in str(e):
                self.sig.finished.emit(job.id, "canceled" if job.stop == "cancel" else "paused", {})
                return
            msg, hint, raw = formats.friendly_error(str(e))
            self.sig.finished.emit(job.id, "error", {"error": msg, "error_hint": hint, "raw": raw})


class History:
    def __init__(self, path=None):
        self.path = path or os.path.join(paths.data_dir(), "history.json")
        self.items = []
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.items = data
        except (OSError, ValueError):
            pass

    def add(self, job):
        self.items.insert(0, {"id": job.id, "title": job.title, "url": job.url, "site": job.site,
                              "uploader": job.uploader, "format": formats.describe(job.choice),
                              "choice": job.choice, "filepath": job.filepath, "size": job.total,
                              "date": job.finished or time.time(), "thumb_url": job.thumb_url,
                              "duration": job.duration})
        del self.items[2000:]
        self.save()

    def remove(self, ids):
        ids = set(ids)
        self.items = [x for x in self.items if x.get("id") not in ids]
        self.save()

    def clear(self):
        self.items = []
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False)
        os.replace(tmp, self.path)


def safe_folder(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name or "").strip(" .")
    return name[:120] or "Playlist"


class DownloadManager(QObject):
    job_added = Signal(object)
    job_changed = Signal(str)
    job_removed = Signal(str)
    job_finished = Signal(object)
    log = Signal(str, str)  # level, msg

    def __init__(self, settings, env, history, queue_path=None):
        super().__init__()
        self.settings = settings
        self.env = env
        self.history = history
        self.jobs = []
        self.by_id = {}
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(5)
        self.queue_path = queue_path or os.path.join(paths.data_dir(), "queue.json")
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save_queue)
        self._lock = threading.Lock()

    # ------------------------------------------------------------ fila
    def load_queue(self):
        try:
            with open(self.queue_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return 0
        n = 0
        for d in data if isinstance(data, list) else []:
            try:
                j = Job.from_dict(d)
            except (KeyError, TypeError):
                continue
            if j.status in ACTIVE or j.status == "queued":
                j.status = "paused"
            self._add(j)
            n += 1
        return n

    def save_queue(self):
        keep = [j.to_dict() for j in self.jobs if j.status not in ("done", "canceled")]
        tmp = self.queue_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(keep, f, ensure_ascii=False)
            os.replace(tmp, self.queue_path)
        except OSError:
            pass

    def _touch(self):
        self._save_timer.start()

    def _add(self, job):
        self.jobs.append(job)
        self.by_id[job.id] = job
        self.job_added.emit(job)

    def add(self, url, choice, title=None, start=True, **kw):
        job = Job(url, choice, title, **kw)
        if not start:
            job.status = "paused"
        self._add(job)
        self._touch()
        self.schedule()
        return job

    def running(self):
        return [j for j in self.jobs if j.status in ACTIVE]

    def schedule(self):
        limit = max(1, int(self.settings["max_concurrent"]))
        for job in self.jobs:
            if len(self.running()) >= limit:
                break
            if job.status == "queued":
                job.status = "starting"
                job.stop = None
                job.stage = "Iniciando"
                self.job_changed.emit(job.id)
                w = DownloadWorker(job, self.settings, self.env)
                w.sig.update.connect(self._on_update)
                w.sig.finished.connect(self._on_finished)
                w.sig.log.connect(self._on_log)
                self.pool.start(w)

    # ------------------------------------------------------------ ações
    def pause(self, jid):
        j = self.by_id.get(jid)
        if not j:
            return
        if j.status in ACTIVE:
            j.stop = "pause"
            j.stage = "Pausando…"
        elif j.status == "queued":
            j.status = "paused"
        self.job_changed.emit(jid)
        self._touch()

    def resume(self, jid):
        j = self.by_id.get(jid)
        if j and j.status in ("paused", "error", "canceled"):
            j.status = "queued"
            j.error = j.error_hint = None
            j.stage = ""
            self.job_changed.emit(jid)
            self._touch()
            self.schedule()

    def cancel(self, jid):
        j = self.by_id.get(jid)
        if not j:
            return
        if j.status in ACTIVE:
            j.stop = "cancel"
            j.stage = "Cancelando…"
            self.job_changed.emit(jid)
        elif j.status not in ("done", "canceled"):
            j.status = "canceled"
            self._cleanup(j)
            self.job_changed.emit(jid)
        self._touch()

    def remove(self, jid):
        j = self.by_id.get(jid)
        if not j:
            return
        if j.status in ACTIVE:
            j.stop = "cancel"
            j._remove_after = True
            return
        if j.status not in ("done",):
            self._cleanup(j)
        self.jobs.remove(j)
        del self.by_id[jid]
        self.job_removed.emit(jid)
        self._touch()

    def pause_all(self):
        for j in list(self.jobs):
            if j.status in ACTIVE or j.status == "queued":
                self.pause(j.id)

    def resume_all(self):
        for j in list(self.jobs):
            if j.status == "paused":
                j.status = "queued"
                self.job_changed.emit(j.id)
        self._touch()
        self.schedule()

    def clear_finished(self):
        for j in [j for j in self.jobs if j.status in ("done", "canceled")]:
            self.remove(j.id)

    @staticmethod
    def _cleanup(j):
        """Apaga só arquivos temporários (.part, .ytdl, fragmentos e trilhas .fNNN antes da junção)."""
        import glob
        cands = set()
        for f in list(j.tmpfiles):
            base = f[:-5] if f.endswith(".part") else f
            cands.update({f, base + ".part", base + ".ytdl", base + ".part.ytdl"})
            cands.update(glob.glob(glob.escape(base) + ".part-Frag*"))
            if _STREAM.search(os.path.basename(base)):
                cands.add(base)
        for c in cands:
            name = os.path.basename(c)
            if not (c.endswith((".part", ".ytdl")) or ".part-Frag" in name or _STREAM.search(name)):
                continue
            try:
                if os.path.isfile(c):
                    os.unlink(c)
            except OSError:
                pass
        j.tmpfiles.clear()

    # ------------------------------------------------------------ sinais dos workers
    def _on_update(self, jid, data):
        j = self.by_id.get(jid)
        if not j:
            return
        if j.stop and data.get("status") in ACTIVE:
            data = {k: v for k, v in data.items() if k not in ("status", "stage")}
        for k, v in data.items():
            setattr(j, k, v)
        self.job_changed.emit(jid)

    def _on_log(self, jid, level, msg):
        j = self.by_id.get(jid)
        if j is not None:
            j.log.append((level, msg))
            del j.log[:-200]
        if level != "info":
            title = j.title if j else jid
            self.log.emit(level, f"{title}: {msg}")

    def _on_finished(self, jid, status, extra):
        j = self.by_id.get(jid)
        if not j:
            return
        remove_after = getattr(j, "_remove_after", False)
        j.status = status
        j.speed = j.eta = None
        j.stage = ""
        raw = extra.pop("raw", None)
        for k, v in extra.items():
            setattr(j, k, v)
        if status == "done":
            j.progress = 100
            j.finished = time.time()
            j.tmpfiles.clear()
            self.history.add(j)
            self.job_finished.emit(j)
        elif status == "canceled":
            j.progress = 0
            self._cleanup(j)
        elif status == "error":
            self.log.emit("error", f"{j.title}: {raw or j.error}")
            self.job_finished.emit(j)
        j.stop = None
        self.job_changed.emit(jid)
        if remove_after:
            j._remove_after = False
            self.remove(jid)
        self._touch()
        self.schedule()


# ---------------------------------------------------------------- análise de links

class AnalyzeSignals(QObject):
    done = Signal(dict)
    failed = Signal(str, str, str)


class AnalyzeWorker(QRunnable):
    def __init__(self, url, settings, env):
        super().__init__()
        self.url = url
        self.settings = settings
        self.env = env
        self.sig = AnalyzeSignals()

    @Slot()
    def run(self):
        try:
            yt = engine.ytdlp()
            opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist",
                    "noplaylist": False, "logger": _Logger(lambda *a: None), "lazy_playlist": False,
                    "playlistend": 1000}
            if self.env.js_param:
                opts["js_runtimes"] = self.env.js_param
            if self.settings.get("cookies_browser"):
                opts["cookiesfrombrowser"] = (self.settings["cookies_browser"],)
            with yt.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False, process=True)
                info = ydl.sanitize_info(info)
            if info is None:
                raise RuntimeError("O site não retornou informações.")
            self.sig.done.emit(info)
        except Exception as e:  # noqa: BLE001
            msg, hint, raw = formats.friendly_error(str(e))
            self.sig.failed.emit(msg, hint or "", raw)


class FetchSignals(QObject):
    done = Signal(str, bytes)


class FetchWorker(QRunnable):
    """Baixa miniaturas sem travar a interface."""

    def __init__(self, url, key=None):
        super().__init__()
        self.url = url
        self.key = key or url
        self.sig = FetchSignals()

    @Slot()
    def run(self):
        from . import net
        try:
            with net.urlopen(self.url, timeout=15) as r:
                data = r.read(4 * 1024 * 1024)
            self.sig.done.emit(self.key, data)
        except Exception:  # noqa: BLE001
            self.sig.done.emit(self.key, b"")
