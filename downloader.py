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

    playlist_end = max_videos if max_videos > 0 else None

    ydl_opts = {
        "format": video_format,
        "outtmpl": str(output_dir / "%(upload_date)s_%(id)s.%(ext)s"),
        "dateafter": date_after,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "playlist_end": playlist_end,
    }

    log.info("Buscando vídeos em: %s (após %s)", channel_url, date_after)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False)
        except Exception as exc:
            log.error("Falha ao acessar canal: %s", exc)
            return []

        if not info:
            return []

        entries = info.get("entries", [info])

        for entry in entries:
            if not entry:
                continue
            video_id = entry.get("id", "")
            if video_id in already_downloaded:
                log.debug("Já baixado, pulando: %s", video_id)
                continue
            try:
                ydl.download([entry.get("webpage_url") or entry.get("url", "")])
            except Exception as exc:
                log.warning("Erro ao baixar %s: %s", video_id, exc)

    _save_state(state_file, already_downloaded | newly_downloaded)
    log.info("%d novo(s) vídeo(s) baixado(s).", len(downloaded_files))
    return downloaded_files
