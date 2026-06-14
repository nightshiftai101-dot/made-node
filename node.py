#!/usr/bin/env python3
"""
============================================================
  M.A.D.E. Coin Node  v0.9.1-testnet
  Making A Daily Earning
  https://madecoin.io
============================================================
"""

import argparse
import os
import sys
import threading
import time

DATA_DIR        = os.path.join(os.path.expanduser("~"), ".madecoin")
BLOCKCHAIN_FILE = os.path.join(DATA_DIR, "blockchain.json")
WALLET_FILE     = os.path.join(DATA_DIR, "wallet.json")

API_PORT = 7777
P2P_PORT = 19333

# ── Seed server (HTTP peer registry) ──────────────────────────────────────────
SEED_SERVER = "https://ultimateminingsystem.com/express-api/seed"

BANNER = """
============================================================
  M.A.D.E. Coin Node  v0.9.1-testnet
  Making A Daily Earning  |  MADE
============================================================"""

HELP_TEXT = """
Commands:
  m  / mine          Start CPU mining
  s  / stop          Stop mining
  b  / balance       Show your MADE balance
  i  / info          Node info (height, hashrate, mempool ...)
  send <addr> <amt>  Send MADE to an address
  peer <host:port>   Connect to a peer manually
  peers              List connected peers
  verify             Verify the full chain integrity
  q  / quit          Save and exit
  h  / help          Show this message
"""


def _get_public_ip() -> str:
    """Fetch own public IP from ipify.org (best-effort)."""
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return ""


def _seed_register(p2p_port: int):
    """Register this node with the seed server."""
    try:
        import urllib.request, json
        payload = json.dumps({"port": p2p_port}).encode()
        req = urllib.request.Request(
            SEED_SERVER + "/register",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            result = json.loads(r.read())
            print(f"[seed] Registered as {result.get('registered', '?')}")
    except Exception as e:
        print(f"[seed] Registration failed (no internet?): {e}")


def _seed_get_peers() -> list:
    """Fetch known peers from the seed server."""
    try:
        import urllib.request, json
        with urllib.request.urlopen(SEED_SERVER + "/peers", timeout=8) as r:
            data = json.loads(r.read())
            return data.get("peers", [])
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="M.A.D.E. Coin Node v0.9.1-testnet")
    parser.add_argument("--mine",        action="store_true")
    parser.add_argument("--no-api",      action="store_true")
    parser.add_argument("--no-p2p",      action="store_true")
    parser.add_argument("--no-browser",  action="store_true")
    parser.add_argument("--no-seed",     action="store_true", help="Skip seed server")
    parser.add_argument("--api-port",    type=int, default=API_PORT)
    parser.add_argument("--p2p-port",    type=int, default=P2P_PORT)
    parser.add_argument("--peer",        type=str)
    parser.add_argument("--wallet-info", action="store_true")
    parser.add_argument("--balance",     action="store_true")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    print(BANNER)

    # ── wallet ────────────────────────────────────────────────
    from wallet import Wallet
    wallet = Wallet.load_only(WALLET_FILE)
    if wallet is None:
        print("  [wallet] No wallet found. Open the dashboard to create one.")

    if args.wallet_info:
        if wallet is None:
            print("  No wallet found. Open the dashboard to create one.")
        else:
            print(f"\n  Address    : {wallet.address}")
            print(f"  Public key : {wallet.public_key_hex[:32]}...")
            print(f"  File       : {WALLET_FILE}")
        return

    # ── blockchain ────────────────────────────────────────────
    from blockchain import Blockchain
    bc = Blockchain.load_or_create(BLOCKCHAIN_FILE)

    if args.balance:
        if wallet is None:
            print("  No wallet yet. Open the dashboard to create one.")
        else:
            print(f"\n  Balance : {bc.get_balance(wallet.address)} MADE")
        return

    # ── p2p ───────────────────────────────────────────────────
    p2p = None
    if not args.no_p2p:
        from p2p import P2PNode
        p2p = P2PNode(bc, port=args.p2p_port)
        p2p.start_server()
        if args.peer:
            p2p.add_peer(args.peer)
            p2p.sync_with_peer(args.peer)

    # ── seed node discovery ───────────────────────────────────
    if p2p and not args.no_seed:
        def _seed_bootstrap():
            time.sleep(2)  # let p2p server start first
            # 1. register ourselves
            _seed_register(args.p2p_port)
            # 2. fetch peers and connect
            known = _seed_get_peers()
            if known:
                print(f"[seed] Found {len(known)} peer(s) from seed server")
                for peer in known:
                    p2p.add_peer(peer)
                    p2p.sync_with_peer(peer)
            else:
                print("[seed] No peers yet — you may be the first node online!")
        threading.Thread(target=_seed_bootstrap, daemon=True, name="SeedBootstrap").start()

    # ── miner ─────────────────────────────────────────────────
    from miner import Miner
    miner = Miner(bc, wallet.address if wallet else "GENESIS")

    def _on_block(block):
        bc.save(BLOCKCHAIN_FILE)
        if p2p:
            p2p.broadcast_block(block)

    miner.on_block_mined(_on_block)

    if args.mine:
        if wallet:
            miner.start()
        else:
            print("  [miner] Create a wallet first before mining.")

    # ── api ───────────────────────────────────────────────────
    if not args.no_api:
        from api import create_app
        _wallet_ref = [wallet]
        app = create_app(bc, miner, p2p, _wallet_ref)
        threading.Thread(
            target=lambda: app.run(
                host="0.0.0.0", port=args.api_port,
                debug=False, use_reloader=False
            ),
            daemon=True, name="APIServer",
        ).start()
        dashboard_url = f"http://localhost:{args.api_port}"
        print(f"[api] Dashboard at {dashboard_url}")

        if not args.no_browser:
            def _open_browser():
                time.sleep(1.5)
                try:
                    import webbrowser
                    webbrowser.open(dashboard_url)
                except Exception:
                    print(f"[node] Open your browser to: {dashboard_url}")
            threading.Thread(target=_open_browser, daemon=True, name="BrowserOpen").start()

    # ── auto-save ─────────────────────────────────────────────
    def _autosave():
        while True:
            time.sleep(60)
            bc.save(BLOCKCHAIN_FILE)
    threading.Thread(target=_autosave, daemon=True, name="AutoSave").start()

    # ── re-register with seed every 10 min to stay alive ─────
    if p2p and not args.no_seed:
        def _keepalive():
            while True:
                time.sleep(600)
                _seed_register(args.p2p_port)
        threading.Thread(target=_keepalive, daemon=True, name="SeedKeepalive").start()

    print(f"\n  Wallet  : {wallet.address if wallet else '[no wallet - create via dashboard]'}")
    print(f"  Height  : {bc.height}")
    print(f"  Peers   : {len(p2p.peers) if p2p else 0}")
    print(f"  Mining  : {'YES' if miner.running else 'NO'}")
    print(f"\n  Dashboard: http://localhost:{args.api_port}")
    print(f"  Type 'help' for commands.\n")

    # ── CLI loop ──────────────────────────────────────────────
    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[node] Shutting down ...")
            miner.stop()
            bc.save(BLOCKCHAIN_FILE)
            sys.exit(0)

        cmd_l = cmd.lower()

        if cmd_l in ("q", "quit", "exit"):
            miner.stop()
            bc.save(BLOCKCHAIN_FILE)
            print("[node] Goodbye.")
            break
        elif cmd_l in ("m", "mine"):
            if wallet:
                miner.start()
            else:
                print("  Create a wallet first (open the dashboard).")
        elif cmd_l in ("s", "stop"):
            miner.stop()
        elif cmd_l in ("b", "balance"):
            if wallet:
                print(f"  Balance : {bc.get_balance(wallet.address)} MADE")
            else:
                print("  No wallet yet.")
        elif cmd_l in ("i", "info"):
            st = miner.status()
            print(f"  Height     : {bc.height}")
            print(f"  Last hash  : {bc.last_block.hash[:32]}...")
            print(f"  Difficulty : {bc.difficulty}")
            print(f"  Mempool    : {len(bc.pending_transactions)} tx(s)")
            print(f"  Peers      : {len(p2p.peers) if p2p else 0}")
            print(f"  Mining     : {'YES' if st['running'] else 'NO'}")
            if st["running"]:
                print(f"  Hashrate   : {st['hashrate']}")
                print(f"  Blocks mined: {st['blocks_mined']}")
        elif cmd_l.startswith("send "):
            if not wallet:
                print("  No wallet yet. Create one in the dashboard.")
                continue
            parts = cmd.split()
            if len(parts) == 3:
                _, recipient, raw_amount = parts
                try:
                    amount = float(raw_amount)
                    from blockchain import Transaction
                    tx = Transaction(
                        sender=wallet.address, recipient=recipient, amount=amount,
                        public_key_hex=wallet.public_key_hex,
                    )
                    tx.signature = wallet.sign(tx.signing_data())
                    ok, msg = bc.add_transaction(tx)
                    print(f"  {'OK' if ok else 'FAIL'} {msg}")
                    if ok and p2p:
                        p2p.broadcast_transaction(tx)
                except ValueError:
                    print("  Error: invalid amount")
            else:
                print("  Usage: send <address> <amount>")
        elif cmd_l.startswith("peer "):
            addr = cmd.split(" ", 1)[1].strip()
            if p2p:
                p2p.add_peer(addr)
                p2p.sync_with_peer(addr)
            else:
                print("  P2P is disabled")
        elif cmd_l == "peers":
            peers = list(p2p.peers) if p2p else []
            print(f"  Peers ({len(peers)}): {peers or 'none'}")
        elif cmd_l == "verify":
            ok, msg = bc.is_valid()
            print(f"  {'OK' if ok else 'FAIL'} {msg}")
        elif cmd_l in ("h", "help", "?"):
            print(HELP_TEXT)
        elif cmd_l == "":
            pass
        else:
            print(f"  Unknown command: '{cmd}'. Type 'help'.")


if __name__ == "__main__":
    main()
