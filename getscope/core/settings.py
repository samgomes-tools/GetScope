"""Configurações persistentes (JSON em ~/.config/getscope)."""
import json
import os

from . import paths

DEFAULTS = {
    "download_dir": "",
    "max_concurrent": 2,
    "rate_limit_kb": 0,
    "name_template": "title",
    "playlist_subfolder": True,
    "mode": "video",
    "quality": "best",
    "container": "mp4",
    "audio_format": "mp3",
    "audio_quality": "192",
    "embed_thumbnail": True,
    "embed_metadata": True,
    "subtitles": False,
    "subtitle_langs": "pt,en",
    "cookies_browser": "",
    "check_engine_on_start": True,
    "notify_done": True,
    "paste_action": "ask",
}

NAME_TEMPLATES = {
    "title": ("Título", "%(title).180B.%(ext)s"),
    "title_id": ("Título [ID]", "%(title).160B [%(id)s].%(ext)s"),
    "channel_title": ("Canal - Título", "%(uploader,channel|Desconhecido).60B - %(title).150B.%(ext)s"),
    "date_title": ("Data - Título", "%(upload_date>%Y-%m-%d|0000-00-00)s - %(title).160B.%(ext)s"),
}

COOKIE_BROWSERS = [("", "Não usar"), ("firefox", "Firefox"), ("chrome", "Google Chrome"),
                   ("chromium", "Chromium"), ("brave", "Brave"), ("edge", "Microsoft Edge"),
                   ("opera", "Opera"), ("vivaldi", "Vivaldi")]


class Settings:
    def __init__(self, path=None):
        self.path = path or os.path.join(paths.config_dir(), "settings.json")
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                self.data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
        if not self.data["download_dir"]:
            self.data["download_dir"] = paths.default_download_dir()

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def update(self, values):
        self.data.update({k: v for k, v in values.items() if k in DEFAULTS})
        self.save()

    def reset(self):
        self.data = dict(DEFAULTS)
        self.data["download_dir"] = paths.default_download_dir()
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
