import logging
import re
import unicodedata
from typing import Optional

import whisper

log = logging.getLogger(__name__)

_model_cache: dict[str, whisper.Whisper] = {}


def _load_model(model_name: str) -> whisper.Whisper:
    if model_name not in _model_cache:
        log.info("Carregando modelo Whisper '%s'…", model_name)
        _model_cache[model_name] = whisper.load_model(model_name)
    return _model_cache[model_name]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def find_phrase_timestamp(
    video_path: str,
    phrase: str,
    model_name: str = "small",
    language: str = "pt",
) -> Optional[float]:
    model = _load_model(model_name)
    lang = None if language == "auto" else language

    log.info("Transcrevendo '%s'…", video_path)
    result = model.transcribe(
        video_path,
        word_timestamps=True,
        language=lang,
        verbose=False,
    )

    needle = _normalize(phrase)
    needle_words = needle.split()
    n = len(needle_words)

    # ── busca palavra-a-palavra nos segmentos ────────────────────────────────
    for segment in result.get("segments", []):
        words = segment.get("words", [])
        if len(words) < n:
            continue
        normalized_words = [_normalize(w["word"]) for w in words]
        for i in range(len(normalized_words) - n + 1):
            window = normalized_words[i : i + n]
            if window == needle_words:
                ts = words[i]["start"]
                log.info("Frase encontrada em %.2fs (via palavras).", ts)
                return ts

    # ── fallback: busca no texto de cada segmento ────────────────────────────
    for segment in result.get("segments", []):
        if needle in _normalize(segment.get("text", "")):
            ts = segment["start"]
            log.info("Frase encontrada em %.2fs (via segmento).", ts)
            return ts

    log.warning("Frase '%s' não encontrada no vídeo.", phrase)
    return None
