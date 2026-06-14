"""
M.A.D.E. Coin — P2P Network
TCP sockets | JSON protocol | longest-chain rule
"""

import json
import socket
import threading
from typing import Callable, List, Set
from blockchain import Blockchain, Block, Transaction

DEFAULT_PORT = 19333
RECV_LIMIT   = 16 * 1024 * 1024   # 16 MB


class P2PNode:
    def __init__(self, blockchain: Blockchain, port: int = DEFAULT_PORT):
        self.blockchain = blockchain
        self.port       = port
        self.peers: Set[str] = set()   # "host:port"
        self._running   = False
        self._server_thread: threading.Thread = None
        self._block_callbacks: List[Callable] = []

    def on_new_block(self, cb: Callable[[Block], None]):
        self._block_callbacks.append(cb)

    # ── server ────────────────────────────────────────────────────────────────

    def start_server(self):
        self._running = True
        self._server_thread = threading.Thread(
            target=self._serve, daemon=True, name="P2PServer"
        )
        self._server_thread.start()
        print(f"[p2p] Listening on port {self.port}")

    def _serve(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("0.0.0.0", self.port))
        except OSError as e:
            print(f"[p2p] Cannot bind port {self.port}: {e}")
            return
        srv.listen(20)
        srv.settimeout(1.0)
        while self._running:
            try:
                conn, addr = srv.accept()
                threading.Thread(
                    target=self._handle, args=(conn,), daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception:
                continue
        srv.close()

    def _handle(self, conn: socket.socket):
        try:
            data = b""
            conn.settimeout(10)
            while len(data) < RECV_LIMIT:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            if data:
                msg = json.loads(data.decode())
                reply = self._dispatch(msg)
                if reply:
                    conn.sendall(json.dumps(reply).encode())
        except Exception:
            pass
        finally:
            conn.close()

    # ── message dispatch ──────────────────────────────────────────────────────

    def _dispatch(self, msg: dict) -> dict:
        t = msg.get("type")

        if t == "ping":
            return {"type": "pong", "height": self.blockchain.height}

        if t == "get_chain":
            return {
                "type":       "chain",
                "difficulty": self.blockchain.difficulty,
                "chain":      [b.to_dict() for b in self.blockchain.chain],
            }

        if t == "new_block":
            block = Block.from_dict(msg["block"])
            ok, reason = self.blockchain.add_block(block)
            if ok:
                for cb in self._block_callbacks:
                    cb(block)
            return {"type": "ack", "ok": ok, "reason": reason}

        if t == "new_transaction":
            tx = Transaction.from_dict(msg["transaction"])
            ok, reason = self.blockchain.add_transaction(tx)
            return {"type": "ack", "ok": ok, "reason": reason}

        if t == "get_peers":
            return {"type": "peers", "peers": list(self.peers)}

        return {"type": "error", "message": "Unknown type"}

    # ── outbound ──────────────────────────────────────────────────────────────

    def _send(self, peer: str, msg: dict) -> dict:
        host, port = peer.rsplit(":", 1)
        try:
            with socket.create_connection((host, int(port)), timeout=5) as s:
                s.sendall(json.dumps(msg).encode())
                data = b""
                s.settimeout(10)
                while len(data) < RECV_LIMIT:
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                return json.loads(data.decode()) if data else {}
        except Exception:
            return {}

    def add_peer(self, peer: str):
        if peer and peer not in self.peers:
            self.peers.add(peer)
            print(f"[p2p] Peer added: {peer}")

    def broadcast_block(self, block: Block):
        msg = {"type": "new_block", "block": block.to_dict()}
        for peer in list(self.peers):
            self._send(peer, msg)

    def broadcast_transaction(self, tx: Transaction):
        msg = {"type": "new_transaction", "transaction": tx.to_dict()}
        for peer in list(self.peers):
            self._send(peer, msg)

    def sync_with_peer(self, peer: str) -> bool:
        """Pull the longer chain from a peer (longest-chain rule)."""
        info = self._send(peer, {"type": "ping"})
        if not info or info.get("height", 0) <= self.blockchain.height:
            return False

        data = self._send(peer, {"type": "get_chain"})
        if not data or "chain" not in data:
            return False

        new_chain = [Block.from_dict(b) for b in data["chain"]]
        if len(new_chain) <= len(self.blockchain.chain):
            return False

        # Validate every link
        for i in range(1, len(new_chain)):
            curr = new_chain[i]
            prev = new_chain[i - 1]
            if curr.previous_hash != prev.hash:
                print(f"[p2p] Sync failed: bad link at {i}")
                return False
            if curr.hash != curr.compute_hash():
                print(f"[p2p] Sync failed: bad hash at {i}")
                return False
            if not curr.hash.startswith("0" * curr.difficulty):
                print(f"[p2p] Sync failed: bad PoW at {i}")
                return False

        self.blockchain.chain      = new_chain
        self.blockchain.difficulty = data.get("difficulty", 4)
        print(f"[p2p] Synced from {peer}: height={self.blockchain.height}")
        return True

    def sync_all(self):
        for peer in list(self.peers):
            self.sync_with_peer(peer)

    def stop(self):
        self._running = False
