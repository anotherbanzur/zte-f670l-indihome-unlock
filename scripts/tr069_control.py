#!/usr/bin/env python3
"""
tr069_control.py — kendali TR-069 (ACS) & password admin via telnet root ZTE F670L.

Mode:
  --disable-tr069   URL->127.0.0.1, Tr069Enable=0, PeriodicInformEnable=0, save
  --enable-tr069    kembalikan URL ACS + enable (perlu --acs-url)
  --set-admin-pass  ganti password akun admin (IGD.AU1)  -> --new-password
  --show            tampilkan MgtServer & DevAuthInfo

Pemakaian:
  python tr069_control.py --user X --password Y --disable-tr069
License: MIT. Hanya untuk perangkat milik sendiri.
"""
import argparse
import sys

from telnet_session import TelnetSession

DEFAULT_ACS_URL = "http://acs.telkom.net:9090/web/tr069"  # default IndiHome/Telkom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.1.1")
    ap.add_argument("--user", required=True, help="user telnet (kredensial factory sementara)")
    ap.add_argument("--password", required=True)
    ap.add_argument("--disable-tr069", action="store_true")
    ap.add_argument("--enable-tr069", action="store_true")
    ap.add_argument("--acs-url", default=DEFAULT_ACS_URL)
    ap.add_argument("--set-admin-pass", action="store_true")
    ap.add_argument("--new-password")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    cmds = []
    if args.disable_tr069:
        cmds += [
            "sendcmd 1 DB set MgtServer 0 URL http://127.0.0.1",
            "sendcmd 1 DB set MgtServer 0 Tr069Enable 0",
            "sendcmd 1 DB set MgtServer 0 PeriodicInformEnable 0",
            "sendcmd 1 DB save",
        ]
    if args.enable_tr069:
        cmds += [
            f"sendcmd 1 DB set MgtServer 0 URL {args.acs_url}",
            "sendcmd 1 DB set MgtServer 0 Tr069Enable 1",
            "sendcmd 1 DB set MgtServer 0 PeriodicInformEnable 1",
            "sendcmd 1 DB save",
        ]
    if args.set_admin_pass:
        if not args.new_password:
            ap.error("--set-admin-pass butuh --new-password")
        cmds += [
            f"sendcmd 1 DB set DevAuthInfo 0 Pass {args.new_password}",
            "sendcmd 1 DB save",
        ]
    if args.show or not cmds:
        cmds += ["sendcmd 1 DB p MgtServer", "sendcmd 1 DB p DevAuthInfo"]

    t = TelnetSession(args.host)
    try:
        t.login(args.user, args.password)
        for c in cmds:
            print(f"\n>>> {c}")
            out = t.run(c, timeout=12)
            sys.stdout.buffer.write(out)
            sys.stdout.buffer.flush()
    finally:
        t.close()


if __name__ == "__main__":
    main()
