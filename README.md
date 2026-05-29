# PPGCC-Redes — Projeto de Redes de Computadores 2026-1
**Universidade Federal do Piauí — PPGCC/UFPI**

Análise comparativa entre sistemas reais (TCP e R-UDP via Sockets + Docker) e modelos formais de simulação (SimPy).

---

## Estrutura do Projeto

```
.
├── client.py              # Cliente TCP / R-UDP (Selective Repeat)
├── server.py              # Servidor multimodal TCP + R-UDP
├── config.py              # Configurações globais
├── utils.py               # Empacotamento, checksum, logger
├── requirements.txt       # Dependências Python
├── Dockerfile             # Imagem Ubuntu com tc, tcpdump, tshark
├── docker-compose.yml     # Rede 172.20.0.0/16, servidor + cliente
├── scripts/
│   ├── set_scenario.sh    # Aplica regras tc qdisc (cenários A/B/C)
│   ├── capture.sh         # Captura tcpdump → PCAP + CSV
│   └── run_tests.sh       # Orquestrador: roda todos os testes
├── analysis/
│   └── analysis.py        # Gráficos Plotly + Seaborn (análise Fase 1)
└── logs/                  # CSV/JSON/PCAP gerados pelos testes
```

---

## Fase 1 — Implementação Real

### 1. Build e subir os containers

```bash
docker compose up -d --build
```

### 2. Rodar todos os testes automaticamente (dentro do cliente)

```bash
# Sobe os containers
docker compose up -d --build

# Entra no cliente
docker exec -it client bash

# Roda tudo automaticamente (cenários A, B, C — TCP e R-UDP)
chmod +x scripts/*.sh
./scripts/run_tests.sh
```

O script:
- Gera um arquivo o arquivo de teste de 10MB
- Para cada cenário (A, B, C): aplica `tc qdisc`, captura com `tcpdump`, roda TCP e R-UDP
- Salva logs em `logs/` (CSV, JSON, PCAP)

### 3. Gerar gráficos de análise

Ao concluir os teste, copie os logs para fora do container

```bash
# Fora do container
docker cp client:/app/logs ./logs
#você pode criar uma venv ou instalar os pacotes nativamente
pip install -r requirements.txt

python3 analysis/analyze.py
```

Gráficos gerados em `analysis/plots/`:
- `throughput.html/png` — Throughput médio ± desvio padrão
- `transfer_time.html/png` — Tempo de transferência
- `retransmissions.html/png` — Retransmissões R-UDP
- `throughput_boxplot.png` — Boxplot Seaborn
- `loss_impact.html/png` — Impacto da perda no throughput
- `data_integration.html/png` — Aplicação vs tcpdump

---

### 4.Verificação de Autenticação (PCAP)

Para validar o envio do cabeçalho personalizado `X-Custom-Auth` (Matrícula e Nome) nos arquivos de captura `.pcap`, utilize os seguintes métodos:

### 1. Wireshark (GUI)
1. Abra o arquivo `.pcap` desejado.
2. No filtro de exibição, digite: `tcp.payload contains "X-Custom-Auth"`.
3. Clique com o botão direito no pacote encontrado e selecione **Follow > TCP Stream**.

### 2. tshark (CLI)
Para extrair a linha de autenticação diretamente via terminal:
```bash
tshark -r logs/capture_tcp_A_XXXX.pcap -Y 'tcp.payload contains "X-Custom-Auth"' -x
```

### 3. tcpdump (CLI)
Caso queira apenas confirmar a presença via `grep`:
```bash
tcpdump -A -r logs/capture_tcp_A_XXXX.pcap | grep "X-Custom-Auth"
```



## Cenários de Rede

| Cenário | Perda | Delay | Comando tc |
|---------|-------|-------|------------|
| A | 0% | 10 ms | `tc qdisc add dev eth0 root netem delay 10ms` |
| B | 10% | 50 ms | `tc qdisc add dev eth0 root netem delay 50ms loss 10%` |
| C | 20% | 100 ms | `tc qdisc add dev eth0 root netem delay 100ms loss 20%` |

---
