import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from crypto import CryptoUtils, Validator


@dataclass
class BlockHeader:
    parent_hash: str
    height: int
    state_hash: str
    proposer: str
    signature: str = ""  # Signature by the proposer

    def encode(self):
        return {
            "parent_hash": self.parent_hash,
            "height": self.height,
            "state_hash": self.state_hash,
            "proposer": self.proposer,
        }

    @property
    def hash(self):
        return CryptoUtils.hash_data(self.encode())


@dataclass
class Vote:
    validator: str
    height: int
    block_hash: str
    phase: str  # "prevote" or "precommit"
    signature: str

    def encode(self):
        return {
            "validator": self.validator,
            "height": self.height,
            "block_hash": self.block_hash,
            "phase": self.phase,
        }

class ConsensusState:
    def __init__(self, validator_set: Set[str], chain_id: str):
        self.validator_set = validator_set
        self.chain_id = chain_id

        self.prevotes: Dict[int, List[Vote]] = {}
        self.precommits: Dict[int, List[Vote]] = {}
        self.finalized_blocks: Dict[int, str] = {}  # height -> block_hash

    def handle_vote(self, vote: Vote) -> bool:
        # Verify signature
        if vote.validator not in self.validator_set:
            return False

        if not Validator.verify(
                public_key_hex=vote.validator,
                signature_hex=vote.signature,
                message=vote.encode(),
                context="VOTE",
                chain_id=self.chain_id,
        ):
            return False

        # Store vote
        if vote.phase == "prevote":
            self.prevotes.setdefault(vote.height, []).append(vote)

        elif vote.phase == "precommit":
            self.precommits.setdefault(vote.height, []).append(vote)
            self.try_finalize(vote.height)

        return True

    def try_finalize(self, height: int) -> Optional[str]:
        votes = self.precommits.get(height, [])
        if not votes:
            # If already finalized, return it
            if height in self.finalized_blocks:
                return self.finalized_blocks[height]
            return None

        # Count votes by block_hash
        tally = {}
        for v in votes:
            tally.setdefault(v.block_hash, 0)
            tally[v.block_hash] += 1

        majority = len(self.validator_set) // 2 + 1

        # Find if any block has majority
        for bh, count in tally.items():
            if count >= majority:
                # safety: ensure no previous commitment at this height
                prev = self.finalized_blocks.get(height)
                if prev and prev != bh:
                    raise Exception(f"SAFETY VIOLATION: conflicting block at height {height}")

                self.finalized_blocks[height] = bh
                return bh

        # If already finalized but no majority for different block, return it
        if height in self.finalized_blocks:
            return self.finalized_blocks[height]

        return None
