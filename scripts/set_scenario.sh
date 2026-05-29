IFACE="eth0"
SCENARIO="${1:-A}"

reset_tc() {
    echo "[TC] Removendo regras existentes em $IFACE..."
    tc qdisc del dev "$IFACE" root 2>/dev/null || true
    echo "[TC] Interface limpa."
}

apply_scenario() {
    local loss="$1"
    local delay="$2"
    local label="$3"

    reset_tc
    echo "[TC] Aplicando Cenário $label: loss=${loss}% delay=${delay}ms em $IFACE"

    if [ "$loss" -eq 0 ]; then
        tc qdisc add dev "$IFACE" root netem delay "${delay}ms"
    else
        tc qdisc add dev "$IFACE" root netem delay "${delay}ms" loss "${loss}%"
    fi

    echo "[TC] Regra aplicada:"
    tc qdisc show dev "$IFACE"
}

case "$SCENARIO" in
    A) apply_scenario 0  10  "A (0% loss / 10ms)" ;;
    B) apply_scenario 10 50  "B (10% loss / 50ms)" ;;
    C) apply_scenario 20 100 "C (20% loss / 100ms)" ;;
    reset) reset_tc ;;
    *)
        echo "Uso: $0 {A|B|C|reset}"
        exit 1
        ;;
esac
