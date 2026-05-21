# ============================================================
# server.py — Servidor TCP / R-UDP (Multimodal)
# PPGCC/UFPI — Redes de Computadores 2026-1
#
# Uso:
#   python server.py
# ============================================================

import socket
import threading
import argparse
import os
import sys
import time

from config import (
    DEFAULT_HOST, SERVER_PORT_TCP, SERVER_PORT_RUDP,
    CHUNK_SIZE, WINDOW_SIZE, TIMEOUT, X_CUSTOM_AUTH, LOG_DIR,
)
from utils import (
    TransferLogger,
    pack_packet, unpack_packet,
    FLAG_DATA, FLAG_ACK, FLAG_FIN, FLAG_SYN,
)

os.makedirs(LOG_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────────
# MODO TCP
# ──────────────────────────────────────────────────────────────────

def handle_tcp_client(conn: socket.socket, addr):
    print(f"[TCP] Conexão de {addr}")
    
    # Recebe cabeçalho X-Custom-Auth (primeira linha terminada em '\n')
    header_line = b""
    while b"\n" not in header_line:
        chunk = conn.recv(256)
        if not chunk:
            break
        header_line += chunk
    if not header_line:
        conn.close()
        return

    auth_received = header_line.decode().strip()
    print(f"[TCP] Auth recebido: {auth_received}")

    # Recebe nome do arquivo (segunda linha)
    fname_line = b""
    while b"\n" not in fname_line:
        chunk = conn.recv(256)
        if not chunk:
            break
        fname_line += chunk
    
    # Formato esperado do cliente pode incluir o cenário: "filename|scenario"
    client_info = fname_line.decode().strip().split("|")
    filename = client_info[0]
    scenario = client_info[1] if len(client_info) > 1 else "unknown"
    
    save_path = os.path.join(LOG_DIR, f"recv_tcp_{filename}")
    logger = TransferLogger("TCP", scenario, "recv")
    logger.start()

    # Recebe dados
    with open(save_path, "wb") as f:
        while True:
            data = conn.recv(CHUNK_SIZE)
            if not data:
                break
            f.write(data)
            logger.bytes_total += len(data)
            logger.packets_recv += 1
            logger.log_event("recv", size=len(data))

    logger.stop()
    logger.print_summary()
    logger.save_csv()
    logger.save_json()
    conn.close()
    print(f"[TCP] Arquivo salvo em {save_path}")


def run_tcp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((DEFAULT_HOST, SERVER_PORT_TCP))
    srv.listen(5)
    print(f"[TCP] Servidor ativo em {DEFAULT_HOST}:{SERVER_PORT_TCP}")
    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=handle_tcp_client,
                             args=(conn, addr), daemon=True)
        t.start()


# ──────────────────────────────────────────────────────────────────
# MODO R-UDP  —  Selective Repeat (receptor)
# ──────────────────────────────────────────────────────────────────

def run_rudp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((DEFAULT_HOST, SERVER_PORT_RUDP))
    # Removemos o timeout global para que o servidor fique sempre ouvindo
    print(f"[R-UDP] Servidor ativo em {DEFAULT_HOST}:{SERVER_PORT_RUDP}")

    expected = 0
    buf: dict[int, bytes] = {}
    save_path = None
    file_obj  = None
    logger    = None
    scenario  = "unknown"

    while True:
        try:
            raw, addr = sock.recvfrom(65535)
        except Exception as e:
            print(f"[R-UDP] Erro no socket: {e}")
            continue

        seq, ack_num, flags, payload, auth, valid = unpack_packet(raw)

        # --- SYN: início de sessão ---
        if flags & FLAG_SYN:
            client_info = payload.decode(errors="replace").split("|")
            filename = client_info[0]
            scenario = client_info[1] if len(client_info) > 1 else "unknown"
            
            save_path = os.path.join(LOG_DIR, f"recv_rudp_{filename}")
            file_obj  = open(save_path, "wb")
            expected  = 0
            buf       = {}
            
            logger = TransferLogger("RUDP", scenario, "recv")
            logger.start()
            
            print(f"[R-UDP] Sessão iniciada por {addr} | Arquivo: {filename} | Cenário: {scenario}")
            
            # ACK do SYN
            ack_pkt = pack_packet(0, 0, FLAG_ACK, b"", X_CUSTOM_AUTH)
            sock.sendto(ack_pkt, addr)
            continue

        # --- FIN: fim de transferência ---
        if flags & FLAG_FIN:
            if file_obj:
                _flush_buffer(file_obj, buf, expected)
                file_obj.close()
                file_obj = None
            
            if logger:
                logger.stop()
                logger.print_summary()
                logger.save_csv()
                logger.save_json()
            
            # ACK do FIN
            ack_pkt = pack_packet(0, seq, FLAG_ACK | FLAG_FIN, b"", X_CUSTOM_AUTH)
            sock.sendto(ack_pkt, addr)
            print(f"[R-UDP] Transferência concluída. Arquivo salvo em {save_path}")
            
            # Reset para próxima conexão
            expected = 0
            buf      = {}
            continue

        # --- DATA ---
        if not valid or not logger:
            continue

        logger.bytes_total += len(payload)
        logger.packets_recv += 1
        logger.log_event("recv", seq=seq, size=len(payload))

        win_end = expected + WINDOW_SIZE
        if expected <= seq < win_end:
            buf[seq] = payload
            while expected in buf:
                if file_obj:
                    file_obj.write(buf.pop(expected))
                expected += 1
        elif seq < expected:
            pass

        # ACK individual
        ack_pkt = pack_packet(0, seq, FLAG_ACK, b"", X_CUSTOM_AUTH)
        sock.sendto(ack_pkt, addr)


def _flush_buffer(file_obj, buf: dict, start: int):
    for seq in sorted(buf):
        file_obj.write(buf[seq])


# ──────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────

def main():
    # Iniciando as threads para ambos os modos
    tcp_thread = threading.Thread(target=run_tcp_server, daemon=True)
    rudp_thread = threading.Thread(target=run_rudp_server, daemon=True)
    
    tcp_thread.start()
    rudp_thread.start()
    
    print("=== Servidor PPGCC Multimodal Iniciado ===")
    print("Pressione Ctrl+C para encerrar.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")

if __name__ == "__main__":
    main()
