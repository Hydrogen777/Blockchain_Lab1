import json
from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path


class DeterministicLogger:    
    def __init__(self, log_file: str = None, enable_console: bool = True):
        self.log_file = log_file
        self.enable_console = enable_console
        self.logs: List[Dict[str, Any]] = []
        
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'w') as f:
                f.write("")
    
    def log(self, event_type: str, node_id: str, timestamp: float, 
            details: Dict[str, Any] = None, height: int = None):
        log_entry = {
            "timestamp": round(timestamp, 6),  # Round to ensure determinism
            "node_id": node_id,
            "event_type": event_type,
        }
        
        if height is not None:
            log_entry["height"] = height
        
        if details:
            log_entry["details"] = details
        
        # Store in memory
        self.logs.append(log_entry)
        
        # Write to file (deterministic JSON format)
        if self.log_file:
            with open(self.log_file, 'a') as f:
                # Use separators for deterministic output (no spaces)
                f.write(json.dumps(log_entry, sort_keys=True, separators=(',', ':')) + '\n')
        
        # Print to console if enabled
        if self.enable_console:
            self._print_log(log_entry)
    
    def _print_log(self, log_entry: Dict[str, Any]):
        timestamp = log_entry["timestamp"]
        node_id = log_entry["node_id"]
        event_type = log_entry["event_type"]
        height = log_entry.get("height", "-")
        
        details_str = ""
        if "details" in log_entry:
            details = log_entry["details"]
            # Format details nicely
            if isinstance(details, dict):
                parts = [f"{k}={v}" for k, v in details.items()]
                details_str = " " + " ".join(parts)
            else:
                details_str = f" {details}"
        
        print(f"[{timestamp:8.2f}] [{node_id:12s}] [{event_type:12s}] [H:{height:4s}]{details_str}")
    
    def get_logs(self) -> List[Dict[str, Any]]:
        return self.logs
    
    def get_final_state_summary(self, nodes: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            "total_logs": len(self.logs),
            "nodes": {}
        }
        
        for node_id, node in nodes.items():
            node_summary = {
                "finalized_blocks": len(node.consensus.finalized_blocks),
                "finalized_heights": sorted(node.consensus.finalized_blocks.keys()),
                "state_hash": node.state.get_commitment(),
                "state_data": dict(sorted(node.state.data.items())),
            }
            summary["nodes"][node_id] = node_summary
        
        return summary
    
    def save_summary(self, summary: Dict[str, Any], summary_file: str):
        Path(summary_file).parent.mkdir(parents=True, exist_ok=True)
        with open(summary_file, 'w') as f:
            json.dump(summary, f, sort_keys=True, indent=2, separators=(',', ':'))
    
    @staticmethod
    def compare_logs(log_file1: str, log_file2: str) -> bool:
        try:
            with open(log_file1, 'rb') as f1, open(log_file2, 'rb') as f2:
                content1 = f1.read()
                content2 = f2.read()
                return content1 == content2
        except FileNotFoundError:
            return False
    
    @staticmethod
    def compare_summaries(summary_file1: str, summary_file2: str) -> bool:
        try:
            with open(summary_file1, 'r') as f1, open(summary_file2, 'r') as f2:
                summary1 = json.load(f1)
                summary2 = json.load(f2)
                return summary1 == summary2
        except FileNotFoundError:
            return False


_global_logger = None

def get_logger() -> DeterministicLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = DeterministicLogger()
    return _global_logger


def set_logger(logger: DeterministicLogger):
    global _global_logger
    _global_logger = logger
