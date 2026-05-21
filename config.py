# ============================================================
# config.py — Configurações globais do projeto
# PPGCC/UFPI — Redes de Computadores 2026-1
# ============================================================

# --- Rede ---
DEFAULT_HOST = "0.0.0.0"
SERVER_PORT_TCP  = 5001
SERVER_PORT_RUDP = 5002

# --- Transferência ---
CHUNK_SIZE     = 4096          # bytes por bloco de dados
WINDOW_SIZE    = 8             # tamanho da janela (Selective Repeat)
TIMEOUT        = 2.0           # segundos até retransmissão
MAX_RETRIES    = 10            # tentativas antes de desistir

# --- Cabeçalho de autenticação ---
# Altere para sua matrícula e nome
MATRICULA = "000000"
NOME      = "Seu Nome Aqui"
X_CUSTOM_AUTH = f"{MATRICULA}:{NOME}"

# --- Logging ---
LOG_DIR = "logs"

# --- Cenários TC (referência) ---
SCENARIOS = {
    "A": {"loss": 0,  "delay_ms": 10},
    "B": {"loss": 10, "delay_ms": 50},
    "C": {"loss": 20, "delay_ms": 100},
}
