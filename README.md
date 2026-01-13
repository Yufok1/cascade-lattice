# cascade-lattice

**Universal AI provenance + inference intervention + code diagnostics. See what AI sees. Choose what AI chooses. Find bugs before they find you.**

[![PyPI](https://img.shields.io/pypi/v/cascade-lattice.svg)](https://pypi.org/project/cascade-lattice/)
[![Python](https://img.shields.io/pypi/pyversions/cascade-lattice.svg)](https://pypi.org/project/cascade-lattice/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

```
pip install cascade-lattice
```

---

## 🎮 Interactive Demo

**See CASCADE-LATTICE in action** — fly a lunar lander with AI, take control anytime:

```bash
pip install cascade-lattice[demo]
cascade-demo
```

**Controls:**
- `[H]` **HOLD-FREEZE** — Pause time, see AI's decision matrix, override with WASD
- `[T]` **HOLD-TAKEOVER** — You fly the lander, AI watches, provenance records everything
- `[ESC]` Release hold, return to AI control

Every action is merkle-chained. Every decision has provenance. This is the future of human-AI interaction.

---

## Two Superpowers

### 1. OBSERVE - Cryptographic receipts for every AI call

```python
from cascade.store import observe

# Every inference -> hashed -> chained -> stored
receipt = observe("my_agent", {"action": "jump", "confidence": 0.92})
print(receipt.cid)  # bafyrei... (permanent content address)
```

### 2. HOLD - Pause AI at decision points

```python
from cascade.hold import Hold
import numpy as np

hold = Hold.get()

# Your model (any framework)
action_probs = model.predict(state)

resolution = hold.yield_point(
    action_probs=action_probs,
    value=0.72,
    observation={"state": state},
    brain_id="my_model",
    action_labels=["up", "down", "left", "right"],  # Human-readable
)

# AI pauses. You see the decision matrix.
# Accept or override. Then it continues.
action = resolution.action
```

### 3. DIAGNOSE - Find bugs before they find you

```python
from cascade.diagnostics import diagnose, BugDetector

# Quick one-liner analysis
report = diagnose("path/to/your/code.py")
print(report)  # Markdown-formatted bug report

# Deep scan a whole project
detector = BugDetector()
issues = detector.scan_directory("./my_project")

for issue in issues:
    print(f"[{issue.severity}] {issue.file}:{issue.line}")
    print(f"  {issue.message}")
    print(f"  Pattern: {issue.pattern.name}")
```

**What it catches:**
- 🔴 **Critical**: Division by zero, null pointer access, infinite loops
- 🟠 **High**: Bare except clauses, resource leaks, race conditions
- 🟡 **Medium**: Unused variables, dead code, type mismatches
- 🔵 **Low**: Style issues, naming conventions, complexity warnings

**Runtime tracing:**
```python
from cascade.diagnostics import CodeTracer

tracer = CodeTracer()

@tracer.trace
def my_function(x):
    return x / (x - 1)  # Potential div by zero when x=1

# After execution, trace root causes
tracer.find_root_causes("error_event_id")
```

---

## Quick Start

### Zero-Config Auto-Patch

```python
import cascade
cascade.init()

# That's it. Every call is now observed.
import openai
# ... use normally, receipts emit automatically
```

### Manual Observation

```python
from cascade.store import observe, query

# Write
observe("gpt-4", {"prompt": "Hello", "response": "Hi!", "tokens": 5})

# Read
for receipt in query("gpt-4", limit=10):
    print(receipt.cid, receipt.data)
```

---

## HOLD: Inference-Level Intervention

HOLD lets you pause any AI at decision points:

```
══════════════════════════════════════════════════
🛑 HOLD #1
   Merkle: 3f92e75df4bf653f
   AI Choice: FORWARD (confidence: 45.00%)
   Value: 0.7200
   Probabilities: FORWARD:0.45, BACK:0.30, LEFT:0.15, RIGHT:0.10
   Wealth: attention, features, reasoning
   Waiting for resolution (timeout: 30s)...
══════════════════════════════════════════════════
```

**Model-agnostic** - works with:
- PyTorch, JAX, TensorFlow
- HuggingFace, OpenAI, Anthropic
- Stable Baselines, RLlib
- Any function that outputs probabilities

### Informational Wealth

Pass everything your model knows to help humans decide:

```python
resolution = hold.yield_point(
    action_probs=probs,
    value=value_estimate,
    observation=obs,
    brain_id="my_model",
    
    # THE WEALTH (all optional):
    action_labels=["FORWARD", "BACK", "LEFT", "RIGHT"],
    latent=model.get_latent(),           # Internal activations
    attention={"position": 0.7, "health": 0.3},
    features={"danger": 0.2, "goal_align": 0.8},
    imagination={                         # Per-action predictions
        0: {"trajectory": ["pos", "pos"], "expected_value": 0.8},
        1: {"trajectory": ["neg", "neg"], "expected_value": -0.3},
    },
    logits=raw_logits,
    reasoning=["High reward path", "Low risk"],
)
```

### Build Your Own Interface

Register a listener to receive full `HoldPoint` data:

```python
def my_ui_handler(hold_point):
    # hold_point contains ALL the wealth
    print(hold_point.action_labels)
    print(hold_point.imagination)
    # Send to your UI, game engine, logger, etc.

hold.register_listener(my_ui_handler)
```

---

## Collective Intelligence

Every observation goes into the **lattice**:

```python
from cascade.store import observe, query

# Agent A observes
observe("pathfinder", {"state": [1,2], "action": 3, "reward": 1.0})

# Agent B queries
past = query("pathfinder")
for r in past:
    print(r.data["action"], r.data["reward"])
```

---

## CLI

```bash
# View lattice stats
cascade stats

# List observations  
cascade list --limit 20

# HOLD info
cascade hold

# HOLD system status
cascade hold-status

# Start proxy
cascade proxy --port 7777
```

---

## Installation

```bash
# Core
pip install cascade-lattice

# With interactive demo (LunarLander)
pip install cascade-lattice[demo]

# With LLM providers
pip install cascade-lattice[openai]
pip install cascade-lattice[anthropic]
pip install cascade-lattice[all]
```

---

## How It Works

```
Your Model                    CASCADE                      Storage
    |                            |                            |
    |  action_probs = [0.1,     |                            |
    |                  0.6,     |                            |
    |                  0.3]     |                            |
    | ------------------------->|                            |
    |                           |  hash(probs) -> CID        |
    |        HOLD               |  chain(prev_cid, cid)      |
    |   +-------------+         | -------------------------> |
    |   | See matrix  |         |              ~/.cascade/   |
    |   | Override?   |         |              lattice/      |
    |   +-------------+         |                            |
    | <-------------------------|                            |
    |   resolution.action       |                            |
```

---

## Genesis

Every receipt chains back to genesis:

```
Genesis: 89f940c1a4b7aa65
```

The lattice grows. Discovery is reading the chain.

---

## Links

- [PyPI](https://pypi.org/project/cascade-lattice/)
- [Issues](https://github.com/Yufok1/cascade-lattice/issues)

---

*"even still, i grow, and yet, I grow still"*

## Documentation

### Research & Theory

**📄 [Research Paper: Kleene Fixed-Point Framework](https://github.com/Yufok1/cascade-lattice/blob/main/docs/RESEARCH_PAPER.md)**  
Deep dive into the mathematical foundations—how CASCADE-LATTICE maps neural network computations to Kleene fixed points, creating verifiable provenance chains through distributed lattice networks.

**📖 [Accessible Guide: From Theory to Practice](https://github.com/Yufok1/cascade-lattice/blob/main/docs/ACCESSIBLE_GUIDE.md)**  
For everyone from data scientists to curious users—understand how CASCADE works, with examples ranging from medical AI oversight to autonomous drone coordination.

**Key Concepts:**
- **Kleene Fixed Points**: Neural networks as monotonic functions converging to stable outputs
- **Provenance Chains**: Cryptographic Merkle trees tracking every layer's computation
- **HOLD Protocol**: Human-in-the-loop intervention at decision boundaries
- **Lattice Network**: Distributed fixed-point convergence across AI agents

### Quick Links

- **Theory**: [Research Paper](https://github.com/Yufok1/cascade-lattice/blob/main/docs/RESEARCH_PAPER.md) | [Mathematical Proofs](https://github.com/Yufok1/cascade-lattice/blob/main/docs/RESEARCH_PAPER.md#appendix-b-mathematical-proofs)
- **Practice**: [Accessible Guide](https://github.com/Yufok1/cascade-lattice/blob/main/docs/ACCESSIBLE_GUIDE.md) | [Real-World Examples](https://github.com/Yufok1/cascade-lattice/blob/main/docs/ACCESSIBLE_GUIDE.md#real-world-examples)

---

## References

Built on foundational work in:
- **Kleene Fixed Points** (Kleene, 1952) — Theoretical basis for provenance convergence
- **Merkle Trees** (Merkle, 1987) — Cryptographic integrity guarantees
- **IPFS/IPLD** (Benet, 2014) — Content-addressed distributed storage

See [full bibliography](https://github.com/Yufok1/cascade-lattice/blob/main/docs/RESEARCH_PAPER.md#references) in the research paper.
