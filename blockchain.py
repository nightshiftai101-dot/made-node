"""
M.A.D.E. Coin — Blockchain Core
SHA-256 Proof-of-Work | 60s blocks | 5 MADE reward | 100M max supply
"""

import hashlib
import json
import os
import time
from typing import List, Optional, Tuple

BLOCK_REWARD       = 5.0
HALVING_INTERVAL   = 2_100_000      # blocks (~4 years at 60s/block)
TARGET_BLOCK_TIME  = 300             # seconds
DIFF_ADJUST_EVERY  = 10             # blocks (every ~50 min at 5 min target)             # blocks (fast adaptation for solo mining)
INITIAL_DIFFICULTY = 26             # leading zero BITS (2^26 = ~67M expected hashes, ~2-5 min on avg CPU)
MAX_SUPPLY         = 100_000_000.0
MAX_TX_PER_BLOCK   = 100

_MAX_HASH = 2 ** 256


def _meets_target(hash_hex: str, difficulty: int) -> bool:
    """True if hash_hex < 2^256 >> difficulty (bit-based PoW)."""
    return int(hash_hex, 16) < (_MAX_HASH >> difficulty)


class Transaction:
    def __init__(self, sender: str, recipient: str, amount: float,
                 public_key_hex: str = "", signature: str = "",
                 tx_id: str = "", timestamp: float = None):
        self.sender        = sender
        self.recipient     = recipient
        self.amount        = round(float(amount), 8)
        self.public_key_hex = public_key_hex
        self.signature     = signature
        self.timestamp     = timestamp if timestamp is not None else time.time()
        self.tx_id         = tx_id or self._make_id()

    def _make_id(self) -> str:
        raw = f"{self.sender}:{self.recipient}:{self.amount}:{self.timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def signing_data(self) -> str:
        """Canonical string that is signed / verified."""
        return f"{self.sender}:{self.recipient}:{self.amount}"

    def to_dict(self) -> dict:
        return {
            "tx_id":          self.tx_id,
            "sender":         self.sender,
            "recipient":      self.recipient,
            "amount":         self.amount,
            "public_key_hex": self.public_key_hex,
            "signature":      self.signature,
            "timestamp":      self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(
            sender=d["sender"],
            recipient=d["recipient"],
            amount=d["amount"],
            public_key_hex=d.get("public_key_hex", ""),
            signature=d.get("signature", ""),
            tx_id=d.get("tx_id", ""),
            timestamp=d.get("timestamp"),
        )


class Block:
    def __init__(self, index: int, transactions: List[Transaction],
                 previous_hash: str, miner: str, difficulty: int,
                 nonce: int = 0, timestamp: float = None):
        self.index         = index
        self.transactions  = transactions
        self.previous_hash = previous_hash
        self.miner         = miner
        self.difficulty    = difficulty
        self.nonce         = nonce
        self.timestamp     = timestamp if timestamp is not None else time.time()
        self.hash          = self.compute_hash()

    def compute_hash(self) -> str:
        payload = json.dumps({
            "index":         self.index,
            "transactions":  [t.to_dict() for t in self.transactions],
            "previous_hash": self.previous_hash,
            "miner":         self.miner,
            "nonce":         self.nonce,
            "timestamp":     self.timestamp,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index":         self.index,
            "hash":          self.hash,
            "previous_hash": self.previous_hash,
            "miner":         self.miner,
            "difficulty":    self.difficulty,
            "nonce":         self.nonce,
            "timestamp":     self.timestamp,
            "tx_count":      len(self.transactions),
            "transactions":  [t.to_dict() for t in self.transactions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        txs = [Transaction.from_dict(t) for t in d.get("transactions", [])]
        b = cls(
            index=d["index"],
            transactions=txs,
            previous_hash=d["previous_hash"],
            miner=d["miner"],
            difficulty=d["difficulty"],
            nonce=d["nonce"],
            timestamp=d["timestamp"],
        )
        b.hash = d["hash"]
        return b


class Blockchain:
    def __init__(self):
        self.chain:                List[Block]       = []
        self.pending_transactions: List[Transaction] = []
        self.difficulty: int = INITIAL_DIFFICULTY
        self._create_genesis()

    # ── genesis ──────────────────────────────────────────────
    def _create_genesis(self):
        genesis_tx = Transaction("COINBASE", "GENESIS", 0.0, timestamp=1_700_000_000.0)
        genesis = Block(
            index=0,
            transactions=[genesis_tx],
            previous_hash="0" * 64,
            miner="GENESIS",
            difficulty=1,
            nonce=0,
            timestamp=1_700_000_000.0,
        )
        self.chain.append(genesis)

    # ── properties ───────────────────────────────────────────
    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @property
    def height(self) -> int:
        return len(self.chain) - 1

    # ── rewards & difficulty ──────────────────────────────────
    def get_block_reward(self) -> float:
        halvings = self.height // HALVING_INTERVAL
        reward = BLOCK_REWARD / (2 ** halvings)
        return round(reward, 8)

    def _adjust_difficulty(self):
        """Adjust difficulty every DIFF_ADJUST_EVERY blocks.
        Uses bit-based difficulty: each ±1 step doubles/halves the expected work."""
        if self.height > 0 and self.height % DIFF_ADJUST_EVERY == 0:
            window   = self.chain[-DIFF_ADJUST_EVERY:]
            elapsed  = window[-1].timestamp - window[0].timestamp
            expected = TARGET_BLOCK_TIME * DIFF_ADJUST_EVERY
            ratio    = elapsed / expected if expected > 0 else 1.0

            # Clamp to ±3 bits per adjustment window to avoid wild swings
            if ratio < 0.5:
                delta = min(3, max(1, int(1 / ratio)))
                self.difficulty = min(self.difficulty + delta, 64)
            elif ratio > 2.0:
                delta = min(3, max(1, int(ratio)))
                self.difficulty = max(self.difficulty - delta, 1)
            # Within 0.5–2.0× of target: no change needed

    # ── balances ─────────────────────────────────────────────
    def get_balance(self, address: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.recipient == address:
                    balance += tx.amount
                if tx.sender == address:
                    balance -= tx.amount
        return round(balance, 8)

    # ── mempool ───────────────────────────────────────────────
    def add_transaction(self, tx: Transaction) -> Tuple[bool, str]:
        if tx.sender == "COINBASE":
            return False, "Cannot submit coinbase transaction"
        if tx.amount <= 0:
            return False, "Amount must be positive"
        if any(p.tx_id == tx.tx_id for p in self.pending_transactions):
            return False, "Transaction already in mempool"
        balance = self.get_balance(tx.sender)
        if balance < tx.amount:
            return False, f"Insufficient balance ({balance} MADE)"
        self.pending_transactions.append(tx)
        return True, "Transaction added to mempool"

    # ── block creation ────────────────────────────────────────
    def create_candidate_block(self, miner_address: str) -> Block:
        coinbase = Transaction("COINBASE", miner_address, self.get_block_reward())
        txs = [coinbase] + self.pending_transactions[:MAX_TX_PER_BLOCK]
        return Block(
            index=self.height + 1,
            transactions=txs,
            previous_hash=self.last_block.hash,
            miner=miner_address,
            difficulty=self.difficulty,
        )

    def add_block(self, block: Block) -> Tuple[bool, str]:
        if block.previous_hash != self.last_block.hash:
            return False, "Previous hash mismatch"
        if block.index != self.height + 1:
            return False, f"Index mismatch (expected {self.height + 1})"
        if block.hash != block.compute_hash():
            return False, "Block hash is invalid"
        if not _meets_target(block.hash, block.difficulty):
            return False, "Proof-of-work not satisfied"
        self.chain.append(block)
        mined_ids = {t.tx_id for t in block.transactions}
        self.pending_transactions = [
            t for t in self.pending_transactions if t.tx_id not in mined_ids
        ]
        self._adjust_difficulty()
        return True, "Block accepted"

    # ── validation ────────────────────────────────────────────
    def is_valid(self) -> Tuple[bool, str]:
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]
            if curr.previous_hash != prev.hash:
                return False, f"Bad prev_hash at block {i}"
            if curr.hash != curr.compute_hash():
                return False, f"Bad hash at block {i}"
            if not _meets_target(curr.hash, curr.difficulty):
                return False, f"Bad PoW at block {i}"
        return True, "Chain is valid"

    # ── persistence ───────────────────────────────────────────
    def save(self, filepath: str):
        tmp = filepath + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"difficulty": self.difficulty,
                       "chain": [b.to_dict() for b in self.chain]}, f)
        os.replace(tmp, filepath)

    @classmethod
    def load(cls, filepath: str) -> "Blockchain":
        with open(filepath) as f:
            data = json.load(f)
        bc = cls.__new__(cls)
        bc.chain = [Block.from_dict(b) for b in data["chain"]]
        bc.difficulty = data.get("difficulty", INITIAL_DIFFICULTY)
        bc.pending_transactions = []
        return bc

    @classmethod
    def load_or_create(cls, filepath: str) -> "Blockchain":
        if os.path.exists(filepath):
            bc = cls.load(filepath)
            print(f"[blockchain] Loaded {bc.height + 1} blocks from {filepath}")
            return bc
        bc = cls()
        bc.save(filepath)
        print(f"[blockchain] New chain created (genesis block)")
        return bc
