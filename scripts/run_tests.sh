# =============================================================
# run_tests.sh — Orquestrador de testes completos
# Execute dentro do container CLIENT:
#   ./scripts/run_tests.sh
#
# O script:
#   1. Gera arquivo de teste (10 MB)
#   2. Para cada cenário (A, B, C):
#      a. Aplica regras tc
#      b. Dispara captura tcpdump em background
#      c. Roda cliente TCP
#      d. Roda cliente R-UDP
#      e. Para captura e exporta CSV
#   3. Imprime sumário final
# =============================================================

SERVER_HOST="${SERVER_HOST:-172.20.0.2}"
TEST_FILE="test_10MB.bin"
TEST_SIZE_MB=10
LOG_DIR="logs"
SCRIPTS_DIR="scripts"

mkdir -p "$LOG_DIR"

# --- Gera arquivo de teste ---
generate_test_file() {
    if [ ! -f "$TEST_FILE" ]; then
        echo "[SETUP] Gerando arquivo de teste: ${TEST_SIZE_MB}MB..."
        dd if=/dev/urandom of="$TEST_FILE" bs=1M count="$TEST_SIZE_MB" 2>/dev/null
        echo "[SETUP] Arquivo gerado: $(du -h $TEST_FILE | cut -f1)"
    else
        echo "[SETUP] Arquivo de teste já existe: $TEST_FILE"
    fi
}

# --- Executa um cenário completo ---
run_scenario() {
    local SCENARIO="$1"
    echo ""
    echo "============================================================"
    echo "  CENÁRIO $SCENARIO"
    echo "============================================================"

    # Aplica tc
    bash "$SCRIPTS_DIR/set_scenario.sh" "$SCENARIO"
    sleep 1

    # --- TCP ---
    echo "[TEST] Iniciando captura TCP (cenário $SCENARIO)..."
    bash "$SCRIPTS_DIR/capture.sh" "$SCENARIO" "tcp" 120 &
    CAP_TCP_PID=$!
    sleep 2   # Aguarda tcpdump iniciar

    echo "[TEST] Transferência TCP..."
    python3 client.py --mode tcp --host "$SERVER_HOST" --file "$TEST_FILE" --scenario "$SCENARIO"
    TCP_EXIT=$?

    sleep 2
    kill $CAP_TCP_PID 2>/dev/null
    wait $CAP_TCP_PID 2>/dev/null

    if [ $TCP_EXIT -ne 0 ]; then
        echo "[WARN] Transferência TCP terminou com erro (código $TCP_EXIT)"
    fi

    sleep 3

    # --- R-UDP ---
    echo "[TEST] Iniciando captura R-UDP (cenário $SCENARIO)..."
    bash "$SCRIPTS_DIR/capture.sh" "$SCENARIO" "udp" 300 &
    CAP_UDP_PID=$!
    sleep 2

    echo "[TEST] Transferência R-UDP..."
    python3 client.py --mode rudp --host "$SERVER_HOST" --file "$TEST_FILE" --scenario "$SCENARIO"
    RUDP_EXIT=$?

    sleep 2
    kill $CAP_UDP_PID 2>/dev/null
    wait $CAP_UDP_PID 2>/dev/null

    if [ $RUDP_EXIT -ne 0 ]; then
        echo "[WARN] Transferência R-UDP terminou com erro (código $RUDP_EXIT)"
    fi

    echo "[TEST] Cenário $SCENARIO concluído."
}

# --- Sumário final ---
print_summary() {
    echo ""
    echo "============================================================"
    echo "  SUMÁRIO DOS LOGS GERADOS"
    echo "============================================================"
    ls -lh "$LOG_DIR"/*.csv 2>/dev/null || echo "Nenhum CSV encontrado."
    ls -lh "$LOG_DIR"/*.pcap 2>/dev/null || echo "Nenhum PCAP encontrado."
    ls -lh "$LOG_DIR"/*.json 2>/dev/null || echo "Nenhum JSON encontrado."
    echo "============================================================"
}

# --- Main ---
generate_test_file

for SCENARIO in A B C; do
    run_scenario "$SCENARIO"
    sleep 5
done

# Remove regras tc ao final
bash "$SCRIPTS_DIR/set_scenario.sh" reset

print_summary

echo ""
echo "[DONE] Todos os testes concluídos."
echo "       Execute 'python3 analysis/analyze.py' para gerar os gráficos."
