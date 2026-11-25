#!/usr/bin/env python3
"""
factory_unlock.py — buka telnet root ZTE F670L (V9.0.11P1N-series) via /webFac.

Alur: reset sesi -> RequestFactoryMode -> SendSq(challenge) -> SendInfo(bukti MAC)
      -> CheckLoginAuth(KREDENSIAL WEB ADMIN) -> FactoryMode mode=2
      -> mengembalikan "FactoryModeAuth.gch?user=X&pass=Y" (kredensial telnet sementara)

Pemakaian:
  python factory_unlock.py --host 192.168.1.1 --user admin --password "Telkomdso123"

Hanya untuk perangkat milik sendiri. License: MIT.
"""
import argparse
import random
import sys
import uuid

try:
    from Crypto.Cipher import AES
except ImportError:
    try:
        from Cryptodome.Cipher import AES
    except ImportError:
        print("butuh pycryptodome: pip install pycryptodome", file=sys.stderr)
        sys.exit(1)

import requests

# KEY_POOL spesifik per build firmware. Dua pool yang dikenal:
#  - POOL_A: terbukti untuk V9.0.11P1N-series (IndiHome)
#  - POOL_B: V9.0.10P18N3D (Airtel) — dari rendlavenu/zte-f670l-toolkit
POOL_A = bytes([
    0x8C, 0x23, 0x65, 0xD1, 0xFC, 0x32, 0x45, 0x37, 0x11, 0x28,
    0x71, 0x63, 0x07, 0x20, 0x69, 0x14, 0x73, 0xE7, 0xD4, 0x53,
    0x13, 0x24, 0x36, 0xC2, 0xB5, 0xE1, 0xFC, 0xCF, 0x8A, 0x9A,
    0x41, 0x89, 0x3C, 0x49, 0xCF, 0x5C, 0x72, 0x8C, 0x9E, 0xEB,
    0x75, 0x0D, 0x3F, 0xD1, 0xFE, 0xCC, 0x57, 0x65, 0x7A, 0x35,
    0x21, 0x3E, 0x68, 0x53, 0x7E, 0x97, 0x02, 0x48, 0x74, 0x71,
    0x95, 0x34, 0x53, 0x84, 0xB4, 0xC3, 0xE2, 0xD6, 0x27, 0x3D,
    0xE6, 0x5D, 0x72, 0x9C, 0xBC, 0x3D, 0x03, 0xFD, 0x76, 0xC1,
    0x9C, 0x25, 0xA8, 0x92, 0x47, 0xE4, 0x18, 0x0F, 0x24, 0x3F,
    0x4F, 0x67, 0xEC, 0x97, 0xF4, 0x99,
])
POOL_B = bytes([
    0x9C, 0x33, 0x75, 0xD1, 0x1C, 0x42, 0x45, 0x37, 0x18, 0x48,
    0x91, 0x73, 0x17, 0x45, 0x79, 0x44, 0x43, 0xD7, 0xD5, 0x73,
    0x33, 0x54, 0x76, 0xD2, 0xC5, 0xF1, 0x2C, 0x4F, 0x7A, 0xBA,
    0x61, 0xD9, 0x5C, 0x69, 0xDF, 0x8C, 0xD2, 0x1C, 0xDE, 0x3B,
    0x35, 0x2D, 0x2F, 0xE1, 0xDE, 0x4C, 0x77, 0xF5, 0x1A, 0x65,
    0xD1, 0xFE, 0x18, 0x43, 0x8E, 0xA7, 0x42, 0x08, 0x04, 0x78,
    0xD5, 0xE4, 0xF3, 0x34, 0xA4, 0xD3, 0xF2, 0x36, 0x47, 0x6D,
    0x86, 0x9D, 0x42, 0x65, 0x13, 0x42, 0xDC, 0x42, 0x99, 0x48,
    0xDC, 0x67, 0x9F, 0x9E, 0xDC, 0x46, 0x37, 0x5F, 0x84, 0x9F,
    0x6F, 0x76, 0xCE, 0x79, 0x4F, 0x49,
])


def pad16(data: bytes) -> bytes:
    return data + b"\x00" * ((16 - len(data) % 16) % 16)


def enc(key: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).encrypt(pad16(data))


def dec(key: bytes, data: bytes) -> bytes:
    n = len(data) // 16 * 16
    return AES.new(key, AES.MODE_ECB).decrypt(data[:n]).rstrip(b"\x00")


def local_mac_bytes() -> bytes:
    """MAC antarmuka lokal (untuk bukti CheckClientInfo)."""
    node = uuid.getnode()
    return bytes.fromhex(f"{node:012X}")


def build_reverse_table() -> dict:
    """reverse[decoded] = i, dengan decoded = pow(i, 0x4F7, 0x9E9) & 255."""
    rev = {}
    for i in range(0x9E9):
        d = pow(i, 0x4F7, 0x9E9) & 255
        if d not in rev:
            rev[d] = i
    return rev


def proof_method2(mac: bytes) -> bytes:
    """Bukti CheckClientInfo: 6 kata little-endian dari MAC lokal."""
    rev = build_reverse_table()
    out = bytearray(24)
    for i in range(6):
        v = rev[mac[i]]
        out[i * 4:i * 4 + 4] = v.to_bytes(4, "little")
    return bytes(out)


def handshake(s: requests.Session, host: str, pool: bytes):
    """Kembalikan key AES jika handshake sukses."""
    r = s.post(f"http://{host}/webFac", data="SendSq.gch", timeout=8)
    if r.status_code != 400:
        raise RuntimeError(f"reset HTTP {r.status_code}")
    try:
        s.post(f"http://{host}/webFac", data="RequestFactoryMode.gch", timeout=8)
    except requests.exceptions.RequestException:
        pass  # koneksi ditutup server = normal
    rand = random.randint(0, 59)
    r = s.post(f"http://{host}/webFac", data=f"SendSq.gch?rand={rand}\r\n", timeout=8)
    if r.status_code != 200:
        raise RuntimeError(f"SendSq HTTP {r.status_code}")
    text = r.text.strip()
    if text.startswith("newrand="):
        newrand = int(text[len("newrand="):])
    elif text.startswith("re_rand="):
        newrand = int(text.split("&")[0][len("re_rand="):])
    else:
        raise RuntimeError(f"challenge tak dikenal: {text[:60]!r}")
    index = ((0x1000193 * rand) & 0x3F ^ newrand) % 60
    return bytes(b ^ 0xA5 for b in pool[index:index + 24])


def unlock(host: str, user: str, password: str, verbose=False):
    mac = local_mac_bytes()
    proof = proof_method2(mac)
    for name, pool in (("A", POOL_A), ("B", POOL_B)):
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux armv7l) AppleWebKit/537.36"
        try:
            key = handshake(s, host, pool)
        except Exception as e:
            if verbose:
                print(f"pool {name}: handshake gagal: {e}")
            continue
        cmd = b"SendInfo.gch?info=6|" + b"".join(v.to_bytes(4, "little") for v in
                                                  [int.from_bytes(proof[i * 4:i * 4 + 4], "little") for i in range(6)])
        r = s.post(f"http://{host}/webFacEntry", data=enc(key, cmd), timeout=8)
        if verbose:
            print(f"pool {name}: SendInfo={r.status_code}")
        if r.status_code != 200:
            continue
        cmd = f"CheckLoginAuth.gch?version50&user={user}&pass={password}".encode()
        r = s.post(f"http://{host}/webFacEntry", data=enc(key, cmd), timeout=8)
        if verbose:
            print(f"pool {name}: Auth={r.status_code}")
        if r.status_code != 200:
            continue
        reply = dec(key, r.content)
        if not reply.startswith(b"FactoryMode"):
            if verbose:
                print(f"pool {name}: balasan aneh: {reply[:60]!r}")
            continue
        cmd = b"FactoryMode.gch?mode=2&user=notused"
        r = s.post(f"http://{host}/webFacEntry", data=enc(key, cmd), timeout=8)
        if verbose:
            print(f"pool {name}: FactoryMode={r.status_code}")
        if r.status_code != 200:
            continue
        return dec(key, r.content).decode("latin1")
    return None


def main():
    ap = argparse.ArgumentParser(description="ZTE F670L /webFac factory unlock (perangkat sendiri!)")
    ap.add_argument("--host", default="192.168.1.1")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True, help="password WEB admin (bukan telnet)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    result = unlock(args.host, args.user, args.password, args.verbose)
    if result:
        print("SUKSES:", result)
        print("-> telnet port 23 aktif; login dengan kredensial di atas.")
    else:
        print("GAGAL — kredensial salah atau pool firmware berbeda.")
        sys.exit(1)


if __name__ == "__main__":
    main()
