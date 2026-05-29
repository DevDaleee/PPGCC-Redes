import hashlib
import time
import csv
import json
import os
import struct
from config import LOG_DIR


# ------------------------------------------------------------------
# Checksum
# ------------------------------------------------------------------

def checksum_md5(data: bytes) -> bytes:
    """Retorna 16 bytes do MD5 do bloco."""
    return hashlib.md5(data).digest()

def verify_checksum(data: bytes, received_checksum: bytes) -> bool:
    return checksum_md5(data) == received_checksum

FLAG_DATA = 0x01
FLAG_ACK  = 0x02
FLAG_FIN  = 0x04
FLAG_SYN  = 0x08

HEADER_BASE_FMT = "!IIBi"          # seq, ack, flags, chunk_size  (13 bytes)
HEADER_BASE_SIZE = struct.calcsize(HEADER_BASE_FMT)   # 13
CHECKSUM_SIZE = 16


def pack_packet(seq: int, ack: int, flags: int,
                payload: bytes, auth: str) -> bytes:
    """Empacota um pacote R-UDP."""
    auth_bytes   = auth.encode()
    auth_len     = len(auth_bytes)
    chunk_size   = len(payload)
    chk          = checksum_md5(payload) if payload else b'\x00' * 16

    header = struct.pack(HEADER_BASE_FMT, seq, ack, flags, chunk_size)
    return header + chk + struct.pack("!B", auth_len) + auth_bytes + payload


def unpack_packet(raw: bytes):
    """
    Desempacota um pacote R-UDP.
    Retorna (seq, ack, flags, payload, auth, valid_checksum).
    """
    offset = 0
    seq, ack, flags, chunk_size = struct.unpack_from(HEADER_BASE_FMT, raw, offset)
    offset += HEADER_BASE_SIZE

    chk_received = raw[offset:offset + CHECKSUM_SIZE]
    offset += CHECKSUM_SIZE

    auth_len = struct.unpack_from("!B", raw, offset)[0]
    offset += 1

    auth = raw[offset:offset + auth_len].decode(errors="replace")
    offset += auth_len

    payload = raw[offset:offset + chunk_size]

    valid = verify_checksum(payload, chk_received) if payload else True
    return seq, ack, flags, payload, auth, valid


# ------------------------------------------------------------------
# Logger de métricas
# ------------------------------------------------------------------

class TransferLogger:
    """Registra métricas de uma transferência e exporta para CSV/JSON."""

    def __init__(self, protocol: str, scenario: str, direction: str):
        self.protocol  = protocol       # TCP | RUDP
        self.scenario  = scenario       # A | B | C
        self.direction = direction      # send | recv
        self.start_time   = None
        self.end_time     = None
        self.bytes_total  = 0
        self.retransmits  = 0
        self.packets_sent = 0
        self.packets_recv = 0
        self.events: list[dict] = []    # linha do tempo granular

    def start(self):
        self.start_time = time.perf_counter()

    def stop(self):
        self.end_time = time.perf_counter()

    def log_event(self, kind: str, seq: int = -1, size: int = 0, note: str = ""):
        ts = time.perf_counter() - (self.start_time or 0)
        self.events.append({
            "ts":   round(ts, 6),
            "kind": kind,       # sent | acked | retransmit | lost | fin
            "seq":  seq,
            "size": size,
            "note": note,
        })

    # --- Propriedades calculadas ---

    @property
    def elapsed(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def throughput_mbps(self) -> float:
        if self.elapsed > 0:
            return (self.bytes_total * 8) / (self.elapsed * 1e6)
        return 0.0

    def summary(self) -> dict:
        return {
            "protocol":       self.protocol,
            "scenario":       self.scenario,
            "direction":      self.direction,
            "bytes_total":    self.bytes_total,
            "elapsed_s":      round(self.elapsed, 4),
            "throughput_mbps": round(self.throughput_mbps, 4),
            "retransmits":    self.retransmits,
            "packets_sent":   self.packets_sent,
            "packets_recv":   self.packets_recv,
        }

    # --- Exportação ---

    def _ensure_dir(self):
        os.makedirs(LOG_DIR, exist_ok=True)

    def save_csv(self, filename: str | None = None):
        self._ensure_dir()
        if filename is None:
            ts = int(time.time())
            filename = f"{self.protocol}_{self.scenario}_{self.direction}_{ts}.csv"
        path = os.path.join(LOG_DIR, filename)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ts","kind","seq","size","note"])
            writer.writeheader()
            writer.writerows(self.events)
        print(f"[LOG] CSV salvo: {path}")
        return path

    def save_json(self, filename: str | None = None):
        self._ensure_dir()
        if filename is None:
            ts = int(time.time())
            filename = f"{self.protocol}_{self.scenario}_{self.direction}_{ts}.json"
        path = os.path.join(LOG_DIR, filename)
        with open(path, "w") as f:
            json.dump({"summary": self.summary(), "events": self.events}, f, indent=2)
        print(f"[LOG] JSON salvo: {path}")
        return path

    def print_summary(self):
        s = self.summary()
        print("\n" + "="*50)
        print(f"  Protocolo  : {s['protocol']}")
        print(f"  Cenário    : {s['scenario']}")
        print(f"  Bytes      : {s['bytes_total']:,}")
        print(f"  Tempo      : {s['elapsed_s']} s")
        print(f"  Throughput : {s['throughput_mbps']} Mbps")
        print(f"  Retransmit : {s['retransmits']}")
        print("="*50 + "\n")
