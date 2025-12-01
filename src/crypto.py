import json
import hashlib
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

class CryptoUtils:
    def __init__(self):
        pass

    @staticmethod
    def get_deterministic_bytes(data: dict | str | bytes) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode('utf-8')
        if isinstance(data, dict):
            return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
        raise ValueError("Unsupported data type")

    @staticmethod
    def hash_data(data) -> str:
        byte_data = CryptoUtils.get_deterministic_bytes(data)
        return hashlib.sha256(byte_data).hexdigest()

class NodeKey:
    def __init__(self):
        # Tạo cặp khóa Ed25519 ngẫu nhiên
        self._signing_key = SigningKey.generate()
        self.verify_key = self._signing_key.verify_key
    
    def get_public_key_hex(self) -> str:
        return self.verify_key.encode().hex()

    def sign(self, message: dict | str, context: str, chain_id: str) -> str:
        msg_bytes = CryptoUtils.get_deterministic_bytes(message)
        prefix = f"{context}:{chain_id}:".encode('utf-8')
        
        full_payload = prefix + msg_bytes
        signed = self._signing_key.sign(full_payload)
        return signed.signature.hex()

class Validator:
    @staticmethod
    def verify(public_key_hex: str, signature_hex: str, message: dict | str, context: str, chain_id: str) -> bool:
        try:
            verify_key = VerifyKey(bytes.fromhex(public_key_hex))
            msg_bytes = CryptoUtils.get_deterministic_bytes(message)
            prefix = f"{context}:{chain_id}:".encode('utf-8')
            full_payload = prefix + msg_bytes

            verify_key.verify(full_payload, bytes.fromhex(signature_hex))
            return True
        except (BadSignatureError, ValueError):
            return False
