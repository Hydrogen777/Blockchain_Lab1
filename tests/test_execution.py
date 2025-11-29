import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crypto import NodeKey
from execution import Transaction, AppState, build_block
from consensus import BlockHeader


class TestTransactionValidation(unittest.TestCase):    
    def setUp(self):
        self.chain_id = "test-chain"
        self.alice_key = NodeKey()
        self.alice_pub = self.alice_key.get_public_key_hex()
        self.bob_key = NodeKey()
        self.bob_pub = self.bob_key.get_public_key_hex()
        self.state = AppState()
    
    def test_valid_transaction(self):
        tx = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/message",
            value="Hello World",
            signature=""
        )
        tx.signature = self.alice_key.sign(tx.encode(), "TX", self.chain_id)
        
        result = self.state.apply_tx(tx, self.chain_id)
        
        self.assertTrue(result)
        self.assertEqual(self.state.data[tx.key], "Hello World")
    
    def test_invalid_signature(self):
        tx = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/message",
            value="Hello",
            signature="invalid_signature_hex_string"
        )
        
        result = self.state.apply_tx(tx, self.chain_id)
        
        self.assertFalse(result)
        self.assertNotIn(tx.key, self.state.data)
    
    def test_wrong_ownership(self):
        # Alice tries to modify Bob's key
        tx = Transaction(
            sender=self.alice_pub,
            key=f"{self.bob_pub}/message",  # Bob's key
            value="Malicious",
            signature=""
        )
        tx.signature = self.alice_key.sign(tx.encode(), "TX", self.chain_id)
        
        result = self.state.apply_tx(tx, self.chain_id)
        
        self.assertFalse(result, "Should not allow modifying other user's keys")
    
    def test_ownership_enforcement(self):
        # Valid: Alice modifies Alice/data
        tx1 = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/data",
            value="Alice's data",
            signature=""
        )
        tx1.signature = self.alice_key.sign(tx1.encode(), "TX", self.chain_id)
        self.assertTrue(self.state.apply_tx(tx1, self.chain_id))
        
        # Invalid: Alice modifies key not starting with her public key
        tx2 = Transaction(
            sender=self.alice_pub,
            key="global/data",
            value="Invalid",
            signature=""
        )
        tx2.signature = self.alice_key.sign(tx2.encode(), "TX", self.chain_id)
        self.assertFalse(self.state.apply_tx(tx2, self.chain_id))


class TestStateManagement(unittest.TestCase):
    def setUp(self):
        self.chain_id = "test-chain"
        self.alice_key = NodeKey()
        self.alice_pub = self.alice_key.get_public_key_hex()
    
    def test_state_commitment_deterministic(self):
        state1 = AppState()
        state2 = AppState()
        
        tx1 = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/a",
            value="value_a",
            signature=""
        )
        tx1.signature = self.alice_key.sign(tx1.encode(), "TX", self.chain_id)
        
        tx2 = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/b",
            value="value_b",
            signature=""
        )
        tx2.signature = self.alice_key.sign(tx2.encode(), "TX", self.chain_id)
        
        state1.apply_tx(tx1, self.chain_id)
        state1.apply_tx(tx2, self.chain_id)
        
        state2.apply_tx(tx2, self.chain_id)
        state2.apply_tx(tx1, self.chain_id)
        
        self.assertEqual(state1.get_commitment(), state2.get_commitment())
    
    def test_state_update_overwrite(self):
        state = AppState()
        
        tx1 = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/counter",
            value="1",
            signature=""
        )
        tx1.signature = self.alice_key.sign(tx1.encode(), "TX", self.chain_id)
        state.apply_tx(tx1, self.chain_id)
        
        self.assertEqual(state.data[tx1.key], "1")
        
        tx2 = Transaction(
            sender=self.alice_pub,
            key=f"{self.alice_pub}/counter",
            value="2",
            signature=""
        )
        tx2.signature = self.alice_key.sign(tx2.encode(), "TX", self.chain_id)
        state.apply_tx(tx2, self.chain_id)
        
        self.assertEqual(state.data[tx2.key], "2")
    
    def test_empty_state_commitment(self):
        state1 = AppState()
        state2 = AppState()
        
        commitment1 = state1.get_commitment()
        commitment2 = state2.get_commitment()
        
        self.assertEqual(commitment1, commitment2)
        self.assertIsInstance(commitment1, str)
        self.assertEqual(len(commitment1), 64)  # SHA-256 hex


class TestBlockBuilding(unittest.TestCase):
    def setUp(self):
        self.chain_id = "test-chain"
        self.proposer_key = NodeKey()
        self.proposer_pub = self.proposer_key.get_public_key_hex()
        
        genesis_state = AppState()
        self.genesis = BlockHeader(
            parent_hash="0" * 64,
            height=0,
            state_hash=genesis_state.get_commitment(),
            proposer="genesis",
            signature=""
        )
    
    def test_build_empty_block(self):
        header, state = build_block(self.genesis, [], self.proposer_key, self.chain_id)
        
        self.assertEqual(header.height, 1)
        self.assertEqual(header.parent_hash, self.genesis.hash)
        self.assertEqual(header.proposer, self.proposer_pub)
        self.assertNotEqual(header.signature, "")
    
    def test_build_block_with_transactions(self):
        alice_key = NodeKey()
        alice_pub = alice_key.get_public_key_hex()
        
        tx = Transaction(
            sender=alice_pub,
            key=f"{alice_pub}/data",
            value="test",
            signature=""
        )
        tx.signature = alice_key.sign(tx.encode(), "TX", self.chain_id)
        
        header, state = build_block(self.genesis, [tx], self.proposer_key, self.chain_id)
        
        self.assertEqual(header.height, 1)
        self.assertIn(tx.key, state.data)
        self.assertEqual(state.data[tx.key], "test")
    
    def test_deterministic_block_building(self):
        alice_key = NodeKey()
        alice_pub = alice_key.get_public_key_hex()
        
        tx = Transaction(
            sender=alice_pub,
            key=f"{alice_pub}/data",
            value="test",
            signature=""
        )
        tx.signature = alice_key.sign(tx.encode(), "TX", self.chain_id)
        
        header1, state1 = build_block(self.genesis, [tx], self.proposer_key, self.chain_id)
        header2, state2 = build_block(self.genesis, [tx], self.proposer_key, self.chain_id)
        
        # State hashes should match (deterministic execution)
        self.assertEqual(header1.state_hash, header2.state_hash)
        self.assertEqual(state1.get_commitment(), state2.get_commitment())


if __name__ == '__main__':
    unittest.main()
