from typing import Dict, List, Optional, Set
from crypto import NodeKey, CryptoUtils
from consensus import ConsensusState, Vote, BlockHeader
from execution import AppState, Transaction, build_block
from network import NetworkEvent


class BlockchainNode:    
    def __init__(self, node_id: str, key: NodeKey, validator_set: Set[str], 
                 chain_id: str, logger=None):
        self.node_id = node_id
        self.key = key
        self.public_key = key.get_public_key_hex()
        self.chain_id = chain_id
        self.logger = logger
        
        # Consensus state
        self.consensus = ConsensusState(validator_set, chain_id)
        
        # Execution state
        self.state = AppState()
        
        # Block storage
        self.blocks: Dict[str, BlockHeader] = {}  # block_hash -> BlockHeader
        self.block_bodies: Dict[str, List[Transaction]] = {}  # block_hash -> txs
        
        # Current height we're working on
        self.current_height = 0
        
        # Genesis block
        self.genesis = BlockHeader(
            parent_hash="0" * 64,
            height=0,
            state_hash=self.state.get_commitment(),
            proposer="genesis",
            signature=""
        )
        self.blocks[self.genesis.hash] = self.genesis
        self.block_bodies[self.genesis.hash] = []
        self.consensus.finalized_blocks[0] = self.genesis.hash
        
        # Pending transactions
        self.pending_txs: List[Transaction] = []
        
        # Track seen votes to prevent duplicates
        self.seen_votes: Set[str] = set()
    
    def _log(self, event_type: str, details: Dict = None, height: int = None):
        if self.logger:
            self.logger.log(event_type, self.node_id, 0.0, details, height)
    
    def receive_transaction(self, tx: Transaction) -> bool:
        # Create a temporary state to test the transaction
        temp_state = AppState()
        temp_state.data = self.state.data.copy()
        
        if temp_state.apply_tx(tx, self.chain_id):
            self.pending_txs.append(tx)
            self._log("TX_RECEIVED", {
                "sender": tx.sender,
                "key": tx.key,
                "value": tx.value
            })
            return True
        else:
            self._log("TX_REJECTED", {
                "sender": tx.sender,
                "key": tx.key,
                "reason": "invalid_signature_or_ownership"
            })
            return False
    
    def propose_block(self, parent_hash: str) -> Optional[BlockHeader]:
        if parent_hash not in self.blocks:
            self._log("PROPOSE_FAILED", {"reason": "parent_not_found", "parent": parent_hash})
            return None
        
        parent = self.blocks[parent_hash]
        
        # Build block with pending transactions
        header, new_state = build_block(parent, self.pending_txs, self.key, self.chain_id)
        
        # Store the block
        self.blocks[header.hash] = header
        self.block_bodies[header.hash] = self.pending_txs.copy()
        
        self._log("BLOCK_PROPOSED", {
            "block_hash": header.hash[:16],
            "parent_hash": parent_hash[:16],
            "tx_count": len(self.pending_txs),
            "state_hash": header.state_hash[:16]
        }, height=header.height)
        
        # Clear pending transactions
        self.pending_txs = []
        
        return header
    
    def receive_block(self, header: BlockHeader, txs: List[Transaction]) -> bool:
        # Check if we already have this block
        if header.hash in self.blocks:
            return True
        
        # Verify parent exists
        if header.parent_hash not in self.blocks:
            self._log("BLOCK_REJECTED", {
                "reason": "parent_not_found",
                "block_hash": header.hash[:16],
                "parent_hash": header.parent_hash[:16]
            }, height=header.height)
            return False
        
        # Verify header signature
        from crypto import Validator
        if not Validator.verify(
            public_key_hex=header.proposer,
            signature_hex=header.signature,
            message=header.encode(),
            context="HEADER",
            chain_id=self.chain_id
        ):
            self._log("BLOCK_REJECTED", {
                "reason": "invalid_signature",
                "block_hash": header.hash[:16]
            }, height=header.height)
            return False
        
        # Re-execute transactions to verify state
        parent = self.blocks[header.parent_hash]
        recomputed_header, _ = build_block(parent, txs, self.key, self.chain_id)
        
        # Check state hash matches (ignore proposer and signature)
        if recomputed_header.state_hash != header.state_hash:
            self._log("BLOCK_REJECTED", {
                "reason": "state_mismatch",
                "block_hash": header.hash[:16],
                "expected": header.state_hash[:16],
                "got": recomputed_header.state_hash[:16]
            }, height=header.height)
            return False
        
        # Store valid block
        self.blocks[header.hash] = header
        self.block_bodies[header.hash] = txs
        
        self._log("BLOCK_RECEIVED", {
            "block_hash": header.hash[:16],
            "proposer": header.proposer[:16],
            "tx_count": len(txs)
        }, height=header.height)
        
        return True
    
    def create_vote(self, block_hash: str, height: int, phase: str) -> Vote:
        vote = Vote(
            validator=self.public_key,
            height=height,
            block_hash=block_hash,
            phase=phase,
            signature=""
        )
        
        # Sign the vote
        vote.signature = self.key.sign(
            message=vote.encode(),
            context="VOTE",
            chain_id=self.chain_id
        )
        
        self._log(f"VOTE_{phase.upper()}", {
            "block_hash": block_hash[:16],
            "phase": phase
        }, height=height)
        
        return vote
    
    def receive_vote(self, vote: Vote) -> bool:
        # Check for duplicate votes
        vote_id = f"{vote.validator}:{vote.height}:{vote.phase}:{vote.block_hash}"
        if vote_id in self.seen_votes:
            return False  # Silently ignore duplicates
        
        # Process vote through consensus
        if self.consensus.handle_vote(vote):
            self.seen_votes.add(vote_id)
            
            self._log(f"VOTE_RECEIVED_{vote.phase.upper()}", {
                "validator": vote.validator[:16],
                "block_hash": vote.block_hash[:16]
            }, height=vote.height)
            
            # Check if this vote caused finalization
            finalized_hash = self.consensus.finalized_blocks.get(vote.height)
            if finalized_hash and finalized_hash == vote.block_hash:
                self._finalize_block(vote.height, finalized_hash)
            
            return True
        else:
            self._log(f"VOTE_REJECTED_{vote.phase.upper()}", {
                "validator": vote.validator[:16],
                "reason": "invalid_signature_or_validator"
            }, height=vote.height)
            return False
    
    def _finalize_block(self, height: int, block_hash: str):
        if block_hash not in self.blocks:
            return
        
        # Apply all transactions from finalized block to state
        txs = self.block_bodies.get(block_hash, [])
        for tx in txs:
            self.state.apply_tx(tx, self.chain_id)
        
        self._log("BLOCK_FINALIZED", {
            "block_hash": block_hash[:16],
            "tx_count": len(txs),
            "state_hash": self.state.get_commitment()[:16]
        }, height=height)
        
        # Update current height
        self.current_height = max(self.current_height, height)
    
    def get_finalized_block_hashes(self) -> List[str]:
        heights = sorted(self.consensus.finalized_blocks.keys())
        return [self.consensus.finalized_blocks[h] for h in heights]
    
    def get_state_summary(self) -> Dict:
        return {
            "state_hash": self.state.get_commitment(),
            "state_data": dict(sorted(self.state.data.items())),
            "finalized_heights": sorted(self.consensus.finalized_blocks.keys()),
            "current_height": self.current_height
        }
