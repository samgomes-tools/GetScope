"""Escolha de formato → opções do yt-dlp, resumo das informações e mensagens de erro."""
import os
import re

from .settings import NAME_TEMPLATES

HEIGHTS = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144]
CONTAINERS = ["mp4", "mkv", "webm"]
AUDIO_FORMATS = [("mp3", "MP3"), ("m4a", "M4A (AAC)"), ("opus", "OPUS"), ("flac", "FLAC (sem perdas)"),
                 ("wav", "WAV (sem compressão)")]
AUDIO_QUALITIES = [("0", "Melhor"), ("320", "320 kbps"), ("256", "256 kbps"), ("192", "192 kbps"),
                   ("128", "128 kbps")]


def height_label(h):
    return {4320: "8K", 2160: "4K", 1440: "2K"}.get(h, "")


def choice_from_settings(s):
    return {k: s[k] for k in ("mode", "quality", "container", "audio_format", "audio_quality",
                              "embed_thumbnail", "embed_metadata", "subtitles", "subtitle_langs")}


def describe(choice):
    """Texto curto do formato para a lista ("MP4 · 1080p", "MP3 · 192 kbps")."""
    if choice.get("mode") == "audio":
        q = choice.get("audio_quality", "0")
        fmt = choice.get("audio_format", "mp3").upper()
        if fmt in ("FLAC", "WAV"):
            return fmt
        return f"{fmt} · {'melhor' if q == '0' else q + ' kbps'}"
    q = choice.get("quality", "best")
    return f"{choice.get('container', 'mp4').upper()} · {'melhor' if q == 'best' else str(q) + 'p'}"


def build_opts(choice, settings, outdir, has_ffmpeg, js=None, ffmpeg_path=None):
    """Monta o dicionário de opções do yt-dlp para um download."""
    tmpl = NAME_TEMPLATES.get(settings.get("name_template"), NAME_TEMPLATES["title"])[1]
    o = {
        "outtmpl": {"default": os.path.join(outdir, tmpl)},
        "noplaylist": True,
        "continuedl": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "overwrites": False,
        "color": {"stdout": "never", "stderr": "never"},
    }
    if js:
        o["js_runtimes"] = js
    if ffmpeg_path:
        o["ffmpeg_location"] = os.path.dirname(ffmpeg_path)
    rl = int(settings.get("rate_limit_kb") or 0)
    if rl > 0:
        o["ratelimit"] = rl * 1024
    br = settings.get("cookies_browser")
    if br:
        o["cookiesfrombrowser"] = (br,)

    pps = []
    audio = choice.get("mode") == "audio"
    if audio:
        if has_ffmpeg:
            o["format"] = "ba/b"
            pps.append({"key": "FFmpegExtractAudio", "preferredcodec": choice.get("audio_format", "mp3"),
                        "preferredquality": choice.get("audio_quality", "0"), "nopostoverwrites": False})
        else:
            o["format"] = "ba[ext=m4a]/ba/b"
    else:
        q = choice.get("quality", "best")
        cont = choice.get("container", "mp4")
        if has_ffmpeg:
            o["format"] = "bv*+ba/b"
            sort = []
            if q != "best":
                sort.append(f"res:{int(q)}")
            if cont == "mp4":
                sort += ["vcodec:h264", "ext:mp4:m4a"] if q != "best" and int(q) <= 1080 else ["ext:mp4:m4a"]
            elif cont == "webm":
                sort.append("ext:webm:webm")
            o["format_sort"] = sort
            o["merge_output_format"] = cont
            if cont == "mkv":
                # sites que entregam arquivo único (mp4) também viram MKV
                pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": "mkv"})
        else:
            o["format"] = "b" if q == "best" else f"b[height<={int(q)}]/b"
    if choice.get("subtitles"):
        langs = [x.strip() for x in str(choice.get("subtitle_langs", "")).split(",") if x.strip()]
        o["writesubtitles"] = True
        o["writeautomaticsub"] = False
        o["subtitleslangs"] = [f"{l}.*" if "." not in l and "*" not in l else l for l in langs] or ["all"]
        if has_ffmpeg and not audio:
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
    if has_ffmpeg and choice.get("embed_metadata"):
        pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": not audio,
                    "add_infojson": False})
    thumb_ok = audio and choice.get("audio_format") in ("mp3", "m4a", "opus", "flac") or (
        not audio and choice.get("container") in ("mp4", "mkv"))
    if has_ffmpeg and choice.get("embed_thumbnail") and thumb_ok:
        o["writethumbnail"] = True
        pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    o["postprocessors"] = pps
    return o


def best_thumbnail(info):
    thumbs = [t for t in (info.get("thumbnails") or []) if t.get("url")]
    jpgs = [t for t in thumbs if re.search(r"\.(jpe?g|png)(\?|$)", t["url"])]
    pool = jpgs or thumbs
    if pool:
        def score(t):
            return ((t.get("width") or 0) * (t.get("height") or 0), t.get("preference") or 0)
        good = [t for t in pool if (t.get("width") or 0) <= 1280] or pool
        return max(good, key=score)["url"]
    return info.get("thumbnail")


def video_heights(info):
    """Alturas disponíveis com o tamanho aproximado (vídeo + melhor áudio)."""
    fmts = info.get("formats") or []
    audio = [f for f in fmts if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    asize = max((f.get("filesize") or f.get("filesize_approx") or 0 for f in audio), default=0)
    by_h = {}
    for f in fmts:
        h = f.get("height")
        if not h or f.get("vcodec") == "none":
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        if f.get("acodec") in (None, "none") and size:
            size += asize
        hh = min(HEIGHTS, key=lambda x: abs(x - h)) if h not in HEIGHTS else h
        by_h[hh] = max(by_h.get(hh, 0), size)
    return sorted(by_h.items(), reverse=True)


def human_size(n):
    if not n:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return (f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}").replace(".", ",")
        n /= 1024
    return "—"


def human_time(sec):
    if sec is None:
        return "—"
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


ERRORS = [
    (r"confirm you.?re not a bot|Sign in to confirm",
     "O YouTube pediu para confirmar que você não é um robô.",
     "Em Configurações › Acesso, escolha o navegador em que você está logado no YouTube para usar os cookies dele, e tente de novo."),
    (r"Private video", "Este vídeo é privado.", "Só é possível baixar se você tiver acesso e usar os cookies do navegador logado."),
    (r"age.?restrict|confirm your age|inappropriate for some users",
     "Vídeo com restrição de idade.", "Use os cookies do navegador logado (Configurações › Acesso)."),
    (r"members.?only|Join this channel", "Conteúdo exclusivo para membros do canal.",
     "Só funciona com os cookies de uma conta que seja membro."),
    (r"Video unavailable|This video is not available|has been removed",
     "Vídeo indisponível ou removido.", None),
    (r"Unsupported URL", "Este link não é suportado.", "Confira se o endereço está completo e é de uma página de vídeo."),
    (r"is not a valid URL|No such file", "O texto colado não é um link válido.", None),
    (r"Requested format is not available", "A qualidade escolhida não está disponível para este vídeo.",
     "Tente “Melhor disponível” ou outra qualidade."),
    (r"ffmpeg|ffprobe", "O FFmpeg é necessário para este download.", "Instale pela aba Diagnóstico."),
    (r"JavaScript runtime|n challenge|Signature solving failed",
     "Falta um runtime JavaScript para o YouTube.", "Na aba Diagnóstico, clique em “Baixar Deno”."),
    (r"HTTP Error 403", "O site recusou o download (erro 403).",
     "Atualize o motor na aba Diagnóstico; se continuar, use os cookies do navegador."),
    (r"HTTP Error 429|Too Many Requests", "Muitas requisições em pouco tempo (erro 429).",
     "Espere alguns minutos ou use os cookies do navegador."),
    (r"Unable to download webpage|getaddrinfo|Network is unreachable|timed out|Connection reset",
     "Falha de conexão com o site.", "Confira a internet e tente novamente."),
    (r"No space left", "Sem espaço no disco.", "Libere espaço ou escolha outra pasta."),
    (r"Permission denied", "Sem permissão para gravar na pasta escolhida.", "Escolha outra pasta em Configurações."),
    (r"could not find .* cookies|cookies database|Failed to decrypt",
     "Não foi possível ler os cookies do navegador escolhido.", "Feche o navegador e tente de novo, ou escolha outro."),
]


def friendly_error(raw):
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(raw or "")).strip()
    text = re.sub(r"^ERROR:\s*", "", text)
    for pat, msg, hint in ERRORS:
        if re.search(pat, text, re.I):
            return msg, hint, text
    short = text.splitlines()[0] if text else "Erro desconhecido."
    return short[:300], None, text
