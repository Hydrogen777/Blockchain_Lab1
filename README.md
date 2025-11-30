# HCMUS Blockchain Lab 01: Design and Implement a Minimal Layer 1 Blockchain 

A Layer 1 Blockchain implementation, featuring BFT consensus, deterministic execution, and network simulation. This project is a hands-on exercise of blockchain fundamentals for the HCMUS Blockchain course.

## Group Members

| Student ID | Full Name |
|------------|-----------|
| 22120357 | Tran Van Anh Thu |
| 22120456 | Vu Chau Minh Tri | 
| 22120457 | Khuu Hai Chau | 
| 22120460 | Duong Hoai Minh | 


## Project Structure

```
Blockchain_Lab1/
├── config/
│   ├── default_config.json    # Default simulation configuration
│   └── requirements.txt       # Python dependencies
├── src/
│   ├── consensus.py           # BFT consensus state management
│   ├── crypto.py              # Ed25519 signatures and hashing
│   ├── execution.py           # Transaction execution and state
│   ├── logger.py              # Deterministic logging
│   ├── models.py              # Data models
│   ├── network.py             # Network simulator with delays/drops
│   └── node.py                # Blockchain node implementation
├── tests/
│   ├── run_tests.py           # Main test runner
│   ├── test_consensus.py      # Consensus unit tests
│   ├── test_crypto.py         # Cryptography unit tests
│   ├── test_e2e.py            # End-to-end integration tests
│   ├── test_execution.py      # Execution layer tests
│   └── verify_determinism.py  # Determinism verification
└── README.md
```

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd Blockchain_Lab1
   ```

2. **Create a virtual environment (recommended)**

   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r config/requirements.txt
   ```

## Running the Simulator

### Run Individual Components

You can test individual modules directly:

```bash
# Test cryptography module
python src/crypto.py

# Test network simulator
python src/network.py
```

### Run Determinism Verification

This runs a complete simulation scenario twice with the same seed to verify deterministic behavior:

```bash
python tests/verify_determinism.py
```

This will:
- Create a 4-node blockchain network
- Process transactions and finalize blocks
- Verify that both runs produce identical logs and states
- Output logs to `logs/` directory

## Running Tests

### Run All Tests

Execute the complete test suite including unit tests and determinism verification:

```bash
python tests/run_tests.py
```

### Run Individual Test Files

```bash
python tests/test_crypto.py
python tests/test_consensus.py
python tests/test_execution.py
python tests/test_e2e.py
```

## Test Coverage

| Test Module | Description |
|-------------|-------------|
| `test_crypto.py` | Signature verification, context separation, hash determinism |
| `test_consensus.py` | Vote validation, vote counting, finalization logic |
| `test_execution.py` | Transaction validation, state management, block building |
| `test_e2e.py` | End-to-end scenarios, network delays, duplicate handling |
| `verify_determinism.py` | Full simulation determinism verification |

## Configuration

Edit [config/default_config.json](config/default_config.json) to customize:

- `chain_id`: Blockchain identifier
- `num_nodes`: Number of validator nodes
- `network`: Drop rate, delays, rate limiting
- `consensus`: Block time and timeouts
- `simulation`: Random seed and duration

## Features

- **Ed25519 Signatures**: Secure digital signatures with context separation
- **BFT Consensus**: Prevote/precommit phases with 2/3+ majority finalization
- **Deterministic Execution**: Reproducible state transitions
- **Network Simulation**: Configurable delays, packet drops, and duplicates
- **Rate Limiting**: Protection against spam attacks
- **Deterministic Logging**: Byte-identical logs across runs
