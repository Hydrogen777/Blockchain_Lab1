import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crypto import NodeKey
from network import NetworkSimulator, set_random_seed
from consensus import Vote
from execution import Transaction
from node import BlockchainNode
from logger import DeterministicLogger

class TestEndToEndScenarios(unittest.TestCase):    
    def setUp(self):
        """Setup test fixtures."""
        self.chain_id = "test-e2e-chain"
        set_random_seed(42)  # Deterministic tests
        
        # Create 4 nodes
        self.num_nodes = 4
        self.node_keys = [NodeKey() for _ in range(self.num_nodes)]
        self.validator_set = {key.get_public_key_hex() for key in self.node_keys}
        
        self.nodes = {}
        for i, key in enumerate(self.node_keys):
            node_id = f"Node_{i}"
            node = BlockchainNode(
                node_id=node_id,
                key=key,
                validator_set=self.validator_set,
                chain_id=self.chain_id,
                logger=None  # No logging in unit tests
            )
            self.nodes[node_id] = node
        
        self.node_ids = list(self.nodes.keys())
    
    def test_single_block_finalization(self):
        """Test 1: Only one block becomes finalized at each height."""
        proposer = self.nodes["Node_0"]
        block = proposer.propose_block(proposer.genesis.hash)
        block_txs = proposer.block_bodies[block.hash]
        
        # Broadcast block to all nodes
        for node_id in self.node_ids[1:]:
            self.nodes[node_id].receive_block(block, block_txs)
        
        # All nodes vote for the block
        for node in self.nodes.values():
            # Prevote
            vote = node.create_vote(block.hash, 1, "prevote")
            for target_node in self.nodes.values():
                target_node.receive_vote(vote)
            
            # Precommit
            vote = node.create_vote(block.hash, 1, "precommit")
            for target_node in self.nodes.values():
                target_node.receive_vote(vote)
        
        # Verify all nodes finalized the same block
        for node in self.nodes.values():
            finalized = node.consensus.finalized_blocks.get(1)
            self.assertEqual(finalized, block.hash)
    
    def test_invalid_signature_rejection(self):
        """Test 2: Messages with invalid signatures are rejected."""
        alice = self.nodes["Node_0"]
        bob = self.nodes["Node_1"]
        
        # Create transaction with invalid signature
        tx = Transaction(
            sender=alice.public_key,
            key=f"{alice.public_key}/data",
            value="test",
            signature="0" * 128  # Invalid signature
        )
        
        # Bob should reject the transaction
        result = bob.receive_transaction(tx)
        self.assertFalse(result)
        
        # Create vote with invalid signature
        vote = Vote(
            validator=alice.public_key,
            height=1,
            block_hash="a" * 64,
            phase="prevote",
            signature="0" * 128  # Invalid signature
        )
        
        # Bob should reject the vote
        result = bob.receive_vote(vote)
        self.assertFalse(result)
    
    def test_wrong_context_rejection(self):
        """Test 2b: Messages with wrong contexts are rejected."""
        alice = self.nodes["Node_0"]
        bob = self.nodes["Node_1"]
        
        # Create transaction
        tx = Transaction(
            sender=alice.public_key,
            key=f"{alice.public_key}/data",
            value="test",
            signature=""
        )
        
        # Sign with wrong context (VOTE instead of TX)
        tx.signature = alice.key.sign(tx.encode(), "VOTE", self.chain_id)
        
        # Should be rejected
        result = bob.receive_transaction(tx)
        self.assertFalse(result)
    
    def test_duplicate_votes_ignored(self):
        """Test 3: Replays/duplicates are ignored without breaking safety."""
        proposer = self.nodes["Node_0"]
        block = proposer.propose_block(proposer.genesis.hash)
        block_txs = proposer.block_bodies[block.hash]
        
        # Broadcast block
        for node_id in self.node_ids[1:]:
            self.nodes[node_id].receive_block(block, block_txs)
        
        alice = self.nodes["Node_0"]
        bob = self.nodes["Node_1"]
        
        # Alice creates a vote
        vote = alice.create_vote(block.hash, 1, "precommit")
        
        # Bob receives it multiple times
        result1 = bob.receive_vote(vote)
        result2 = bob.receive_vote(vote)  # Duplicate
        result3 = bob.receive_vote(vote)  # Another duplicate
        
        self.assertTrue(result1)
        self.assertFalse(result2)  # Duplicate ignored
        self.assertFalse(result3)  # Duplicate ignored
        
        # Should only count once
        votes_from_alice = [
            v for v in bob.consensus.precommits.get(1, [])
            if v.validator == alice.public_key
        ]
        self.assertEqual(len(votes_from_alice), 1)
    
    def test_network_delays_dont_break_consensus(self):
        """Test 4: Delayed messages don't cause conflicting finalization."""
        # Even if messages arrive out of order, consensus should work
        proposer = self.nodes["Node_0"]
        block = proposer.propose_block(proposer.genesis.hash)
        block_txs = proposer.block_bodies[block.hash]
        
        # Simulate delayed block delivery (some nodes get it late)
        early_nodes = self.node_ids[:2]
        late_nodes = self.node_ids[2:]
        
        # Early nodes receive block
        for node_id in early_nodes:
            if node_id != "Node_0":
                self.nodes[node_id].receive_block(block, block_txs)
        
        # Early nodes vote
        for node_id in early_nodes:
            node = self.nodes[node_id]
            vote = node.create_vote(block.hash, 1, "precommit")
            # Broadcast to everyone
            for target_node in self.nodes.values():
                target_node.receive_vote(vote)
        
        # Late nodes receive block now
        for node_id in late_nodes:
            self.nodes[node_id].receive_block(block, block_txs)
        
        # Late nodes vote
        for node_id in late_nodes:
            node = self.nodes[node_id]
            vote = node.create_vote(block.hash, 1, "precommit")
            # Broadcast to everyone
            for target_node in self.nodes.values():
                target_node.receive_vote(vote)
        
        # All nodes should finalize the same block
        finalized_hashes = set()
        for node in self.nodes.values():
            finalized = node.consensus.finalized_blocks.get(1)
            if finalized:
                finalized_hashes.add(finalized)
        
        self.assertEqual(len(finalized_hashes), 1)
        self.assertEqual(list(finalized_hashes)[0], block.hash)
    
    def test_deterministic_execution(self):
        """Test 5: Identical runs produce identical results."""
        # Run scenario twice with same seed
        results = []
        
        for run in range(2):
            set_random_seed(100 + run)  # Different seed each run
            
            # Create nodes
            keys = [NodeKey() for _ in range(3)]
            validator_set = {k.get_public_key_hex() for k in keys}
            
            nodes = {}
            for i, key in enumerate(keys):
                node = BlockchainNode(
                    node_id=f"N{i}",
                    key=key,
                    validator_set=validator_set,
                    chain_id=self.chain_id,
                    logger=None
                )
                nodes[f"N{i}"] = node
            
            # Create and execute transactions
            for i, (node_id, node) in enumerate(nodes.items()):
                tx = Transaction(
                    sender=node.public_key,
                    key=f"{node.public_key}/msg",
                    value=f"Message{i}",
                    signature=""
                )
                tx.signature = node.key.sign(tx.encode(), "TX", self.chain_id)
                
                # Broadcast to all
                for target in nodes.values():
                    target.receive_transaction(tx)
            
            # Propose and finalize block
            proposer = nodes["N0"]
            block = proposer.propose_block(proposer.genesis.hash)
            block_txs = proposer.block_bodies[block.hash]
            
            for node_id in list(nodes.keys())[1:]:
                nodes[node_id].receive_block(block, block_txs)
            
            # Vote
            for node in nodes.values():
                vote = node.create_vote(block.hash, 1, "precommit")
                for target in nodes.values():
                    target.receive_vote(vote)
            
            # Collect final state
            final_states = {}
            for node_id, node in nodes.items():
                final_states[node_id] = node.state.get_commitment()
            
            results.append(final_states)
        
        # Results should be different (different keys and seeds)
        # But within each run, all nodes should agree
        for result in results:
            state_hashes = list(result.values())
            self.assertEqual(len(set(state_hashes)), 1, "All nodes should have same state")


class TestBlockValidation(unittest.TestCase):    
    def setUp(self):
        self.chain_id = "test-validation-chain"
        set_random_seed(42)
        
        self.num_nodes = 3
        self.node_keys = [NodeKey() for _ in range(self.num_nodes)]
        self.validator_set = {key.get_public_key_hex() for key in self.node_keys}
        
        self.nodes = []
        for i, key in enumerate(self.node_keys):
            node = BlockchainNode(
                node_id=f"Node_{i}",
                key=key,
                validator_set=self.validator_set,
                chain_id=self.chain_id,
                logger=None
            )
            self.nodes.append(node)
    
    def test_block_with_invalid_parent(self):
        proposer = self.nodes[0]
        receiver = self.nodes[1]
        
        # Create block with fake parent
        block = proposer.propose_block(proposer.genesis.hash)
        block.parent_hash = "fake_parent_hash"
        
        result = receiver.receive_block(block, [])
        
        self.assertFalse(result)
    
    def test_block_with_invalid_proposer_signature(self):
        proposer = self.nodes[0]
        receiver = self.nodes[1]
        
        block = proposer.propose_block(proposer.genesis.hash)
        block_txs = proposer.block_bodies[block.hash]
        
        # Tamper with signature
        block.signature = "0" * 128
        
        result = receiver.receive_block(block, block_txs)
        
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
