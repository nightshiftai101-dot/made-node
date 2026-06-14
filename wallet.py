"""
M.A.D.E. Coin - Wallet
ECDSA secp256k1 keys | MADE-prefixed addresses
"""

import hashlib
import json
import os
import base64
import ecdsa

CURVE = ecdsa.SECP256k1


def generate_keypair():
    sk = ecdsa.SigningKey.generate(curve=CURVE)
    vk = sk.get_verifying_key()
    return sk, vk


def public_key_to_address(vk: ecdsa.VerifyingKey) -> str:
    pub_bytes = vk.to_string()
    step1 = hashlib.sha256(pub_bytes).digest()
    step2 = hashlib.new("ripemd160", step1).hexdigest()
    return "MADE" + step2.upper()


def sk_to_wif(sk: ecdsa.SigningKey) -> str:
    return base64.urlsafe_b64encode(sk.to_string()).decode()


def wif_to_sk(wif: str) -> ecdsa.SigningKey:
    return ecdsa.SigningKey.from_string(
        base64.urlsafe_b64decode(wif.encode()), curve=CURVE
    )


def sign(sk: ecdsa.SigningKey, data: str) -> str:
    sig = sk.sign(data.encode(), hashfunc=hashlib.sha256)
    return sig.hex()


def verify(vk: ecdsa.VerifyingKey, data: str, sig_hex: str) -> bool:
    try:
        vk.verify(bytes.fromhex(sig_hex), data.encode(), hashfunc=hashlib.sha256)
        return True
    except ecdsa.BadSignatureError:
        return False


def vk_from_hex(hex_str: str) -> ecdsa.VerifyingKey:
    return ecdsa.VerifyingKey.from_string(bytes.fromhex(hex_str), curve=CURVE)


class Wallet:
    def __init__(self, sk: ecdsa.SigningKey = None):
        if sk is None:
            sk, _ = generate_keypair()
        self.sk = sk
        self.vk = sk.get_verifying_key()
        self.address = public_key_to_address(self.vk)

    @property
    def public_key_hex(self) -> str:
        return self.vk.to_string().hex()

    def sign(self, data: str) -> str:
        return sign(self.sk, data)

    def to_dict(self) -> dict:
        return {
            "address":         self.address,
            "public_key_hex":  self.public_key_hex,
            "private_key_wif": sk_to_wif(self.sk),
        }

    def save(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "Wallet":
        with open(filepath) as f:
            data = json.load(f)
        return cls(wif_to_sk(data["private_key_wif"]))

    @classmethod
    def load_only(cls, filepath: str):
        """Load wallet if it exists; return None if it does not (no auto-create)."""
        if not os.path.exists(filepath):
            return None
        return cls.load(filepath)

    @classmethod
    def load_or_create(cls, filepath: str) -> "Wallet":
        """Legacy helper - kept for compatibility."""
        if os.path.exists(filepath):
            return cls.load(filepath)
        w = cls()
        w.save(filepath)
        return w
