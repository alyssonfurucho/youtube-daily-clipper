#!/usr/bin/env bash
set -euo pipefail

echo "=== YouTube Daily Clipper — Setup ==="

# ── ffmpeg ─────────────────────────────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    echo "Instalando ffmpeg..."
    if command -v brew &>/dev/null; then
        brew install ffmpeg
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y ffmpeg
    else
        echo "AVISO: ffmpeg não encontrado. Instale manualmente: https://ffmpeg.org/download.html"
    fi
else
    echo "ffmpeg já instalado: $(ffmpeg -version 2>&1 | head -1)"
fi

# ── Python venv ────────────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Instalando dependências Python..."
pip install --upgrade pip -q
pip install -r requirements.txt

echo ""
echo "=== Setup concluído! ==="
echo ""
echo "Próximos passos:"
echo "  1. Inicie a interface web:"
echo "       source .venv/bin/activate && streamlit run app.py"
echo "  2. Acesse http://localhost:8501 no navegador"
echo "  3. Configure o canal e a frase na barra lateral e clique em Executar"
echo ""
echo "  Modo CLI (sem interface):"
echo "       source .venv/bin/activate && python main.py"
echo "  Agendador diário:"
echo "       source .venv/bin/activate && python main.py --schedule"
