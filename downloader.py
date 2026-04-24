import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yt_dlp

log = logging.getLogger(__name__)


def _load_state(state_file: str) -> set:
    path = Path(state_file)
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def _save_state(state_file: str, downloaded: set) -> None:
    Path(state_file).write_text(json.dumps(sorted(downloaded)))


def download_new_videos(
    channel_url: str,
    days_back: int,
    output_dir: str,
    state_file: str,
    video_format: str,
    max_videos: int = 0,
    cookies_from_browser: str = "",
    cookies_file: str = "",
) -> list[str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)

    already_downloaded = _load_state(state_file)
    date_after = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

    downloaded_files: list[str] = []
    newly_downloaded: set[str] = set()

    def progress_hook(d):
        if d["status"] == "finished":
            video_id = d.get("info_dict", {}).get("id", "")
            filepath = d.get("filename") or d.get("info_dict", {}).get("_filename", "")
            if filepath and video_id not in already_downloaded:
                downloaded_files.append(filepath)
                newly_downloaded.add(video_id)
                log.info("Baixado: %s", Path(filepath).name)

    # Limita metadados: busca apenas os N vídeos mais recentes do canal
    # (canais grandes têm milhares de vídeos — não precisamos varrer todos)
    playlist_items = max_videos if max_videos > 0 else 20

    ydl_opts = {
        "format": video_format,
        "outtmpl": str(output_dir / "%(upload_date)s_%(id)s.%(ext)s"),
        "dateafter": date_after,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        # Pega apenas os N vídeos mais recentes (evita varrer 12 mil vídeos)
        "playlist_end": playlist_items,
    }

    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)
        log.info("Usando cookies do navegador: %s", cookies_from_browser)
    elif cookies_file and Path(cookies_file).exists():
        ydl_opts["cookiefile"] = cookies_file
        log.info("Usando arquivo de cookies: %s", cookies_file)

    log.info("Buscando os %d vídeos mais recentes em: %s (após %s)",
             playlist_items, channel_url, date_after)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=True)
        except Exception as exc:
            log.error("Falha ao acessar canal: %s", exc)
            return []

        if not info:
            return []

        # Coleta arquivos baixados a partir das entries
        entries = info.get("entries", [info]) if isinstance(info, dict) else []
        for entry in entries:
            if not entry:
                continue
            video_id = entry.get("id", "")
            if not video_id or video_id in already_downloaded:
                continue
            # O progress_hook já captura o filepath; aqui só registramos o id
            newly_downloaded.add(video_id)

    _save_state(state_file, already_downloaded | newly_downloaded)
    log.info("%d novo(s) vídeo(s) baixado(s).", len(downloaded_files))
    return downloaded_files
