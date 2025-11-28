import json
from dataclasses import dataclass
from crypto import CryptoUtils
from crypto import Validator
from consensus import BlockHeader


@dataclass
class Transaction:
    sender: str
    key: str
    value: str
    signature: str

    def encode(self):
        return {
            "sender": self.sender,
            "key": self.key,
            "value": self.value,
        }


# -------------------------------------------------------------------
# State object (key-value)
# -------------------------------------------------------------------
class AppState:
    def __init__(self):
        self.data = {}  # deterministic Python dict

    def apply_tx(self, tx: Transaction, chain_id: str) -> bool:
        # 1. Ensure key belongs to sender
        if not tx.key.startswith(tx.sender + "/"):
            return False

        # 2. Verify signature
        ok = Validator.verify(
            public_key_hex=tx.sender,
            signature_hex=tx.signature,
            message=tx.encode(),
            context="TX",
            chain_id=chain_id,
        )
        if not ok:
            return False

        # 3. Apply change deterministically
        self.data[tx.key] = tx.value
        return True

    def get_commitment(self) -> str:
        """Deterministic state root for block header."""
        return CryptoUtils.hash_data(self.data)

def build_block(parent_header, txs: list, proposer_key, chain_id: str):
    # 1. Execute txs on fresh state
    state = AppState()
    for tx in txs:
        if not state.apply_tx(tx, chain_id):
            print("INVALID TX rejected:", tx)
            continue

    state_hash = state.get_commitment()

    header = BlockHeader(
        parent_hash=parent_header.hash,
        height=parent_header.height + 1,
        state_hash=state_hash,
        proposer=proposer_key.get_public_key_hex(),
    )

    # 2. Sign header
    header.signature = proposer_key.sign(
        message=header.encode(),
        context="HEADER",
        chain_id=chain_id
    )

    return header, state
