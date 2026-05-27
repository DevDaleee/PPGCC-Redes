#!/usr/bin/env bash
# =============================================================
# capture.sh — Captura tráfego com tcpdump e exporta para CSV
# PPGCC/UFPI — Redes de Computadores 2026-1
#
# Uso:
#   ./scripts/capture.sh <scenario> <protocol> <duration_s>
#   Exemplo: ./scripts/capture.sh A tcp 30
#
# Saída:
#   logs/capture_<protocol>_<scenario>_<ts>.pcap
#   logs/capture_<protocol>_<scenario>_<ts>.csv
# =============================================================

SCENARIO="${1:-A}"
PROTOCOL="${2:-tcp}"     # tcp | udp
DURATION="${3:-60}"      # segundos de captura
IFACE="eth0"
LOG_DIR="logs"
TS=$(date +%s)
PCAP_FILE="${LOG_DIR}/capture_${PROTOCOL}_${SCENARIO}_${TS}.pcap"
CSV_FILE="${LOG_DIR}/capture_${PROTOCOL}_${SCENARIO}_${TS}.csv"

mkdir -p "$LOG_DIR"

# --- Filtro de porta por protocolo ---
if [ "$PROTOCOL" = "tcp" ]; then
    FILTER="tcp port 5001"
else
    FILTER="udp port 5002"
fi

echo "[CAPTURE] Iniciando captura: protocolo=${PROTOCOL} cenário=${SCENARIO} duração=${DURATION}s"
echo "[CAPTURE] Interface: $IFACE  |  Filtro: '$FILTER'"
echo "[CAPTURE] PCAP: $PCAP_FILE"

# Captura em background por $DURATION segundos
tcpdump -i "$IFACE" "$FILTER" -w "$PCAP_FILE" -n &
TCPDUMP_PID=$!

sleep "$DURATION"

kill "$TCPDUMP_PID" 2>/dev/null
wait "$TCPDUMP_PID" 2>/dev/null

echo "[CAPTURE] Captura finalizada. Convertendo para CSV..."

# --- Converte pcap → CSV com tshark ---
# Campos: timestamp, IP src, IP dst, protocolo, tamanho, flags TCP, seq, ack
tshark -r "$PCAP_FILE" \
    -T fields \
    -e frame.time_epoch \
    -e ip.src \
    -e ip.dst \
    -e ip.proto \
    -e frame.len \
    -e tcp.flags \
    -e tcp.seq \
    -e tcp.ack \
    -e udp.length \
    -E header=y \
    -E separator=, \
    -E quote=d \
    -E occurrence=f \
    > "$CSV_FILE" 2>/dev/null

LINES=$(wc -l < "$CSV_FILE")
echo "[CAPTURE] CSV gerado: $CSV_FILE  ($LINES linhas)"
echo "[CAPTURE] Arquivos prontos para análise."
