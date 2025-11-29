import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crypto import NodeKey
from consensus import ConsensusState, Vote, BlockHeader

class TestVoteValidation(unittest.TestCase):
    def setUp(self):
        self.chain_id = "test-chain"
        
        # Create 4 validators
        self.validators = []
        self.validator_keys = []
        for i in range(4):
            key = NodeKey()
            self.validator_keys.append(key)
            self.validators.append(key.get_public_key_hex())
        
        self.consensus = ConsensusState(set(self.validators), self.chain_id)
    
    def test_valid_prevote(self):
        vote = Vote(
            validator=self.validators[0],
            height=1,
            block_hash="a" * 64,
            phase="prevote",
            signature=""
        )
        vote.signature = self.validator_keys[0].sign(
            vote.encode(), "VOTE", self.chain_id
        )
        
        result = self.consensus.handle_vote(vote)
        
        self.assertTrue(result)
        self.assertEqual(len(self.consensus.prevotes[1]), 1)
    
    def test_valid_precommit(self):
        vote = Vote(
            validator=self.validators[0],
            height=1,
            block_hash="a" * 64,
            phase="precommit",
            signature=""
        )
        vote.signature = self.validator_keys[0].sign(
            vote.encode(), "VOTE", self.chain_id
        )
        
        result = self.consensus.handle_vote(vote)
        
        self.assertTrue(result)
        self.assertEqual(len(self.consensus.precommits[1]), 1)
    
    def test_invalid_signature(self):
        vote = Vote(
            validator=self.validators[0],
            height=1,
            block_hash="a" * 64,
            phase="prevote",
            signature="invalid_signature"
        )
        
        result = self.consensus.handle_vote(vote)
        
        self.assertFalse(result)
        self.assertEqual(len(self.consensus.prevotes.get(1, [])), 0)
    
    def test_wrong_validator_signature(self):
        vote = Vote(
            validator=self.validators[0],
            height=1,
            block_hash="a" * 64,
            phase="prevote",
            signature=""
        )
        vote.signature = self.validator_keys[1].sign(
            vote.encode(), "VOTE", self.chain_id
        )
        
        result = self.consensus.handle_vote(vote)
        
        self.assertFalse(result)
    
    def test_non_validator_vote(self):
        non_validator_key = NodeKey()
        non_validator_pub = non_validator_key.get_public_key_hex()
        
        vote = Vote(
            validator=non_validator_pub,
            height=1,
            block_hash="a" * 64,
            phase="prevote",
            signature=""
        )
        vote.signature = non_validator_key.sign(
            vote.encode(), "VOTE", self.chain_id
        )
        
        result = self.consensus.handle_vote(vote)
        
        self.assertFalse(result)


class TestVoteCounting(unittest.TestCase):
    def setUp(self):
        self.chain_id = "test-chain"
        
        # Create 5 validators (need 3 for majority)
        self.validators = []
        self.validator_keys = []
        for i in range(5):
            key = NodeKey()
            self.validator_keys.append(key)
            self.validators.append(key.get_public_key_hex())
        
        self.consensus = ConsensusState(set(self.validators), self.chain_id)
        self.block_hash = "a" * 64
    
    def test_no_finalization_without_majority(self):
        # Only 2 out of 5 validators precommit (need 3)
        for i in range(2):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=self.block_hash,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        finalized = self.consensus.try_finalize(1)
        
        self.assertIsNone(finalized)
        self.assertNotIn(1, self.consensus.finalized_blocks)
    
    def test_finalization_with_majority(self):
        # 3 out of 5 validators precommit (strict majority)
        for i in range(3):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=self.block_hash,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        finalized = self.consensus.try_finalize(1)
        
        self.assertEqual(finalized, self.block_hash)
        self.assertEqual(self.consensus.finalized_blocks[1], self.block_hash)
    
    def test_finalization_with_supermajority(self):
        # All 5 validators precommit
        for i in range(5):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=self.block_hash,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        finalized = self.consensus.try_finalize(1)
        
        self.assertEqual(finalized, self.block_hash)


class TestConsensusLogic(unittest.TestCase):
    def setUp(self):
        self.chain_id = "test-chain"
        
        # Create 4 validators (need 3 for majority)
        self.validators = []
        self.validator_keys = []
        for i in range(4):
            key = NodeKey()
            self.validator_keys.append(key)
            self.validators.append(key.get_public_key_hex())
        
        self.consensus = ConsensusState(set(self.validators), self.chain_id)
    
    def test_prevote_phase_separate_from_precommit(self):
        block_hash = "a" * 64
        
        # All validators prevote
        for i in range(4):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=block_hash,
                phase="prevote",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        # Block should not be finalized (no precommits yet)
        self.assertNotIn(1, self.consensus.finalized_blocks)
        
        # Now send precommits
        for i in range(3):  # Majority
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=block_hash,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        # Now block should be finalized
        self.assertEqual(self.consensus.finalized_blocks[1], block_hash)
    
    def test_conflicting_block_safety_violation(self):
        block_hash_1 = "a" * 64
        block_hash_2 = "b" * 64
        
        # Finalize first block
        for i in range(3):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=block_hash_1,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        self.assertEqual(self.consensus.finalized_blocks[1], block_hash_1)
        
        # Try to finalize conflicting block
        consensus2 = ConsensusState(set(self.validators), self.chain_id)
        consensus2.finalized_blocks[1] = block_hash_1  # Set previous finalization
        
        # Add votes directly to precommits to avoid automatic try_finalize call
        for i in range(3):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=block_hash_2,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            # Add directly to precommits instead of using handle_vote
            consensus2.precommits.setdefault(1, []).append(vote)
        
        # Should raise safety violation when try_finalize is called
        with self.assertRaises(Exception) as context:
            consensus2.try_finalize(1)
        
        self.assertIn("SAFETY VIOLATION", str(context.exception))
    
    def test_different_heights_independent(self):
        block_hash_1 = "a" * 64
        block_hash_2 = "b" * 64
        
        # Finalize block at height 1
        for i in range(3):
            vote = Vote(
                validator=self.validators[i],
                height=1,
                block_hash=block_hash_1,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        # Finalize different block at height 2
        for i in range(3):
            vote = Vote(
                validator=self.validators[i],
                height=2,
                block_hash=block_hash_2,
                phase="precommit",
                signature=""
            )
            vote.signature = self.validator_keys[i].sign(
                vote.encode(), "VOTE", self.chain_id
            )
            self.consensus.handle_vote(vote)
        
        # Both should be finalized
        self.assertEqual(self.consensus.finalized_blocks[1], block_hash_1)
        self.assertEqual(self.consensus.finalized_blocks[2], block_hash_2)


if __name__ == '__main__':
    unittest.main()
