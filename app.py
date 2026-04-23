#!/usr/bin/env python3
"""
Interface web — inicie com:
    streamlit run app.py

Deploy: Streamlit Community Cloud → share.streamlit.io
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
import yaml

# ── detecta ambiente (local vs Streamlit Cloud) ───────────────────────────────
IS_CLOUD = os.environ.get("STREAMLIT_SHARING_MODE") == "streamlit_sharing" or \
           "HOSTNAME" in os.environ and "streamlit" in os.environ.get("HOSTNAME", "")

# Na nuvem usa /tmp (único diretório gravável); localmente usa ./output
BASE_DIR = Path("/tmp/yt-clipper") if IS_CLOUD else Path("output")
BASE_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "downloads").mkdir(exist_ok=True)
(BASE_DIR / "clips").mkdir(exist_ok=True)
(BASE_DIR / "final").mkdir(exist_ok=True)

CONFIG_PATH = Path("config.yaml")
LOG_PATH = BASE_DIR / "run.log"

# ── helpers ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # sobrescreve paths para o ambiente atual
    cfg["downloads_dir"] = str(BASE_DIR / "downloads")
    cfg["clips_dir"] = str(BASE_DIR / "clips")
    cfg["final_dir"] = str(BASE_DIR / "final")
    cfg["state_file"] = str(BASE_DIR / ".downloaded.json")
    return cfg


def save_config(config: dict) -> None:
    on_disk = {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        on_disk = yaml.safe_load(f)
    on_disk.update({
        k: config[k]
        for k in ("channel_url", "start_phrase", "language",
                  "whisper_model", "days_back", "run_at", "max_videos")
        if k in config
    })
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(on_disk, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def list_final_files() -> list[Path]:
    d = BASE_DIR / "final"
    return sorted(d.glob("*.mp4"), reverse=True)


# ── layout ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="YouTube Daily Clipper",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎬 YouTube Daily Clipper")
st.caption("Baixa, corta e concatena vídeos de um canal automaticamente.")

if IS_CLOUD:
    st.info(
        "**Modo nuvem:** os arquivos gerados ficam em memória temporária e são apagados quando "
        "o app for reiniciado. Para armazenamento permanente, rode localmente.",
        icon="☁️",
    )

config = load_config()

# ─── Sidebar — configuração ───────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuração")

    channel_url = st.text_input(
        "URL do Canal",
        value=config.get("channel_url", ""),
        placeholder="https://www.youtube.com/@NomeDoCanal",
    )
    start_phrase = st.text_input(
        "Frase de corte",
        value=config.get("start_phrase", ""),
        placeholder="Ex.: agora vamos ao que interessa",
        help="O vídeo será cortado a partir do momento em que essa frase aparecer.",
    )

    col_l, col_r = st.columns(2)
    with col_l:
        language = st.selectbox(
            "Idioma",
            ["pt", "en", "es", "fr", "auto"],
            index=["pt", "en", "es", "fr", "auto"].index(config.get("language", "pt")),
        )
    with col_r:
        model_options = ["tiny", "base", "small", "medium", "large"]
        whisper_model = st.selectbox(
            "Modelo Whisper",
            model_options,
            index=model_options.index(config.get("whisper_model", "small")),
            help="tiny/base = rápido | small/medium = mais preciso | large = máxima precisão",
        )

    col_d, col_h = st.columns(2)
    with col_d:
        days_back = st.number_input("Dias atrás", min_value=1, max_value=90,
                                    value=int(config.get("days_back", 1)))
    with col_h:
        run_at = st.text_input("Horário diário", value=config.get("run_at", "06:00"),
                               help="Apenas para modo --schedule local.", disabled=IS_CLOUD)

    max_videos = st.number_input(
        "Máx. vídeos por execução", min_value=0, max_value=50,
        value=int(config.get("max_videos", 10)), help="0 = sem limite.",
    )

    if st.button("💾 Salvar configuração", use_container_width=True):
        config.update({
            "channel_url": channel_url,
            "start_phrase": start_phrase,
            "language": language,
            "whisper_model": whisper_model,
            "days_back": int(days_back),
            "run_at": run_at,
            "max_videos": int(max_videos),
        })
        save_config(config)
        st.success("Configuração salva!")

    st.divider()

    if not IS_CLOUD:
        st.markdown("**Modo agendador** (terminal):\n```\npython main.py --schedule\n```")
    else:
        st.markdown(
            "**Execução local com agendador:**\n"
            "```bash\nbash setup.sh\npython main.py --schedule\n```"
        )

# ─── Área principal ───────────────────────────────────────────────────────────
tab_run, tab_files, tab_logs = st.tabs(["▶️ Executar", "📁 Arquivos", "📋 Histórico"])

# ── Tab: Executar ─────────────────────────────────────────────────────────────
with tab_run:
    ready = bool(channel_url.strip()) and bool(start_phrase.strip())

    if not ready:
        st.warning("Preencha a **URL do canal** e a **frase de corte** na barra lateral antes de executar.")

    if IS_CLOUD:
        st.caption(
            "Na nuvem o modelo Whisper é baixado na primeira execução (~150 MB para `base`). "
            "Isso pode levar alguns minutos."
        )

    run_btn = st.button("▶️ Executar agora", type="primary",
                        disabled=not ready, use_container_width=False)

    if run_btn:
        config.update({
            "channel_url": channel_url,
            "start_phrase": start_phrase,
            "language": language,
            "whisper_model": whisper_model,
            "days_back": int(days_back),
            "run_at": run_at,
            "max_videos": int(max_videos),
        })
        save_config(config)

        st.info("Processando… acompanhe os logs abaixo.")
        log_box = st.empty()
        logs: list[str] = []

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).parent),
            env=env,
        )

        for line in proc.stdout:
            line = line.rstrip()
            if line:
                logs.append(line)
                log_box.code("\n".join(logs[-80:]), language=None)

        proc.wait()

        if proc.returncode == 0:
            st.success("✅ Concluído! Veja os arquivos na aba **📁 Arquivos**.")
        else:
            st.error("❌ Erro durante o processamento. Verifique os logs acima.")

# ── Tab: Arquivos gerados ─────────────────────────────────────────────────────
with tab_files:
    st.subheader("Compilados gerados")
    files = list_final_files()

    if not files:
        st.info("Nenhum arquivo gerado ainda. Execute o processamento primeiro.")
    else:
        for f in files[:20]:
            size_mb = f.stat().st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            col_name, col_size, col_dl = st.columns([4, 1, 1])
            col_name.markdown(f"**{f.name}**  \n`{mtime}`")
            col_size.markdown(f"`{size_mb:.1f} MB`")
            with open(f, "rb") as fp:
                col_dl.download_button(
                    label="⬇️ Baixar",
                    data=fp,
                    file_name=f.name,
                    mime="video/mp4",
                    key=f"dl_{f.name}",
                )
            st.divider()

# ── Tab: Histórico de logs ────────────────────────────────────────────────────
with tab_logs:
    st.subheader("Log da última execução")

    if LOG_PATH.exists():
        log_text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
        st.code(log_text[-8000:] if len(log_text) > 8000 else log_text, language=None)
        if st.button("🗑️ Limpar log"):
            LOG_PATH.write_text("")
            st.rerun()
    else:
        st.info("Nenhum log disponível ainda.")
