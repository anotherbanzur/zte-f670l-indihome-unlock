#!/usr/bin/env python3
"""
telnet_session.py — klien telnet generik untuk sesi factory/root ZTE F670L.

Pemakaian:
  python telnet_session.py --user <tempuser> --password <temppass> \
      --cmd "sendcmd 1 DB p DevAuthInfo" \
      --cmd "sendcmd 1 DB save"

Bisa banyak --cmd; dieksekusi berurutan. License: MIT.
"""
import argparse
import socket
import sys
import time


def strip_iac(d: bytes) -> bytes:
    """Buang byte negosiasi telnet (IAC)."""
    out = bytearray()
    i = 0
    while i < len(d):
        if d[i] == 0xFF and i + 1 < len(d):
            c = d[i + 1]
            if c in (0xFB, 0xFC, 0xFD, 0xFE):
                i += 3
                continue
            if c == 0xFF:
                out.append(0xFF)
                i += 2
                continue
            i += 2
            continue
        out.append(d[i])
        i += 1
    return bytes(out)


class TelnetSession:
    def __init__(self, host, port=23, timeout=15):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(3)
        self.buf = b""

    def read_until(self, tokens, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            try:
                d = self.s.recv(4096)
                if d:
                    self.buf += d
            except socket.timeout:
                pass
            for t in tokens:
                if t in self.buf:
                    out, self.buf = self.buf, b""
                    return out
        out, self.buf = self.buf, b""
        return out

    def login(self, user, password):
        self.read_until([b"Login:", b"login:", b"Username:"])
        self.s.sendall(user.encode() + b"\r\n")
        time.sleep(1)
        self.read_until([b"Password:", b"password:"])
        self.s.sendall(password.encode() + b"\r\n")
        time.sleep(2)
        return self.read_until([b"# "], timeout=10)

    def run(self, cmd, timeout=10):
        self.s.sendall(cmd.encode() + b"\r\n")
        time.sleep(1.5)
        return self.read_until([b"/ # ", b"# "], timeout=timeout)

    def close(self):
        self.s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.1.1")
    ap.add_argument("--port", type=int, default=23)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--cmd", action="append", required=True, help="perintah; boleh diulang")
    args = ap.parse_args()

    t = TelnetSession(args.host, args.port)
    try:
        t.login(args.user, args.password)
        for c in args.cmd:
            print(f"\n>>> {c}")
            out = t.run(c)
            sys.stdout.buffer.write(strip_iac(out))
            sys.stdout.buffer.flush()
    finally:
        t.close()


if __name__ == "__main__":
    main()
