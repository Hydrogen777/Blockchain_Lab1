import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from crypto import NodeKey, Validator, CryptoUtils

class TestCryptoUtils(unittest.TestCase):    
    def test_deterministic_bytes_dict(self):
        data1 = {"b": 2, "a": 1, "c": 3}
        data2 = {"a": 1, "b": 2, "c": 3}
        data3 = {"c": 3, "a": 1, "b": 2}
        
        # All should produce same bytes (keys sorted)
        bytes1 = CryptoUtils.get_deterministic_bytes(data1)
        bytes2 = CryptoUtils.get_deterministic_bytes(data2)
        bytes3 = CryptoUtils.get_deterministic_bytes(data3)
        
        self.assertEqual(bytes1, bytes2)
        self.assertEqual(bytes2, bytes3)
    
    def test_deterministic_hash(self):
        data1 = {"key": "value", "num": 123}
        data2 = {"num": 123, "key": "value"}
        
        hash1 = CryptoUtils.hash_data(data1)
        hash2 = CryptoUtils.hash_data(data2)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA-256 hex
    
    def test_different_data_different_hash(self):
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}
        
        hash1 = CryptoUtils.hash_data(data1)
        hash2 = CryptoUtils.hash_data(data2)
        
        self.assertNotEqual(hash1, hash2)


class TestSignatureVerification(unittest.TestCase):    
    def setUp(self):
        self.chain_id = "test-chain"
        self.alice_key = NodeKey()
        self.alice_pub = self.alice_key.get_public_key_hex()
        self.bob_key = NodeKey()
        self.bob_pub = self.bob_key.get_public_key_hex()
    
    def test_valid_signature(self):
        message = {"sender": "Alice", "data": "hello"}
        signature = self.alice_key.sign(message, "TX", self.chain_id)
        
        is_valid = Validator.verify(
            self.alice_pub, signature, message, "TX", self.chain_id
        )
        
        self.assertTrue(is_valid)
    
    def test_invalid_signature_wrong_key(self):
        message = {"sender": "Alice", "data": "hello"}
        signature = self.alice_key.sign(message, "TX", self.chain_id)
        
        # Try to verify with Bob's key
        is_valid = Validator.verify(
            self.bob_pub, signature, message, "TX", self.chain_id
        )
        
        self.assertFalse(is_valid)
    
    def test_tampered_message(self):
        message = {"sender": "Alice", "amount": 100}
        signature = self.alice_key.sign(message, "TX", self.chain_id)
        
        # Tamper with message
        tampered = {"sender": "Alice", "amount": 1000}
        is_valid = Validator.verify(
            self.alice_pub, signature, tampered, "TX", self.chain_id
        )
        
        self.assertFalse(is_valid)
    
    def test_context_separation(self):
        message = {"height": 1, "data": "test"}
        signature = self.alice_key.sign(message, "TX", self.chain_id)
        
        # Try to use TX signature as VOTE signature
        is_valid = Validator.verify(
            self.alice_pub, signature, message, "VOTE", self.chain_id
        )
        
        self.assertFalse(is_valid, "Signature should not validate with different context")
    
    def test_chain_id_separation(self):
        message = {"sender": "Alice", "data": "hello"}
        signature = self.alice_key.sign(message, "TX", "chain-1")
        
        # Try to verify with different chain ID
        is_valid = Validator.verify(
            self.alice_pub, signature, message, "TX", "chain-2"
        )
        
        self.assertFalse(is_valid, "Signature should not validate with different chain ID")
    
    def test_multiple_contexts(self):
        message = {"data": "test"}
        contexts = ["TX", "HEADER", "VOTE", "CUSTOM"]
        
        for context in contexts:
            signature = self.alice_key.sign(message, context, self.chain_id)
            is_valid = Validator.verify(
                self.alice_pub, signature, message, context, self.chain_id
            )
            self.assertTrue(is_valid, f"Context {context} should work")
            
            # Verify it doesn't work with other contexts
            for other_context in contexts:
                if other_context != context:
                    is_valid = Validator.verify(
                        self.alice_pub, signature, message, other_context, self.chain_id
                    )
                    self.assertFalse(
                        is_valid,
                        f"Signature from {context} should not work with {other_context}"
                    )


class TestPublicKeyFormat(unittest.TestCase):
    def test_public_key_hex_format(self):
        key = NodeKey()
        pub_hex = key.get_public_key_hex()
        
        try:
            bytes.fromhex(pub_hex)
        except ValueError:
            self.fail("Public key should be valid hex")
        
        # Should be consistent length (Ed25519 = 32 bytes = 64 hex chars)
        self.assertEqual(len(pub_hex), 64)
    
    def test_different_keys_different_public_keys(self):
        key1 = NodeKey()
        key2 = NodeKey()
        
        pub1 = key1.get_public_key_hex()
        pub2 = key2.get_public_key_hex()
        
        self.assertNotEqual(pub1, pub2)


if __name__ == '__main__':
    unittest.main()