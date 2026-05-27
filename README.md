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
│   ├── analyze.py         # Gráficos Plotly + Seaborn (análise Fase 1)
│   └── plots/             # Saída dos gráficos (gerada automaticamente)
├── simpy/
│   └── simulator.py       # Simulador SimPy — 10 tarefas de validação (Fase 2)
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
docker exec -it client bash
./scripts/run_tests.sh
```

O script:
- Gera um arquivo de teste de 10 MB
- Para cada cenário (A, B, C): aplica `tc qdisc`, captura com `tcpdump`, roda TCP e R-UDP
- Salva logs em `logs/` (CSV, JSON, PCAP)

### 3. Rodar manualmente (cenário específico)

```bash
# No container cliente — aplica cenário B
./scripts/set_scenario.sh B

# Em outro terminal, captura tráfego UDP por 120s
./scripts/capture.sh B udp 120 &

# Roda transferência R-UDP
python3 client.py --mode rudp --host 172.20.0.2 --file test.bin --scenario B
```

### 4. Gerar gráficos de análise

```bash
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

## Fase 2 — Modelagem Estocástica (SimPy)

```bash
pip install -r requirements.txt
python3 simpy/simulator.py
```

### 10 Tarefas de Validação

| # | Tarefa | Descrição |
|---|--------|-----------|
| T1 | Modelagem de Atraso | Distribuição normal calibrada por cenário |
| T2 | Perda de Bernoulli | Valida taxa SimPy vs tc qdisc |
| T3 | Timeout e Retransmissão | Conta retransmissões por cenário |
| T4 | Curva de Vazão | Throughput de 1 MB a 100 MB |
| T5 | Sensibilidade da Janela | Saturação teórica variando N |
| T6 | Validação de RTT | RTT simulado vs esperado (2×delay) |
| T7 | Impacto do Jitter | Throughput vs std do atraso |
| T8 | Cenário de Estresse | 25% de perda, múltiplos delays |
| T9 | Análise de Eficiência | Razão pacotes de dados / controle |
| T10 | Convergência Estatística | IC 95% com 30+ execuções |

Saídas em `analysis/plots/`:
- `t1_delay_distribution.html/png` até `t10_convergence.html/png`
- `real_vs_simulated.html/png` — Comparativo Real vs Simulado
- `simulation_results.json` — Dados consolidados de todas as tarefas

---

## Cenários de Rede

| Cenário | Perda | Delay | Comando tc |
|---------|-------|-------|------------|
| A | 0% | 10 ms | `tc qdisc add dev eth0 root netem delay 10ms` |
| B | 10% | 50 ms | `tc qdisc add dev eth0 root netem delay 50ms loss 10%` |
| C | 20% | 100 ms | `tc qdisc add dev eth0 root netem delay 100ms loss 20%` |

---

## Critérios de Avaliação (Fase 1 — 10 pts)

| Critério | Pontos |
|----------|--------|
| Ambiente Docker & TC | 1.0 |
| Protocolo R-UDP (Selective Repeat) | 2.5 |
| Validação TCPDump (PCAP + X-Custom-Auth) | 1.5 |
| Análise Estatística (gráficos) | 2.0 |
| Integração de Dados (app vs tcpdump) | 1.0 |
| Relatório SBC | 1.0 |
| Vídeo Demonstrativo | 1.0 |

**Datas de entrega:**
- Fase 1: **29/05/2026**
- Fase 2: **25/06/2026**
