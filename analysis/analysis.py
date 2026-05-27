# analyze.py — Análise estatística e geração de gráficos
#
# Gera:
#   - Throughput médio ± desvio padrão (TCP vs R-UDP por cenário)
#   - Retransmissões por cenário
#   - Atraso (tempo de transferência) por cenário
#   - Integração: bytes da aplicação vs bytes capturados (tcpdump)
#   - Todos os gráficos salvos em analysis/plots/
#
# Uso:
#   python3 analysis/analyze.py
# =============================================================

import os
import json
import glob
import csv
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

LOG_DIR    = "logs"
PLOT_DIR   = "analysis/plots"
SCENARIOS  = ["A", "B", "C"]
PROTOCOLS  = ["TCP", "RUDP"]
SCENARIO_LABELS = {
    "A": "A (0% / 10ms)",
    "B": "B (10% / 50ms)",
    "C": "C (20% / 100ms)",
}

os.makedirs(PLOT_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────
# 1. Carregamento de dados
# ──────────────────────────────────────────────────────────────────

def load_app_metrics() -> pd.DataFrame:
    """Carrega todos os arquivos JSON de métricas da aplicação."""
    records = []
    for path in glob.glob(os.path.join(LOG_DIR, "*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            s = data.get("summary", {})
            if s:
                records.append(s)
        except Exception as e:
            print(f"[WARN] Erro ao ler {path}: {e}")

    if not records:
        print("[WARN] Nenhum JSON de métricas encontrado. Usando dados simulados para demonstração.")
        return _synthetic_data()

    df = pd.DataFrame(records)
    # Normaliza nomes de coluna
    df.columns = [c.lower() for c in df.columns]
    return df


def _synthetic_data() -> pd.DataFrame:
    """Dados sintéticos para demonstrar os gráficos quando não há execuções reais."""
    np.random.seed(42)
    rows = []
    params = {
        ("TCP",  "A"): (9.5,  0.3,  0.05, 0),
        ("TCP",  "B"): (4.2,  0.8,  0.25, 0),
        ("TCP",  "C"): (1.8,  0.5,  0.80, 0),
        ("RUDP", "A"): (8.9,  0.4,  0.06, 2),
        ("RUDP", "B"): (3.5,  0.9,  0.35, 45),
        ("RUDP", "C"): (1.2,  0.4,  1.20, 180),
    }
    for (proto, sc), (thr_mean, thr_std, ela_mean, retx) in params.items():
        for _ in range(5):   # 5 execuções por combinação
            thr  = max(0.1, np.random.normal(thr_mean, thr_std))
            ela  = max(0.01, np.random.normal(ela_mean, ela_mean * 0.1))
            rows.append({
                "protocol":        proto,
                "scenario":        sc,
                "throughput_mbps": round(thr, 4),
                "elapsed_s":       round(ela, 4),
                "retransmits":     int(abs(np.random.poisson(max(0, retx)))),
                "bytes_total":     10 * 1024 * 1024,
            })
    return pd.DataFrame(rows)


def load_pcap_csv() -> pd.DataFrame:
    """Carrega CSVs gerados pelo tshark e agrega bytes por protocolo/cenário."""
    records = []
    for path in glob.glob(os.path.join(LOG_DIR, "capture_*.csv")):
        basename = os.path.basename(path)
        parts = basename.replace(".csv", "").split("_")
        # capture_<protocol>_<scenario>_<ts>.csv
        if len(parts) < 4:
            continue
        protocol = parts[1].upper()
        scenario = parts[2].upper()
        try:
            df = pd.read_csv(path)
            # tshark exporta frame.len como coluna de tamanho
            size_col = next((c for c in df.columns if "len" in c.lower()), None)
            total_bytes = int(df[size_col].sum()) if size_col else 0
            total_pkts  = len(df)
            records.append({
                "protocol": protocol,
                "scenario": scenario,
                "pcap_bytes": total_bytes,
                "pcap_packets": total_pkts,
            })
        except Exception as e:
            print(f"[WARN] Erro ao ler {path}: {e}")

    if not records:
        return pd.DataFrame(columns=["protocol","scenario","pcap_bytes","pcap_packets"])
    return pd.DataFrame(records).groupby(["protocol","scenario"], as_index=False).sum()


# ──────────────────────────────────────────────────────────────────
# 2. Gráficos com Plotly
# ──────────────────────────────────────────────────────────────────

COLORS = {"TCP": "#3B82F6", "RUDP": "#F59E0B"}

def plot_throughput(df: pd.DataFrame):
    """Throughput médio ± desvio padrão por cenário e protocolo."""
    stats = (df.groupby(["protocol", "scenario"])["throughput_mbps"]
               .agg(["mean", "std"]).reset_index()
               .rename(columns={"mean": "mean_thr", "std": "std_thr"}))
    stats["std_thr"] = stats["std_thr"].fillna(0)
    stats["scenario_label"] = stats["scenario"].map(SCENARIO_LABELS)

    fig = go.Figure()
    for proto in PROTOCOLS:
        sub = stats[stats["protocol"] == proto]
        fig.add_trace(go.Bar(
            name=proto,
            x=sub["scenario_label"],
            y=sub["mean_thr"],
            error_y=dict(type="data", array=sub["std_thr"].tolist(), visible=True),
            marker_color=COLORS[proto],
            text=sub["mean_thr"].round(2).astype(str) + " Mbps",
            textposition="outside",
        ))

    fig.update_layout(
        title="Throughput Médio ± Desvio Padrão — TCP vs R-UDP",
        xaxis_title="Cenário",
        yaxis_title="Throughput (Mbps)",
        barmode="group",
        template="plotly_white",
        legend_title="Protocolo",
    )
    path = os.path.join(PLOT_DIR, "throughput.html")
    fig.write_html(path)
    fig.write_image(path.replace(".html", ".png"), scale=2)
    print(f"[PLOT] {path}")
    return fig


def plot_transfer_time(df: pd.DataFrame):
    """Tempo de transferência médio por cenário."""
    stats = (df.groupby(["protocol", "scenario"])["elapsed_s"]
               .agg(["mean", "std"]).reset_index()
               .rename(columns={"mean": "mean_ela", "std": "std_ela"}))
    stats["std_ela"] = stats["std_ela"].fillna(0)
    stats["scenario_label"] = stats["scenario"].map(SCENARIO_LABELS)

    fig = go.Figure()
    for proto in PROTOCOLS:
        sub = stats[stats["protocol"] == proto]
        fig.add_trace(go.Bar(
            name=proto,
            x=sub["scenario_label"],
            y=sub["mean_ela"],
            error_y=dict(type="data", array=sub["std_ela"].tolist(), visible=True),
            marker_color=COLORS[proto],
            text=sub["mean_ela"].round(3).astype(str) + " s",
            textposition="outside",
        ))

    fig.update_layout(
        title="Tempo de Transferência Médio ± Desvio Padrão",
        xaxis_title="Cenário",
        yaxis_title="Tempo (s)",
        barmode="group",
        template="plotly_white",
        legend_title="Protocolo",
    )
    path = os.path.join(PLOT_DIR, "transfer_time.html")
    fig.write_html(path)
    fig.write_image(path.replace(".html", ".png"), scale=2)
    print(f"[PLOT] {path}")
    return fig


def plot_retransmissions(df: pd.DataFrame):
    """Número de retransmissões por cenário (apenas R-UDP)."""
    rudp = df[df["protocol"] == "RUDP"].copy()
    if rudp.empty:
        print("[WARN] Sem dados R-UDP para retransmissões.")
        return

    stats = (rudp.groupby("scenario")["retransmits"]
                 .agg(["mean", "std"]).reset_index()
                 .rename(columns={"mean": "mean_retx", "std": "std_retx"}))
    stats["std_retx"] = stats["std_retx"].fillna(0)
    stats["scenario_label"] = stats["scenario"].map(SCENARIO_LABELS)

    fig = go.Figure(go.Bar(
        x=stats["scenario_label"],
        y=stats["mean_retx"],
        error_y=dict(type="data", array=stats["std_retx"].tolist(), visible=True),
        marker_color="#EF4444",
        text=stats["mean_retx"].round(1).astype(str),
        textposition="outside",
    ))
    fig.update_layout(
        title="Retransmissões Médias por Cenário — R-UDP",
        xaxis_title="Cenário",
        yaxis_title="Retransmissões",
        template="plotly_white",
    )
    path = os.path.join(PLOT_DIR, "retransmissions.html")
    fig.write_html(path)
    fig.write_image(path.replace(".html", ".png"), scale=2)
    print(f"[PLOT] {path}")
    return fig


def plot_seaborn_boxplot(df: pd.DataFrame):
    """Boxplot do throughput por protocolo e cenário (Seaborn)."""
    df2 = df.copy()
    df2["scenario_label"] = df2["scenario"].map(SCENARIO_LABELS)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.boxplot(
        data=df2,
        x="scenario_label",
        y="throughput_mbps",
        hue="protocol",
        palette={"TCP": "#3B82F6", "RUDP": "#F59E0B"},
        ax=ax,
    )
    ax.set_title("Distribuição do Throughput — TCP vs R-UDP", fontsize=14)
    ax.set_xlabel("Cenário")
    ax.set_ylabel("Throughput (Mbps)")
    ax.legend(title="Protocolo")
    sns.despine()
    path = os.path.join(PLOT_DIR, "throughput_boxplot.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"[PLOT] {path}")


def plot_data_integration(app_df: pd.DataFrame, pcap_df: pd.DataFrame):
    """Compara bytes registrados pela aplicação vs capturados pelo tcpdump."""
    if pcap_df.empty:
        print("[INFO] Sem dados PCAP para integração. Pulando gráfico de integração.")
        return

    merged = app_df.groupby(["protocol", "scenario"])["bytes_total"].mean().reset_index()
    merged = merged.merge(pcap_df, on=["protocol", "scenario"], how="left")
    merged["pcap_bytes"] = merged["pcap_bytes"].fillna(0)
    merged["label"] = merged["protocol"] + "/" + merged["scenario"].map(SCENARIO_LABELS)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Aplicação (Python)",  x=merged["label"], y=merged["bytes_total"],  marker_color="#3B82F6"))
    fig.add_trace(go.Bar(name="Rede (tcpdump)",       x=merged["label"], y=merged["pcap_bytes"],   marker_color="#10B981"))

    fig.update_layout(
        title="Integração de Dados — Aplicação vs tcpdump",
        xaxis_title="Protocolo / Cenário",
        yaxis_title="Bytes",
        barmode="group",
        template="plotly_white",
        legend_title="Fonte",
    )
    path = os.path.join(PLOT_DIR, "data_integration.html")
    fig.write_html(path)
    fig.write_image(path.replace(".html", ".png"), scale=2)
    print(f"[PLOT] {path}")


def plot_packet_loss_impact(df: pd.DataFrame):
    """Linha: throughput vs taxa de perda para TCP e R-UDP."""
    loss_map = {"A": 0, "B": 10, "C": 20}
    df2 = df.copy()
    df2["loss_pct"] = df2["scenario"].map(loss_map)

    stats = (df2.groupby(["protocol","loss_pct"])["throughput_mbps"]
               .mean().reset_index())

    fig = go.Figure()
    for proto in PROTOCOLS:
        sub = stats[stats["protocol"] == proto]
        fig.add_trace(go.Scatter(
            name=proto,
            x=sub["loss_pct"],
            y=sub["throughput_mbps"],
            mode="lines+markers",
            line=dict(color=COLORS[proto], width=2),
            marker=dict(size=8),
        ))

    fig.update_layout(
        title="Impacto da Perda de Pacotes no Throughput",
        xaxis_title="Taxa de Perda (%)",
        yaxis_title="Throughput Médio (Mbps)",
        template="plotly_white",
        legend_title="Protocolo",
    )
    path = os.path.join(PLOT_DIR, "loss_impact.html")
    fig.write_html(path)
    fig.write_image(path.replace(".html", ".png"), scale=2)
    print(f"[PLOT] {path}")


# ──────────────────────────────────────────────────────────────────
# 3. Sumário estatístico CSV
# ──────────────────────────────────────────────────────────────────

def export_summary_csv(df: pd.DataFrame):
    """Exporta tabela de médias e desvios para CSV."""
    stats = df.groupby(["protocol","scenario"]).agg(
        throughput_mean=("throughput_mbps","mean"),
        throughput_std=("throughput_mbps","std"),
        elapsed_mean=("elapsed_s","mean"),
        elapsed_std=("elapsed_s","std"),
        retransmits_mean=("retransmits","mean"),
        retransmits_std=("retransmits","std"),
        n_runs=("throughput_mbps","count"),
    ).reset_index().round(4)

    path = os.path.join(PLOT_DIR, "summary_stats.csv")
    stats.to_csv(path, index=False)
    print(f"[CSV] Sumário estatístico: {path}")
    print(stats.to_string(index=False))


# ──────────────────────────────────────────────────────────────────
# 4. Main
# ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Análise Estatística")
    print("=" * 60)

    app_df  = load_app_metrics()
    pcap_df = load_pcap_csv()

    print(f"\n[INFO] {len(app_df)} registros de métricas carregados.")
    print(f"[INFO] {len(pcap_df)} registros PCAP carregados.\n")

    plot_throughput(app_df)
    plot_transfer_time(app_df)
    plot_retransmissions(app_df)
    plot_seaborn_boxplot(app_df)
    plot_packet_loss_impact(app_df)
    plot_data_integration(app_df, pcap_df)
    export_summary_csv(app_df)

    print("\n[DONE] Todos os gráficos salvos em:", PLOT_DIR)


if __name__ == "__main__":
    main()
