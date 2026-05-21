#!/bin/bash

# Este script deve ser executado no host ou dentro do container do cliente
# para automatizar a execução de um teste.

MODE=$1        # tcp | rudp
SCENARIO=$2    # A | B | C
FILE=$3        # caminho do arquivo
SERVER_IP="172.20.0.2"

if [ -z "$MODE" ] || [ -z "$SCENARIO" ] || [ -z "$FILE" ]; then
    echo "Uso: $0 <mode> <scenario> <file>"
    exit 1
fi

TIMESTAMP=$(date +%s)
PCAP_FILE="logs/capture_${MODE}_${SCENARIO}_${TIMESTAMP}.pcap"
CSV_FILE="logs/capture_${MODE}_${SCENARIO}_${TIMESTAMP}.csv"

echo "=== Iniciando Teste: Modo=$MODE, Cenário=$SCENARIO ==="

# 1. Configurar TC no cliente (ou servidor, dependendo de onde queremos a perda)
# Geralmente injetamos no emissor (cliente) para perda de saída ou receptor (servidor) para perda de entrada.
# Para simplificar, vamos rodar no cliente.
docker exec -it client bash /app/scripts/setup_tc.sh $SCENARIO

# 2. Iniciar tcpdump em background no cliente
echo "Iniciando captura em $PCAP_FILE..."
docker exec -d client tcpdump -i eth0 -w /app/$PCAP_FILE

# 3. Executar o cliente
echo "Executando cliente..."
docker exec -it client python3 client.py --mode $MODE --host $SERVER_IP --file $FILE --scenario $SCENARIO

# 4. Parar tcpdump
echo "Parando captura..."
docker exec -it client pkill tcpdump

# 5. Exportar PCAP para CSV usando tshark
echo "Exportando para CSV..."
docker exec -it client tshark -r /app/$PCAP_FILE \
    -T fields \
    -e frame.time_relative \
    -e ip.src \
    -e ip.dst \
    -e frame.len \
    -e tcp.seq \
    -e tcp.ack \
    -e udp.length \
    -E header=y -E separator=, > $CSV_FILE

echo "Teste concluído. Arquivos gerados em logs/"
