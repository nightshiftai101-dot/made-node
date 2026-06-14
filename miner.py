"""
M.A.D.E. Coin — CPU Miner
SHA-256 PoW | threaded | hashrate tracking
"""

import threading
import time
from typing import Callable, Optional
from blockchain import Blockchain, Block, _meets_target, _MAX_HASH


class Miner:
    def __init__(self, blockchain: Blockchain, address: str):
        self.blockchain    = blockchain
        self.address       = address
        self._thread: Optional[threading.Thread] = None
        self._stop         = threading.Event()
        self.running       = False
        self.hashrate      = 0.0      # H/s
        self.blocks_mined  = 0
        self._on_block: Optional[Callable[[Block], None]] = None

    def on_block_mined(self, callback: Callable[[Block], None]):
        self._on_block = callback

    # ── control ───────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            print("[miner] Already running")
            return
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MinerThread")
        self._thread.start()
        print(f"[miner] Started → mining to {self.address}")

    def stop(self):
        if not self.running:
            return
        self._stop.set()
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.hashrate = 0.0
        print("[miner] Stopped")

    # ── mining loop ───────────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.is_set():
            block    = self.blockchain.create_candidate_block(self.address)
            diff     = block.difficulty
            target   = _MAX_HASH >> diff
            count    = 0
            t_start  = time.time()
            refresh  = t_start + 30       # rebuild candidate every 30 s

            while not self._stop.is_set():
                block.nonce    += 1
                block.timestamp = time.time()
                block.hash      = block.compute_hash()
                count          += 1

                elapsed = time.time() - t_start
                if elapsed > 0:
                    self.hashrate = count / elapsed

                if int(block.hash, 16) < target:
                    ok, msg = self.blockchain.add_block(block)
                    if ok:
                        self.blocks_mined += 1
                        reward = self.blockchain.get_block_reward()
                        print(
                            f"\n[BLOCK #{block.index}] "
                            f"hash={block.hash[:16]}... "
                            f"nonce={block.nonce:,} "
                            f"reward={reward} MADE "
                            f"hr={self._fmt(self.hashrate)}"
                        )
                        if self._on_block:
                            self._on_block(block)
                    break  # start fresh candidate

                # Refresh candidate to include new mempool txs
                if time.time() >= refresh:
                    break

    # ── status ────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "running":       self.running,
            "address":       self.address,
            "hashrate_hps":  round(self.hashrate, 2),
            "hashrate":      self._fmt(self.hashrate),
            "blocks_mined":  self.blocks_mined,
            "difficulty":    self.blockchain.difficulty,
        }

    @staticmethod
    def _fmt(hps: float) -> str:
        if hps >= 1_000_000:
            return f"{hps / 1_000_000:.2f} MH/s"
        if hps >= 1_000:
            return f"{hps / 1_000:.2f} KH/s"
        return f"{hps:.0f} H/s"
