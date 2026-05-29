# --- Rede ---
DEFAULT_HOST = "0.0.0.0"
SERVER_PORT_TCP  = 5001
SERVER_PORT_RUDP = 5002

# --- Transferência ---
CHUNK_SIZE     = 1450          # bytes por bloco de dados
WINDOW_SIZE    = 256           # tamanho da janela (Selective Repeat)
TIMEOUT        = 1.0           # segundos até retransmissão (valor inicial adaptativo)
MAX_RETRIES    = 10            # máximo de retransmissões por pacote

# --- Cabeçalho de autenticação ---
# Altere para sua matrícula e nome
MATRICULA = "20261005092"
NOME      = "Marcos Dalessandro Cavalcante Lima"
X_CUSTOM_AUTH = f"{MATRICULA}:{NOME}"

# --- Logging ---
LOG_DIR = "logs"

# --- Cenários TC (referência) ---
SCENARIOS = {
    "A": {"loss": 0,  "delay_ms": 10},
    "B": {"loss": 10, "delay_ms": 50},
    "C": {"loss": 20, "delay_ms": 100},
}
