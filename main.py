#!/usr/bin/env python3
"""
Uso:
    python main.py                # executa uma vez agora
    python main.py --schedule     # roda no horário definido em config.yaml, todo dia
    python main.py --config outro.yaml
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import schedule
import time
import yaml

from downloader import download_new_videos
from transcriber import find_phrase_timestamp
from processor import cut_from_timestamp, concatenate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/run.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(config: dict) -> None:
    today = datetime.now().strftime("%Y%m%d")
    log.info("═" * 60)
    log.info("Execução iniciada — %s", today)
    log.info("Canal: %s", config["channel_url"])
    log.info("Frase de corte: '%s'", config["start_phrase"])

    # 1 ── Download ────────────────────────────────────────────────────────────
    videos = download_new_videos(
        channel_url=config["channel_url"],
        days_back=int(config.get("days_back", 1)),
        output_dir=config["downloads_dir"],
        state_file=config["state_file"],
        video_format=config["video_format"],
        max_videos=int(config.get("max_videos", 0)),
    )

    if not videos:
        log.info("Nenhum vídeo novo encontrado. Encerrando.")
        return

    # 2 ── Transcrever e cortar ────────────────────────────────────────────────
    clips: list[str] = []
    for video in videos:
        timestamp = find_phrase_timestamp(
            video_path=video,
            phrase=config["start_phrase"],
            model_name=config.get("whisper_model", "small"),
            language=config.get("language", "pt"),
        )
        if timestamp is None:
            log.warning("Frase não localizada em '%s'. Vídeo ignorado.", Path(video).name)
            continue

        clip = cut_from_timestamp(video, timestamp, config["clips_dir"])
        clips.append(clip)

    if not clips:
        log.warning("Nenhum clip gerado. Verifique se a frase está correta.")
        return

    # 3 ── Concatenar ──────────────────────────────────────────────────────────
    filename = config.get("final_filename", "compilado_{date}.mp4").replace("{date}", today)
    final_path = str(Path(config["final_dir"]) / filename)
    result = concatenate(clips, final_path)

    log.info("✓ Concluído! Arquivo final: %s", result)
    log.info("═" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Daily Clipper")
    parser.add_argument("--config", default="config.yaml", help="Caminho para config.yaml")
    parser.add_argument("--schedule", action="store_true", help="Executa como agendador diário")
    args = parser.parse_args()

    config = load_config(args.config)
    Path("output").mkdir(exist_ok=True)

    if not args.schedule:
        run(config)
        return

    run_at = config.get("run_at", "06:00")
    log.info("Agendador ativo — executa todos os dias às %s.", run_at)
    schedule.every().day.at(run_at).do(run, config=config)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
