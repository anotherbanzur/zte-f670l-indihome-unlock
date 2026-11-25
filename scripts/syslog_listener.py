# -*- coding: utf-8 -*-
"""Listener syslog UDP 514 — menangkap log router (termasuk operasi TR-069/ACS)."""
import socket
import datetime

OUT = r"D:\Router\syslog_capture.log"
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 514))
print("listener UDP 514 aktif, menunggu log router...", flush=True)
with open(OUT, "a", encoding="utf-8", errors="replace") as f:
    while True:
        data, addr = sock.recvfrom(65535)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {addr[0]}: {data.decode('utf-8', errors='replace')}"
        print(line, flush=True)
        f.write(line + "\n")
        f.flush()
