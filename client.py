import socket
import threading
import argparse
import os
import sys
import time

from config import (
    SERVER_PORT_TCP, SERVER_PORT_RUDP,
    CHUNK_SIZE, WINDOW_SIZE, TIMEOUT, MAX_RETRIES, X_CUSTOM_AUTH,
)
from utils import (
    TransferLogger,
    pack_packet, unpack_packet,
    FLAG_DATA, FLAG_ACK, FLAG_FIN, FLAG_SYN,
)


# ──────────────────────────────────────────────────────────────────
# MODO TCP
# ──────────────────────────────────────────────────────────────────

def send_tcp(host: str, filepath: str, scenario: str):
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    print(f"[TCP] Enviando '{filename}' ({filesize:,} bytes)  →  {host}:{SERVER_PORT_TCP}")

    logger = TransferLogger("TCP", scenario, "send")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, SERVER_PORT_TCP))

    # Envia cabeçalho de autenticação e nome do arquivo (agora incluindo o cenário)
    sock.sendall(f"X-Custom-Auth: {X_CUSTOM_AUTH}\n".encode())
    sock.sendall(f"{filename}|{scenario}\n".encode())

    logger.start()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
            logger.bytes_total += len(chunk)
            logger.packets_sent += 1
            logger.log_event("sent", size=len(chunk))

    sock.close()
    logger.stop()
    logger.print_summary()
    logger.save_csv()
    logger.save_json()


# ──────────────────────────────────────────────────────────────────
# MODO R-UDP — Selective Repeat (emissor)
# ──────────────────────────────────────────────────────────────────

class SRSender:
    """
    Selective Repeat sender.

    Mantém uma janela de tamanho WINDOW_SIZE.
    Cada slot tem seu próprio timer independente.
    Thread separada escuta ACKs e marca slots como confirmados.
    """

    def __init__(self, sock: socket.socket, addr, logger: TransferLogger):
        self.sock   = sock
        self.addr   = addr
        self.logger = logger

        # Estado da janela
        self.base    = 0           # seq mais antigo não confirmado
        self.next_seq = 0          # próximo seq a enviar

        self.window: dict[int, dict] = {}

        # RTO Adaptativo (Jacobson/Karels)
        self.srtt = None           # Smoothed Round Trip Time
        self.rttvar = None         # RTT Variation
        self.rto = TIMEOUT         # Valor inicial do timeout

        self.lock   = threading.Lock()
        self.done   = False        # FIN confirmado?
        self.fin_sent = False

    # --- Thread de recepção de ACKs ---

    def _ack_listener(self):
        self.sock.settimeout(1.0)
        while not self.done:
            try:
                raw, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            _, ack_num, flags, payload, auth, _ = unpack_packet(raw)

            if flags & FLAG_ACK:
                now = time.perf_counter()
                with self.lock:
                    if flags & FLAG_FIN:
                        print("[R-UDP] FIN-ACK recebido no listener.")
                        self.done = True
                        return

                    if ack_num in self.window and not self.window[ack_num]["acked"]:
                        # Atualiza RTO adaptativo se for a primeira retransmissão
                        if self.window[ack_num]["retries"] == 0:
                            sample_rtt = now - self.window[ack_num]["timer"]
                            if self.srtt is None:
                                self.srtt = sample_rtt
                                self.rttvar = sample_rtt / 2
                            else:
                                alpha = 0.125
                                beta = 0.25
                                self.rttvar = (1 - beta) * self.rttvar + beta * abs(self.srtt - sample_rtt)
                                self.srtt = (1 - alpha) * self.srtt + alpha * sample_rtt
                            self.rto = max(0.2, self.srtt + 4 * self.rttvar)

                        self.window[ack_num]["acked"] = True
                        self.logger.log_event("acked", seq=ack_num)

                        # Fast Retransmit: se recebemos um ACK superior à base,
                        # retransmitimos a base imediatamente (assumindo perda)
                        if ack_num > self.base:
                            if self.base in self.window and not self.window[self.base]["acked"]:
                                self._retransmit(self.base, now)

                        # Avança base
                        while self.base in self.window and self.window[self.base]["acked"]:
                            del self.window[self.base]
                            self.base += 1

    def _retransmit(self, seq, now):
        slot = self.window[seq]
        if slot["retries"] >= MAX_RETRIES:
            print(f"[R-UDP] seq={seq} excedeu MAX_RETRIES — abortando")
            self.done = True
            return
        self.sock.sendto(slot["pkt"], self.addr)
        slot["timer"] = now
        slot["retries"] += 1
        self.logger.retransmits += 1
        self.logger.log_event("retransmit", seq=seq, note=f"retry={slot['retries']} RTO={self.rto:.3f}")

    # --- Verificação e retransmissão por timeout ---
    def _check_timeouts(self):
        now = time.perf_counter()
        with self.lock:
            for seq, slot in list(self.window.items()):
                if not slot["acked"] and (now - slot["timer"]) >= self.rto:
                    self._retransmit(seq, now)

    # --- Envio de um bloco de dados ---
    def send_chunk(self, seq: int, payload: bytes):
        pkt = pack_packet(seq, 0, FLAG_DATA, payload, X_CUSTOM_AUTH)
        with self.lock:
            self.window[seq] = {
                "pkt":     pkt,
                "acked":   False,
                "retries": 0,
                "timer":   time.perf_counter(),
            }
        self.sock.sendto(pkt, self.addr)
        self.logger.packets_sent += 1
        self.logger.bytes_total  += len(payload)
        self.logger.log_event("sent", seq=seq, size=len(payload))

    # --- Espera a janela ter espaço ---
    def wait_for_window(self):
        while True:
            with self.lock:
                if self.next_seq - self.base < WINDOW_SIZE:
                    return
                if self.done:
                    return
            self._check_timeouts()
            time.sleep(0.01)

    # --- Envia FIN e aguarda confirmação via flag ---
    def send_fin(self):
        fin_pkt = pack_packet(self.next_seq, 0, FLAG_FIN, b"", X_CUSTOM_AUTH)
        print("[R-UDP] Enviando FIN...")
        for attempt in range(MAX_RETRIES):
            with self.lock:
                if self.done: return
            self.sock.sendto(fin_pkt, self.addr)

            # Aguarda um pouco o ACK vir pela thread listener
            for _ in range(int(TIMEOUT * 10)):
                time.sleep(0.1)
                with self.lock:
                    if self.done:
                        print("[R-UDP] FIN confirmado (via listener).")
                        return
            print(f"[R-UDP] FIN timeout (tentativa {attempt+1})")

        print("[R-UDP] FIN não confirmado — encerrando mesmo assim.")
        with self.lock:
            self.done = True


def send_rudp(host: str, filepath: str, scenario: str):
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    print(f"[R-UDP] Enviando '{filename}' ({filesize:,} bytes)  →  {host}:{SERVER_PORT_RUDP}")

    logger = TransferLogger("RUDP", scenario, "send")
    sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr   = (host, SERVER_PORT_RUDP)

    # --- SYN: inicia sessão (enviando filename|scenario) ---
    info_str = f"{filename}|{scenario}"
    syn_pkt = pack_packet(0, 0, FLAG_SYN, info_str.encode(), X_CUSTOM_AUTH)
    sock.settimeout(TIMEOUT)
    for attempt in range(MAX_RETRIES):
        sock.sendto(syn_pkt, addr)
        try:
            raw, _ = sock.recvfrom(65535)
            _, _, flags, _, _, _ = unpack_packet(raw)
            if flags & FLAG_ACK:
                print("[R-UDP] SYN-ACK recebido, iniciando transferência.")
                break
        except socket.timeout:
            print(f"[R-UDP] SYN timeout (tentativa {attempt+1})")
    else:
        print("[R-UDP] Não foi possível estabelecer sessão.")
        sock.close()
        return

    sender = SRSender(sock, addr, logger)

    # Inicia thread de ACKs
    ack_thread = threading.Thread(target=sender._ack_listener, daemon=True)
    ack_thread.start()

    logger.start()

    seq = 0
    with open(filepath, "rb") as f:
        while True:
            if sender.done:
                break
            sender.wait_for_window()
            if sender.done:
                break

            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            sender.send_chunk(seq, chunk)
            sender.next_seq = seq + 1
            seq += 1

    # Aguarda todos os ACKs pendentes
    print("[R-UDP] Aguardando ACKs finais...")
    deadline = time.perf_counter() + TIMEOUT * 5
    while time.perf_counter() < deadline:
        with sender.cv:
            if not sender.window:
                break
            # Espera por mudanças ou timeout
            sender.cv.wait(timeout=0.1)
        sender._check_timeouts()

    sender.send_fin()
    sender.done = True

    logger.stop()
    logger.print_summary()
    logger.save_csv()
    logger.save_json()

    ack_thread.join(timeout=2)
    sock.close()


# ──────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cliente TCP/R-UDP")
    parser.add_argument("--mode",     choices=["tcp", "rudp"], required=True)
    parser.add_argument("--host",     default="127.0.0.1")
    parser.add_argument("--file",     required=True, help="Arquivo a enviar")
    parser.add_argument("--scenario", choices=["A", "B", "C"], default="A")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"Erro: arquivo '{args.file}' não encontrado.")
        sys.exit(1)

    if args.mode == "tcp":
        send_tcp(args.host, args.file, args.scenario)
    else:
        send_rudp(args.host, args.file, args.scenario)


if __name__ == "__main__":
    main()
