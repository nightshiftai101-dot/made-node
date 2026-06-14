"""
M.A.D.E. Coin - REST API
"""
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os, json

from blockchain import Blockchain, Transaction
from wallet import Wallet, verify, vk_from_hex

DASHBOARD   = os.path.join(os.path.dirname(__file__), "dashboard.html")
DATA_DIR    = os.path.join(os.path.expanduser("~"), ".madecoin")
WALLET_FILE = os.path.join(DATA_DIR, "wallet.json")


def create_app(blockchain: Blockchain, miner, p2p, wallet_ref: list) -> Flask:
    """wallet_ref is a mutable list [wallet_or_None] so endpoints can swap it."""
    app = Flask(__name__)
    CORS(app)

    def w():
        return wallet_ref[0]

    @app.route("/")
    def dashboard():
        return send_file(DASHBOARD)

    @app.route("/api/info")
    def info():
        cur = w()
        return jsonify({
            "coin": "M.A.D.E. Coin", "ticker": "MADE", "version": "0.9.1-testnet",
            "height": blockchain.height, "last_hash": blockchain.last_block.hash,
            "difficulty": blockchain.difficulty,
            "block_reward": blockchain.get_block_reward(),
            "mempool_size": len(blockchain.pending_transactions),
            "peers": len(p2p.peers) if p2p else 0,
            "mining": miner.running if miner else False,
            "hashrate": miner.status()["hashrate"] if miner else "0 H/s",
            "wallet_exists": cur is not None,
        })

    @app.route("/api/blocks")
    def get_blocks():
        limit  = min(int(request.args.get("limit", 20)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
        blocks = list(reversed(blockchain.chain))[offset:offset + limit]
        return jsonify({"blocks": [b.to_dict() for b in blocks],
                        "total": len(blockchain.chain), "height": blockchain.height})

    @app.route("/api/block/<identifier>")
    def get_block(identifier):
        if identifier.isdigit():
            idx = int(identifier)
            if 0 <= idx < len(blockchain.chain):
                return jsonify(blockchain.chain[idx].to_dict())
        for b in reversed(blockchain.chain):
            if b.hash == identifier or b.hash.startswith(identifier):
                return jsonify(b.to_dict())
        return jsonify({"error": "Block not found"}), 404

    @app.route("/api/mempool")
    def mempool():
        return jsonify({"transactions": [t.to_dict() for t in blockchain.pending_transactions],
                        "count": len(blockchain.pending_transactions)})

    @app.route("/api/transaction", methods=["POST"])
    def submit_tx():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No JSON body"}), 400
        for field in ("sender", "recipient", "amount", "signature", "public_key_hex"):
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400
        try:
            vk = vk_from_hex(data["public_key_hex"])
            dummy = Transaction(data["sender"], data["recipient"], data["amount"])
            if not verify(vk, dummy.signing_data(), data["signature"]):
                return jsonify({"error": "Invalid signature"}), 400
        except Exception as e:
            return jsonify({"error": f"Signature error: {e}"}), 400
        tx = Transaction(sender=data["sender"], recipient=data["recipient"],
                         amount=data["amount"], public_key_hex=data["public_key_hex"],
                         signature=data["signature"])
        ok, msg = blockchain.add_transaction(tx)
        if not ok:
            return jsonify({"error": msg}), 400
        if p2p:
            p2p.broadcast_transaction(tx)
        return jsonify({"success": True, "tx_id": tx.tx_id})

    @app.route("/api/address/<address>")
    def address_info(address):
        txs = []
        for b in blockchain.chain:
            for tx in b.transactions:
                if tx.sender == address or tx.recipient == address:
                    d = tx.to_dict()
                    d["block_height"] = b.index
                    txs.append(d)
        txs.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify({"address": address, "balance": blockchain.get_balance(address),
                        "tx_count": len(txs), "transactions": txs[:50]})

    @app.route("/api/wallet")
    def wallet_info():
        cur = w()
        if not cur:
            return jsonify({"exists": False})
        return jsonify({
            "exists": True,
            "address": cur.address,
            "balance": blockchain.get_balance(cur.address),
            "public_key_hex": cur.public_key_hex,
        })

    @app.route("/api/wallet/export")
    def wallet_export():
        """Export private key - only called when user explicitly requests it."""
        cur = w()
        if not cur:
            return jsonify({"error": "No wallet"}), 404
        return jsonify({"private_key_wif": cur.to_dict()["private_key_wif"]})

    @app.route("/api/wallet/new", methods=["POST"])
    def wallet_new():
        """Generate a brand-new wallet - only called on explicit user request."""
        os.makedirs(DATA_DIR, exist_ok=True)
        new_w = Wallet()
        new_w.save(WALLET_FILE)
        wallet_ref[0] = new_w
        if miner:
            miner.miner_address = new_w.address
        return jsonify({
            "exists": True,
            "address": new_w.address,
            "public_key_hex": new_w.public_key_hex,
        })

    @app.route("/api/send", methods=["POST"])
    def send():
        cur = w()
        if not cur:
            return jsonify({"error": "No wallet. Create one in the dashboard first."}), 400
        data = request.get_json(silent=True)
        if not data or "recipient" not in data or "amount" not in data:
            return jsonify({"error": "Need recipient and amount"}), 400
        try:
            amount = float(data["amount"])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount"}), 400
        tx = Transaction(sender=cur.address, recipient=data["recipient"],
                         amount=amount, public_key_hex=cur.public_key_hex)
        tx.signature = cur.sign(tx.signing_data())
        ok, msg = blockchain.add_transaction(tx)
        if not ok:
            return jsonify({"error": msg}), 400
        if p2p:
            p2p.broadcast_transaction(tx)
        return jsonify({"success": True, "tx_id": tx.tx_id})

    @app.route("/api/mining/status")
    def mining_status():
        return jsonify(miner.status() if miner else {"running": False})

    @app.route("/api/mining/start", methods=["POST"])
    def start_mining():
        if not miner:
            return jsonify({"error": "No miner"}), 400
        cur = w()
        if not cur:
            return jsonify({"error": "Create a wallet first before mining."}), 400
        miner.start()
        return jsonify({"success": True})

    @app.route("/api/mining/stop", methods=["POST"])
    def stop_mining():
        if not miner:
            return jsonify({"error": "No miner"}), 400
        miner.stop()
        return jsonify({"success": True})

    @app.route("/api/peers")
    def get_peers():
        return jsonify({"peers": list(p2p.peers) if p2p else []})

    @app.route("/api/peers", methods=["POST"])
    def add_peer():
        data = request.get_json(silent=True)
        if not data or "peer" not in data:
            return jsonify({"error": "Need peer field"}), 400
        if p2p:
            p2p.add_peer(data["peer"])
            p2p.sync_with_peer(data["peer"])
        return jsonify({"success": True})

    return app
