"""Manage the ShieldAI / PPAG user store (rotate the seeded demo passwords!).

Examples:
    python scripts/manage_users.py list
    python scripts/manage_users.py set-password admin 'a-strong-password'
    python scripts/manage_users.py add jdoe 'pw' analyst
"""

from __future__ import annotations

import argparse
import json

from app.core.settings import settings
from app.proxy.identity import UserStore


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sp = sub.add_parser("set-password")
    sp.add_argument("username")
    sp.add_argument("password")
    ap_add = sub.add_parser("add")
    ap_add.add_argument("username")
    ap_add.add_argument("password")
    ap_add.add_argument("role", choices=["admin", "analyst", "officer", "teller"])
    args = ap.parse_args()

    store = UserStore(settings.users_store_path)

    if args.cmd == "list":
        data = json.loads(open(settings.users_store_path, encoding="utf-8").read())
        for u, row in data.items():
            print(f"{u:12} role={row['role']:8} mfa={'yes' if row.get('totp_secret') else 'no'}")
    elif args.cmd == "set-password":
        ok = store.set_password(args.username, args.password)
        print("updated" if ok else "user not found")
    elif args.cmd == "add":
        ok = store.create_user(args.username, args.password, args.role)
        print("created" if ok else "user already exists")


if __name__ == "__main__":
    main()
