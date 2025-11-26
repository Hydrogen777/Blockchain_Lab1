import heapq
import random
import json
from dataclasses import dataclass, field
from typing import List, Any, Dict, Set
from collections import deque

# Config
DROP_RATE = 0.05        
DUPLICATE_RATE = 0.05   
MIN_DELAY = 0.5         
MAX_DELAY = 3.0         
RATE_LIMIT_WINDOW = 5.0 
MAX_MSG_PER_WINDOW = 5 
BLOCK_DURATION = 10.0   

@dataclass(order=True)
class NetworkEvent:
    arrival_time: float
    sender_id: str = field(compare=False)
    receiver_id: str = field(compare=False)
    message: Any = field(compare=False)

class NetworkSimulator:
    def __init__(self):
        self.event_queue = []
        self.current_time = 0.0
        self.links: Dict[str, Set[str]] = {}

        self.traffic_history: Dict[str, deque] = {}
        
        self.blocked_senders: Dict[str, float] = {}

    def add_node(self, node_id: str):
        if node_id not in self.links:
            self.links[node_id] = set()
            self.traffic_history[node_id] = deque()

    def connect(self, node_a: str, node_b: str):
        self.add_node(node_a)
        self.add_node(node_b)
        self.links[node_a].add(node_b)
        self.links[node_b].add(node_a)

    def _check_rate_limit(self, sender_id: str) -> bool:
        if sender_id in self.blocked_senders:
            if self.current_time < self.blocked_senders[sender_id]:
                return True 
            else:
                del self.blocked_senders[sender_id]
                self.log(f"UNBLOCK: Node {sender_id} is active again.", sender_id)

        history = self.traffic_history.get(sender_id, deque())
        while history and history[0] < self.current_time - RATE_LIMIT_WINDOW:
            history.popleft()
        
        if len(history) >= MAX_MSG_PER_WINDOW:
            self.blocked_senders[sender_id] = self.current_time + BLOCK_DURATION
            self.log(f"BLOCK: Node {sender_id} blocked for {BLOCK_DURATION}s (Rate Limit Exceeded).", sender_id)
            return True
        
        history.append(self.current_time)
        self.traffic_history[sender_id] = history
        return False

    def send(self, sender_id: str, receiver_id: str, message: Any):        
        if receiver_id not in self.links.get(sender_id, set()):
            self.log(f"FAIL: No connection from {sender_id} to {receiver_id}", sender_id)
            return

        if self._check_rate_limit(sender_id):
            return 

        if random.random() < DROP_RATE:
            self.log(f"DROP: Message from {sender_id} to {receiver_id} lost.", sender_id, message)
            return
        def schedule_event(delay_offset=0.0):
            delay = random.uniform(MIN_DELAY, MAX_DELAY) + delay_offset
            arrival = self.current_time + delay
            event = NetworkEvent(arrival, sender_id, receiver_id, message)
            heapq.heappush(self.event_queue, event)
            return arrival


        arrival_time = schedule_event()
        self.log(f"SENT: -> {receiver_id} (Arrive ~{arrival_time:.2f})", sender_id, message)
        if random.random() < DUPLICATE_RATE:
            dup_time = schedule_event(delay_offset=0.5)
            self.log(f"DUPLICATE: -> {receiver_id} (Ghost msg arrive ~{dup_time:.2f})", sender_id, message)

    def tick(self, steps=1.0) -> List[NetworkEvent]:
        self.current_time += steps
        arrived = []
        while self.event_queue and self.event_queue[0].arrival_time <= self.current_time:
            event = heapq.heappop(self.event_queue)
            arrived.append(event)
        return arrived

    def log(self, content: str, node_id: str = "NET", message: Any = None):
        msg_type = "UNK"
        msg_height = "-"
        if isinstance(message, dict):
            msg_type = message.get("type", "DATA") 
            msg_height = str(message.get("height", "-"))
        
        elif isinstance(message, str) and message.startswith("{"):
            try:
                data = json.loads(message)
                msg_type = data.get("type", "DATA")
                msg_height = str(data.get("height", "-"))
            except:
                pass

        print(f"[{self.current_time:.2f}] [{node_id}] [{msg_type}|H:{msg_height}] {content}")

# Test script
if __name__ == "__main__":
    net = NetworkSimulator()
    net.connect("Alice", "Bob")
    net.connect("Bob", "Charlie")

    print("--- Test 1: Topology & Routing ---")
    net.send("Alice", "Bob", {"type": "TX", "height": 10, "data": "Hello Bob"})
    net.send("Alice", "Charlie", "Hello Charlie")

    print("\n--- Test 2: Rate Limiting & Blocking ---")
    for i in range(7):
        net.send("Alice", "Bob", {"type": "SPAM", "id": i})
        net.tick(0.1)

    print("\n--- Test 3: Simulation Loop ---")
    for i in range(10):
        print(f"\n--- Tick {i} (Time: {net.current_time:.1f}) ---")
        events = net.tick(1.0)
        for e in events:
            print(f"   >>> HANDLER: {e.receiver_id} received '{e.message}'")