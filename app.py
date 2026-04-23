#!/usr/bin/env python3
"""
Interface web — inicie com:
    streamlit run app.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
import yaml

CONFIG_PATH = Path("config.yaml")
LOG_PATH = Path("output/run.log")

# ── helpers ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def list_final_files(final_dir: str) -> list[Path]:
    d = Path(final_dir)
    if not d.exists():
        return []
    return sorted(d.glob("*.mp4"), reverse=True)


# ── página ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="YouTube Daily Clipper",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎬 YouTube Daily Clipper")
st.caption("Baixa, corta e concatena vídeos de um canal automaticamente.")

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
        whisper_model = st.selectbox(
            "Modelo Whisper",
            ["tiny", "base", "small", "medium", "large"],
            index=["tiny", "base", "small", "medium", "large"].index(
                config.get("whisper_model", "small")
            ),
            help="Modelos maiores são mais precisos, porém mais lentos.",
        )

    col_d, col_h = st.columns(2)
    with col_d:
        days_back = st.number_input(
            "Dias atrás",
            min_value=1,
            max_value=90,
            value=int(config.get("days_back", 1)),
            help="Quantos dias retroativos considerar como 'novos'.",
        )
    with col_h:
        run_at = st.text_input(
            "Horário diário",
            value=config.get("run_at", "06:00"),
            help="Usado no modo agendador (--schedule).",
        )

    max_videos = st.number_input(
        "Máx. vídeos por execução",
        min_value=0,
        max_value=50,
        value=int(config.get("max_videos", 10)),
        help="0 = sem limite.",
    )

    if st.button("💾 Salvar configuração", use_container_width=True):
        config.update(
            {
                "channel_url": channel_url,
                "start_phrase": start_phrase,
                "language": language,
                "whisper_model": whisper_model,
                "days_back": int(days_back),
                "run_at": run_at,
                "max_videos": int(max_videos),
            }
        )
        save_config(config)
        st.success("Configuração salva!")

    st.divider()
    st.markdown(
        "**Modo agendador** (terminal):\n```\npython main.py --schedule\n```"
    )

# ─── Área principal ───────────────────────────────────────────────────────────
tab_run, tab_files, tab_logs = st.tabs(["▶️ Executar", "📁 Arquivos", "📋 Histórico"])

# ── Tab: Executar ─────────────────────────────────────────────────────────────
with tab_run:
    ready = bool(channel_url.strip()) and bool(start_phrase.strip())

    if not ready:
        st.warning("Preencha a **URL do canal** e a **frase de corte** na barra lateral antes de executar.")

    run_btn = st.button(
        "▶️ Executar agora",
        type="primary",
        disabled=not ready,
        use_container_width=False,
    )

    if run_btn:
        # salva config atual antes de rodar
        config.update(
            {
                "channel_url": channel_url,
                "start_phrase": start_phrase,
                "language": language,
                "whisper_model": whisper_model,
                "days_back": int(days_back),
                "run_at": run_at,
                "max_videos": int(max_videos),
            }
        )
        save_config(config)

        st.info("Processando… acompanhe os logs abaixo.")
        log_box = st.empty()
        logs: list[str] = []

        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).parent),
        )

        for line in proc.stdout:
            line = line.rstrip()
            if line:
                logs.append(line)
                log_box.code("\n".join(logs[-80:]), language=None)

        proc.wait()

        if proc.returncode == 0:
            st.success("✅ Processamento concluído! Veja os arquivos na aba **📁 Arquivos**.")
        else:
            st.error("❌ Ocorreu um erro. Verifique os logs acima.")

# ── Tab: Arquivos gerados ─────────────────────────────────────────────────────
with tab_files:
    st.subheader("Compilados gerados")

    files = list_final_files(config.get("final_dir", "output/final"))

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
