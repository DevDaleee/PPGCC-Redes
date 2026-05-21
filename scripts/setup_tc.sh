#!/bin/bash

INTERFACE="eth0"
SCENARIO=$1

# Limpa configurações anteriores
tc qdisc del dev $INTERFACE root 2>/dev/null

case $SCENARIO in
    "A")
        echo "Configurando Cenário A: 0% perda, 10ms delay"
        tc qdisc add dev $INTERFACE root netem delay 10ms
        ;;
    "B")
        echo "Configurando Cenário B: 10% perda, 50ms delay"
        tc qdisc add dev $INTERFACE root netem delay 50ms loss 10%
        ;;
    "C")
        echo "Configurando Cenário C: 20% perda, 100ms delay"
        tc qdisc add dev $INTERFACE root netem delay 100ms loss 20%
        ;;
    *)
        echo "Uso: $0 {A|B|C}"
        exit 1
        ;;
esac

tc qdisc show dev $INTERFACE
