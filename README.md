# Cascade Lattice

**Universal AI provenance layer — cryptographic receipts for every call, with HOLD inference halt protocol**

[![PyPI version](https://badge.fury.io/py/cascade-lattice.svg)](https://pypi.org/project/cascade-lattice/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install cascade-lattice
```

With optional dependencies:
```bash
pip install cascade-lattice[torch]  # PyTorch integration
pip install cascade-lattice[all]    # All integrations
```

## Quick Start

```python
from cascade import Monitor

# Create a monitor for your component
monitor = Monitor("training_loop")

# Observe events (parses logs, extracts metrics)
event = monitor.observe("Epoch 5: loss=0.0234, accuracy=0.9812")
print(event.data)  # {'loss': 0.0234, 'accuracy': 0.9812, ...}

# Get metrics summary
print(monitor.metrics.summary())
```

## Features

- **Universal Observation** — Monitor training, inference, system logs, API calls
- **Cryptographic Receipts** — Every observation gets a verifiable hash chain
- **HOLD Protocol** — Inference halt capability for safety-critical applications
- **Tape Storage** — JSONL event streams for replay and analysis
- **Provider Patches** — Drop-in monitoring for OpenAI, Anthropic, LiteLLM, Ollama

## CLI Usage

```bash
cascade --help              # Show all commands
cascade stats               # Lattice statistics
cascade list -n 20          # Recent observations
cascade watch               # Live observation feed
cascade fingerprint model/  # Fingerprint a model
cascade pii scan.log        # Scan for PII
```

## Tape Utilities

```python
from cascade.viz import load_tape_file, find_latest_tape, list_tape_files

# Find and load tape files
latest = find_latest_tape("./logs")
events = load_tape_file(latest)

for event in events:
    print(event['event']['event_type'], event['event']['data'])
```

## License

MIT
