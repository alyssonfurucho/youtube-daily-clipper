import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _ffmpeg(*args: str) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou:\n{result.stderr}")


def cut_from_timestamp(input_path: str, timestamp: float, output_dir: str) -> str:
    """Corta o vídeo a partir do timestamp dado (re-codifica para evitar artefatos)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(input_path).stem
    output_path = output_dir / f"clip_{stem}.mp4"

    log.info("Cortando '%s' a partir de %.2fs…", Path(input_path).name, timestamp)
    _ffmpeg(
        "-ss", str(timestamp),
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output_path),
    )
    log.info("Clip salvo: %s", output_path.name)
    return str(output_path)


def concatenate(video_paths: list[str], output_path: str) -> str:
    """Concatena uma lista de vídeos MP4 em um único arquivo final."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    list_file = output_path.parent / "_concat_list.txt"
    lines = [f"file '{Path(p).resolve()}'" for p in video_paths]
    list_file.write_text("\n".join(lines))

    log.info("Concatenando %d clip(s) → %s…", len(video_paths), output_path.name)
    try:
        _ffmpeg(
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        )
    finally:
        list_file.unlink(missing_ok=True)

    log.info("Arquivo final: %s", output_path)
    return str(output_path)
