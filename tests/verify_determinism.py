import sys
import os
import random
import hashlib
from pathlib import Path

SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH.resolve()))

from crypto import NodeKey, CryptoUtils
from network import NetworkSimulator, set_random_seed
from consensus import ConsensusState
from execution import Transaction
from node import BlockchainNode
from logger import DeterministicLogger
from nacl.signing import SigningKey

def run_scenario(run_id: int, seed: int = 42) -> dict:
    print(f"\n{'='*70}")
    print(f"  RUN {run_id}: Starting deterministic scenario (seed={seed})")
    print(f"{'='*70}\n")
    
    set_random_seed(seed)
    
    log_file = f"logs/run_{run_id}.log"
    summary_file = f"logs/run_{run_id}_summary.json"
    logger = DeterministicLogger(log_file=log_file, enable_console=False)
    
    CHAIN_ID = "lab01-determinism-test"
    NUM_NODES = 4
    
    # Create deterministic keys from seed
    node_keys = []
    for i in range(NUM_NODES):
        # Create a deterministic 32-byte seed from (seed, i)
        seed_bytes = hashlib.sha256(f"{seed}:{i}".encode('utf-8')).digest()
        # Create SigningKey from seed (deterministic)
        signing_key = SigningKey(seed_bytes)
        # Create a NodeKey-like object
        key = NodeKey()
        key._signing_key = signing_key
        key.verify_key = signing_key.verify_key
        node_keys.append(key)
    
    validator_set = {key.get_public_key_hex() for key in node_keys}
    
    nodes = {}
    for i, key in enumerate(node_keys):
        node_id = f"Node_{i}"
        node = BlockchainNode(
            node_id=node_id,
            key=key,
            validator_set=validator_set,
            chain_id=CHAIN_ID,
            logger=logger
        )
        nodes[node_id] = node
    
    network = NetworkSimulator(logger=logger)
    
    node_ids = list(nodes.keys())
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            network.connect(node_ids[i], node_ids[j])
    
    logger.log("INIT", "SYSTEM", 0.0, {
        "chain_id": CHAIN_ID,
        "num_nodes": NUM_NODES,
        "seed": seed
    })
    
    # === Scenario: Create and finalize blocks ===
    
    # Step 1: Create some transactions
    logger.log("SCENARIO_START", "SYSTEM", 0.0, {"step": "create_transactions"})
    
    transactions = []
    for i, node_id in enumerate(node_ids[:3]):  # First 3 nodes create transactions
        node = nodes[node_id]
        tx = Transaction(
            sender=node.public_key,
            key=f"{node.public_key}/message",
            value=f"Hello from {node_id}",
            signature=""
        )
        tx.signature = node.key.sign(tx.encode(), "TX", CHAIN_ID)
        transactions.append(tx)
        
        # Broadcast transaction to all nodes
        for target_id in node_ids:
            nodes[target_id].receive_transaction(tx)
    
    # Step 2: Node_0 proposes a block at height 1
    logger.log("SCENARIO_START", "SYSTEM", 0.0, {"step": "propose_block", "height": 1})
    
    proposer = nodes["Node_0"]
    parent_hash = proposer.genesis.hash
    block_header = proposer.propose_block(parent_hash)
    
    if not block_header:
        raise Exception("Failed to propose block")
    
    block_txs = proposer.block_bodies[block_header.hash]
    
    # Broadcast block to all nodes
    for node_id, node in nodes.items():
        if node_id != "Node_0":
            node.receive_block(block_header, block_txs)
    
    # Step 3: All nodes prevote for the block
    logger.log("SCENARIO_START", "SYSTEM", 0.0, {"step": "prevote_phase", "height": 1})
    
    for node_id, node in nodes.items():
        vote = node.create_vote(block_header.hash, 1, "prevote")
        
        # Broadcast vote to all nodes
        for target_id, target_node in nodes.items():
            target_node.receive_vote(vote)
    
    # Step 4: All nodes precommit for the block
    logger.log("SCENARIO_START", "SYSTEM", 0.0, {"step": "precommit_phase", "height": 1})
    
    for node_id, node in nodes.items():
        vote = node.create_vote(block_header.hash, 1, "precommit")
        
        # Broadcast vote to all nodes
        for target_id, target_node in nodes.items():
            target_node.receive_vote(vote)
    
    # Step 5: Verify all nodes finalized the same block
    logger.log("SCENARIO_START", "SYSTEM", 0.0, {"step": "verify_finalization"})
    
    finalized_hashes = {}
    for node_id, node in nodes.items():
        hashes = node.get_finalized_block_hashes()
        finalized_hashes[node_id] = hashes
        logger.log("FINALIZED_BLOCKS", node_id, 0.0, {
            "count": len(hashes),
            "hashes": [h[:16] + "..." for h in hashes]
        })
    
    # Verify all nodes have same finalized blocks
    first_node_hashes = finalized_hashes[node_ids[0]]
    for node_id in node_ids[1:]:
        if finalized_hashes[node_id] != first_node_hashes:
            raise Exception(f"Node {node_id} has different finalized blocks!")
    
    logger.log("SCENARIO_END", "SYSTEM", 0.0, {"status": "success"})
    
    # Generate final state summary
    summary = logger.get_final_state_summary(nodes)
    logger.save_summary(summary, summary_file)
    
    print(f"\n{'='*70}")
    print(f"  RUN {run_id}: Completed successfully")
    print(f"  - Log file: {log_file}")
    print(f"  - Summary file: {summary_file}")
    print(f"  - Total logs: {summary['total_logs']}")
    print(f"  - Finalized blocks: {len(first_node_hashes)}")
    print(f"{'='*70}\n")
    
    return summary


def compare_runs(run1_summary: dict, run2_summary: dict) -> bool:
    print("\n" + "="*70)
    print("  COMPARISON RESULTS")
    print("="*70 + "\n")
    
    all_match = True
    
    # Compare node states
    for node_id in run1_summary["nodes"]:
        node1 = run1_summary["nodes"][node_id]
        node2 = run2_summary["nodes"][node_id]
        
        print(f"Node: {node_id}")
        
        # Compare state hash
        if node1["state_hash"] == node2["state_hash"]:
            print(f"State hash matches: {node1['state_hash'][:16]}...")
        else:
            print(f"State hash mismatch!")
            print(f"    Run 1: {node1['state_hash']}")
            print(f"    Run 2: {node2['state_hash']}")
            all_match = False
        
        # Compare finalized blocks
        if node1["finalized_heights"] == node2["finalized_heights"]:
            print(f"Finalized heights match: {node1['finalized_heights']}")
        else:
            print(f"Finalized heights mismatch!")
            print(f"    Run 1: {node1['finalized_heights']}")
            print(f"    Run 2: {node2['finalized_heights']}")
            all_match = False
        
        # Compare state data
        if node1["state_data"] == node2["state_data"]:
            print(f"State data matches ({len(node1['state_data'])} entries)")
        else:
            print(f"State data mismatch!")
            all_match = False
        
        print()
    
    return all_match


def main():
    print("\n" + "="*70)
    print("  BLOCKCHAIN DETERMINISM VERIFICATION")
    print("  Lab 01 - Part 8: Determinism and Logging")
    print("="*70)
    
    Path("logs").mkdir(exist_ok=True)
    
    SEED = 42
    
    try:
        summary1 = run_scenario(run_id=1, seed=SEED)
        summary2 = run_scenario(run_id=2, seed=SEED)
        
        print("\nComparing log files...")
        logs_identical = DeterministicLogger.compare_logs(
            "logs/run_1.log",
            "logs/run_2.log"
        )
        
        if logs_identical:
            print("Log files are BYTE-IDENTICAL")
        else:
            print("Log files are DIFFERENT")
            print("\nShowing first difference:")
            with open("logs/run_1.log", 'r') as f1, open("logs/run_2.log", 'r') as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()
                for i, (line1, line2) in enumerate(zip(lines1, lines2), 1):
                    if line1 != line2:
                        print(f"  Line {i} differs:")
                        print(f"    Run 1: {line1.strip()}")
                        print(f"    Run 2: {line2.strip()}")
                        break
        
        print("\nComparing final states...")
        summaries_identical = compare_runs(summary1, summary2)
        
        # Final verdict
        print("\n" + "="*70)
        print("  FINAL VERDICT")
        print("="*70 + "\n")
        
        if logs_identical and summaries_identical:
            print("SUCCESS")
            print("Both runs produced IDENTICAL logs and final states.")
            print("The system is DETERMINISTIC and REPRODUCIBLE.")
            return 0
        else:
            print("FAILURE")
            print("Runs produced different outputs.")
            print("The system is NOT deterministic.")
            return 1
    
    except Exception as e:
        print(f"\nERROR")
        print(f"An error occurred during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
