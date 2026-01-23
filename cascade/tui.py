"""
🌐 CASCADE-LATTICE TUI - Textual Terminal User Interface

A celebration of provenance. Navigate the lattice like a curious explorer.

Run: python -m cascade.tui
     python cascade/tui.py

Features:
- Module Explorer: Drill into any module, see actual code
- Graph Navigation: Follow relationships, not just hierarchy
- Explanation Toggle: "For Dummies" vs "For Scientists"
- Live Stats: See your observation counts, genesis root
- Interactive Demos: Test functions in real-time

"even still, i grow, and yet, I grow still"
"""

from __future__ import annotations

import sys
import inspect
import importlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Static, Button, Label,
    Tree, TabbedContent, TabPane,
    RichLog, Markdown, Rule, Switch, Input,
    ListView, ListItem, Collapsible,
)
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.message import Message
from textual.css.query import NoMatches

from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown as RichMarkdown


# ═══════════════════════════════════════════════════════════════
# MODULE GRAPH - Maps relationships between modules
# ═══════════════════════════════════════════════════════════════

@dataclass
class ModuleNode:
    """A node in the module graph."""
    name: str
    full_path: str
    doc_dummy: str = ""      # Explanation for beginners
    doc_scientist: str = ""  # Technical explanation
    exports: List[str] = field(default_factory=list)
    imports_from: List[str] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)  # Sub-modules
    parent: Optional[str] = None
    category: str = "core"   # core, hold, store, viz, diagnostics, forensics
    icon: str = "📦"


# The module graph - hand-crafted with love
MODULE_GRAPH: Dict[str, ModuleNode] = {
    # ═══════════════════════════════════════════════════════════
    # ROOT
    # ═══════════════════════════════════════════════════════════
    "cascade_lattice": ModuleNode(
        name="cascade_lattice",
        full_path="cascade_lattice",
        icon="🌐",
        category="root",
        doc_dummy="""
# 🌐 CASCADE-LATTICE

**What is this?** Think of it as a "receipt printer" for AI decisions.

Every time an AI makes a choice, cascade-lattice writes it down with a 
cryptographic signature. Like getting a receipt at a store - you can 
prove what happened, when, and trace it back to the source.

**Why does this matter?**
- 🔍 **Transparency**: See exactly what your AI did
- 🛡️ **Safety**: Humans can pause and review decisions (HOLD)
- 📜 **Provenance**: Trace any output back to its origins
- 🔗 **Integrity**: Cryptographic proofs prevent tampering

**The Genesis Block**: Everything traces back to one root hash.
Like the first block in a blockchain, but for AI decisions.
        """,
        doc_scientist="""
# CASCADE-LATTICE: Universal AI Provenance Layer

A content-addressed, Merkle-authenticated observation framework implementing 
the HOLD protocol for human-in-the-loop inference control.

## Architecture

```
                    ┌─────────────────┐
                    │  Genesis Root   │
                    │  89f940c1a4b7   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Receipt │         │ Receipt │         │ Receipt │
   │ CID: baf│         │ CID: baf│         │ CID: baf│
   └─────────┘         └─────────┘         └─────────┘
```

## Key Concepts

- **CID**: Content Identifier (IPFS CIDv1, dag-cbor codec)
- **Merkle Root**: SHA-256 hash chain for integrity verification
- **HoldPoint**: Freeze-frame of model state for human inspection
- **SymbioticAdapter**: Kleene fixed-point signal normalization
- **ProvenanceChain**: Linked list of cryptographic attestations

## Module Hierarchy

- `core/`: Event, Graph, Provenance, Adapter primitives
- `hold/`: HOLD protocol implementation (pause/inspect/override)
- `store`: SQLite + IPFS + HuggingFace persistence
- `genesis`: Root provenance chain creation
- `viz/`: Tape recording and playback
- `diagnostics/`: Bug detection, execution monitoring
- `forensics/`: Data archaeology, tech fingerprinting
        """,
        exports=["Hold", "HoldPoint", "HoldState", "HoldResolution", "Receipt", 
                 "Monitor", "SymbioticAdapter", "CausationGraph", "genesis", 
                 "observe", "store", "viz", "diagnostics", "forensics"],
        children=["core", "hold", "store", "genesis", "viz", "diagnostics", "forensics"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # CORE MODULE
    # ═══════════════════════════════════════════════════════════
    "core": ModuleNode(
        name="core",
        full_path="cascade_lattice.core",
        icon="⚙️",
        category="core",
        parent="cascade_lattice",
        doc_dummy="""
# ⚙️ Core Module

**What is this?** The engine room of cascade-lattice.

Think of it like the foundation of a house - you don't see it, 
but everything else is built on top of it.

**What's inside:**
- 📊 **Event**: A single "thing that happened" 
- 🔗 **Graph**: How events connect to each other
- 🔐 **Provenance**: The chain of custody (who touched what, when)
- 🤝 **Adapter**: Translates between different signal formats
        """,
        doc_scientist="""
# Core Module (`cascade.core`)

Foundational primitives for the observation framework.

## Components

### Event (`core.event`)
```python
@dataclass
class Event:
    timestamp: float
    component: str
    event_type: str
    data: Dict[str, Any]
    event_id: str  # Auto-generated UUID
```

### CausationGraph (`core.graph`)
Directed acyclic graph for causal relationship tracking.
- `add_event(event)` → Register event node
- `add_link(cause_id, effect_id, strength)` → Causal edge
- `find_path(start, end)` → Shortest causal path
- `get_root_events()` → Events with no causes

### ProvenanceChain (`core.provenance`)
Merkle-authenticated chain of records.
- `add_record(input_hash, output_hash, model_hash)`
- `verify()` → Validate chain integrity
- `get_lineage()` → Full audit trail

### SymbioticAdapter (`core.adapter`)
Kleene fixed-point signal interpreter.
- `interpret(signal)` → Normalize ANY format to Event
- `learned_patterns` → Discovered signal structures
        """,
        exports=["Event", "CausationGraph", "ProvenanceChain", "ProvenanceRecord",
                 "SymbioticAdapter", "compute_merkle_root", "hash_tensor"],
        children=["event", "graph", "provenance", "adapter"],
        imported_by=["hold", "store", "genesis", "diagnostics"],
    ),
    
    "event": ModuleNode(
        name="event",
        full_path="cascade_lattice.core.event",
        icon="📊",
        category="core",
        parent="core",
        doc_dummy="""
# 📊 Event

**What is this?** A snapshot of "something happened."

Like a diary entry: "At 3:42pm, the AI looked at a cat picture 
and decided it was 90% cat, 10% loaf of bread."

**Key parts:**
- ⏰ **timestamp**: When did it happen?
- 🏷️ **event_type**: What kind of thing? (decision, observation, error)
- 📝 **data**: The actual details
- 🆔 **event_id**: Unique fingerprint for this exact moment
        """,
        doc_scientist="""
# Event (`cascade.core.event`)

Immutable record of a discrete system occurrence.

```python
@dataclass
class Event:
    timestamp: float          # Unix epoch (time.time())
    component: str            # Source subsystem identifier
    event_type: str           # Taxonomy: state_change, decision, observation
    data: Dict[str, Any]      # Arbitrary payload (JSON-serializable)
    event_id: str             # UUID v4, auto-generated
    source_signal: Any = None # Original input before normalization
    
    def to_dict(self) -> Dict[str, Any]: ...
    @classmethod
    def from_dict(cls, d: Dict) -> 'Event': ...
```

## Event Types
- `state_change`: Internal state mutation
- `decision`: Action selection with confidence
- `observation`: External input processing
- `hold_point`: HITL pause trigger
- `resolution`: Human decision on hold
        """,
        exports=["Event"],
        imports_from=["provenance"],
        imported_by=["graph", "adapter", "hold.primitives"],
    ),
    
    "graph": ModuleNode(
        name="graph",
        full_path="cascade_lattice.core.graph",
        icon="🕸️",
        category="core",
        parent="core",
        doc_dummy="""
# 🕸️ Causation Graph

**What is this?** A map of cause and effect.

Imagine a detective's board with photos connected by red string.
"This event CAUSED that event." You can trace backwards to find
the root cause of anything.

**What can you do:**
- 🔍 **Trace backwards**: "What caused this bug?"
- ➡️ **Trace forwards**: "What did this decision affect?"
- 🌳 **Find roots**: "Where did it all begin?"
- 📏 **Find paths**: "How are these two events connected?"
        """,
        doc_scientist="""
# CausationGraph (`cascade.core.graph`)

DAG-based causal relationship tracker with temporal ordering.

```python
class CausationGraph:
    def add_event(self, event: Event) -> str: ...
    def add_link(self, cause_id: str, effect_id: str, 
                 strength: float = 1.0) -> None: ...
    def get_causes(self, event_id: str) -> List[Event]: ...
    def get_effects(self, event_id: str) -> List[Event]: ...
    def find_path(self, start_id: str, end_id: str) -> List[str]: ...
    def get_root_events(self) -> List[Event]: ...
    def get_terminal_events(self) -> List[Event]: ...
    def compute_impact(self, event_id: str) -> float: ...
```

## Link Semantics
- `strength ∈ [0, 1]`: Causal contribution weight
- Multiple causes: `Σ strength_i` need not equal 1
- Temporal constraint: `cause.timestamp < effect.timestamp`

## Traversal
- BFS for shortest path
- DFS for exhaustive impact analysis
- Topological sort for execution order
        """,
        exports=["CausationGraph", "CausationChain"],
        imports_from=["event"],
        imported_by=["diagnostics", "monitor"],
    ),
    
    "provenance": ModuleNode(
        name="provenance",
        full_path="cascade_lattice.core.provenance",
        icon="🔐",
        category="core",
        parent="core",
        doc_dummy="""
# 🔐 Provenance

**What is this?** A chain of custody for AI decisions.

Like evidence in a courtroom - you need to prove the evidence 
wasn't tampered with. Provenance creates a cryptographic trail
that proves: "This output really came from this input through 
this model, and nobody messed with it."

**Key functions:**
- 🧮 **hash_tensor**: Fingerprint a neural network's weights
- 📝 **hash_input**: Fingerprint what went in
- 🔗 **compute_merkle_root**: Combine all fingerprints into one
- ✅ **verify_chain**: Check if anything was tampered with
        """,
        doc_scientist="""
# Provenance (`cascade.core.provenance`)

Merkle-authenticated provenance tracking with cryptographic verification.

```python
def hash_tensor(tensor: np.ndarray) -> str:
    '''SHA-256 of normalized tensor bytes (first 16 hex chars)'''

def hash_params(module: nn.Module) -> str:
    '''Hash all named_parameters recursively'''

def hash_input(data: Any) -> str:
    '''JSON-serialize then hash'''

def compute_merkle_root(hashes: List[str]) -> str:
    '''Binary tree Merkle root computation'''

@dataclass
class ProvenanceRecord:
    input_hash: str
    output_hash: str
    model_hash: str
    timestamp: float
    parent_merkle: Optional[str]
    merkle_root: str  # Computed from above fields
    
@dataclass
class ProvenanceChain:
    model_id: str
    session_id: str
    records: List[ProvenanceRecord]
    merkle_root: str
    
    def add_record(self, input_h, output_h, model_h) -> ProvenanceRecord: ...
    def verify(self) -> bool: ...
    def get_lineage(self) -> List[ProvenanceRecord]: ...
```

## Merkle Tree Structure
```
        root
       /    \\
     h01    h23
    /  \\   /  \\
   h0  h1 h2  h3
```
        """,
        exports=["ProvenanceChain", "ProvenanceRecord", "ProvenanceTracker",
                 "compute_merkle_root", "hash_tensor", "hash_params", 
                 "hash_input", "hash_model", "verify_chain"],
        imported_by=["genesis", "store", "hold.primitives"],
    ),
    
    "adapter": ModuleNode(
        name="adapter",
        full_path="cascade_lattice.core.adapter",
        icon="🤝",
        category="core",
        parent="core",
        doc_dummy="""
# 🤝 Symbiotic Adapter

**What is this?** A universal translator for AI signals.

Different AI models speak different languages - some output 
dictionaries, some output numpy arrays, some output raw text.
The adapter learns to understand ANY format and converts it 
to a standard Event.

**Think of it like:** Google Translate, but for AI outputs.

**Magic feature:** It learns patterns as it sees more signals!
        """,
        doc_scientist="""
# SymbioticAdapter (`cascade.core.adapter`)

Kleene fixed-point signal normalizer implementing universal interpretation.

```python
class SymbioticAdapter:
    def __init__(self): 
        self._patterns: List[SignalPattern] = []
        self._signal_count: int = 0
    
    def interpret(self, signal: Any) -> Event:
        '''
        Fixed-point iteration:
        1. Try known patterns in order
        2. If match, extract structured data
        3. If no match, create raw_message wrapper
        4. Learn new pattern if structure detected
        '''
    
    @property
    def signal_count(self) -> int: ...
    
    @property 
    def learned_patterns(self) -> List[str]: ...
```

## Pattern Learning
- Dict with 'embedding' key → vector extraction
- Dict with 'action'/'reward' → RL transition
- numpy.ndarray → tensor observation
- str → raw message wrapper

## Kleene Semantics
Interpretation reaches fixed-point when:
- Pattern matching stabilizes
- No new patterns discovered in N signals
        """,
        exports=["SymbioticAdapter", "SignalPattern"],
        imports_from=["event"],
        imported_by=["monitor", "hold.session"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # HOLD MODULE
    # ═══════════════════════════════════════════════════════════
    "hold": ModuleNode(
        name="hold",
        full_path="cascade_lattice.hold",
        icon="⏸️",
        category="hold",
        parent="cascade_lattice",
        doc_dummy="""
# ⏸️ HOLD - Human-in-the-Loop

**What is this?** A pause button for AI decisions.

Before the AI acts, HOLD freezes everything and asks:
"Hey human, here's what I'm about to do. Is this okay?"

**You can:**
- ✅ **Accept**: "Yes, do it"
- ✏️ **Override**: "No, do THIS instead"
- ❌ **Cancel**: "Stop everything"
- ⏰ **Timeout**: If you don't respond, a default happens

**Why is this important?** 
It's the "11th man" - the human who has final say over AI decisions.
        """,
        doc_scientist="""
# HOLD Protocol (`cascade.hold`)

Human-in-the-loop inference control implementing freeze-frame inspection.

## Architecture
```
Model Forward Pass
       │
       ▼
   ┌───────────┐
   │ HoldPoint │◄─── Freeze state
   └─────┬─────┘
         │
    ┌────┴────┐
    │ PENDING │
    └────┬────┘
         │
   ┌─────┴─────┐
   │  Human    │
   │ Decision  │
   └─────┬─────┘
         │
    ┌────┴────┐        ┌────────────┐
    │ACCEPTED │   or   │ OVERRIDDEN │
    └─────────┘        └────────────┘
```

## State Machine
```
PENDING ──accept()──► ACCEPTED
   │
   ├──override()──► OVERRIDDEN
   │
   ├──cancel()──► CANCELLED
   │
   └──timeout()──► TIMEOUT
```

## Key Classes
- `Hold`: Singleton controller, manages yield_point flow
- `HoldPoint`: Immutable snapshot with merkle_root
- `HoldResolution`: Result of human decision
- `HoldState`: Enum of possible states
        """,
        exports=["Hold", "HoldPoint", "HoldResolution", "HoldState", "HoldAwareMixin"],
        children=["hold.primitives", "hold.session"],
        imports_from=["core.event", "core.provenance"],
        imported_by=["store", "viz"],
    ),
    
    "hold.primitives": ModuleNode(
        name="primitives",
        full_path="cascade_lattice.hold.primitives",
        icon="🧱",
        category="hold",
        parent="hold",
        doc_dummy="""
# 🧱 Hold Primitives

**What is this?** The building blocks of HOLD.

- **HoldPoint**: A freeze-frame snapshot
  - What action was the AI going to take?
  - How confident was it?
  - What was it looking at?
  
- **HoldState**: Is it waiting? Approved? Overridden?

- **HoldResolution**: What did the human decide?
        """,
        doc_scientist="""
# Hold Primitives (`cascade.hold.primitives`)

Core data structures for the HOLD protocol.

```python
class HoldState(Enum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    OVERRIDDEN = 'overridden'
    TIMEOUT = 'timeout'
    CANCELLED = 'cancelled'

@dataclass
class HoldPoint:
    action_probs: np.ndarray      # Softmax distribution
    value: float                   # V(s) estimate
    observation: Any               # Input state
    brain_id: str                  # Source model identifier
    action_labels: List[str] = None
    latent: np.ndarray = None      # Hidden state
    attention: np.ndarray = None   # Attention weights
    features: Dict = None          # Arbitrary display data
    imagination: Any = None        # World model prediction
    logits: np.ndarray = None      # Pre-softmax scores
    reasoning: str = None          # CoT trace
    world_prediction: Any = None   # Future state prediction
    
    # Auto-computed
    id: str                        # UUID
    timestamp: float               # Creation time
    parent_merkle: str = None      # Chain linkage
    merkle_root: str               # Integrity hash
    state: HoldState = PENDING

@dataclass
class HoldResolution:
    action: int                    # Selected action index
    was_override: bool             # Human changed it?
    override_source: str = None    # Who overrode?
    hold_duration: float           # Seconds in PENDING
    notes: str = None              # Human annotation
```
        """,
        exports=["HoldPoint", "HoldState", "HoldResolution"],
        imports_from=["core.provenance"],
        imported_by=["hold.session", "viz.tape"],
    ),
    
    "hold.session": ModuleNode(
        name="session",
        full_path="cascade_lattice.hold.session",
        icon="🎮",
        category="hold",
        parent="hold",
        doc_dummy="""
# 🎮 Hold Session

**What is this?** The controller that manages HOLD pauses.

It's like a game pause menu:
- Press pause (yield_point)
- Game freezes
- You make a choice
- Game resumes

**Key actions:**
- `yield_point()`: Pause and wait for human
- `accept()`: Resume with AI's choice
- `override()`: Resume with human's choice
- `cancel()`: Abort entirely
        """,
        doc_scientist="""
# Hold Session (`cascade.hold.session`)

Singleton-pattern HOLD controller with listener registration.

```python
class Hold:
    _instance: 'Hold' = None  # Singleton
    
    def __new__(cls) -> 'Hold':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def yield_point(
        self,
        action_probs: np.ndarray,
        value: float,
        observation: Any,
        brain_id: str,
        blocking: bool = True,
        **kwargs
    ) -> Optional[HoldResolution]:
        '''
        Create HoldPoint, notify listeners, optionally block.
        Returns HoldResolution when resolved.
        '''
    
    def accept(self, action: int = None) -> HoldResolution: ...
    def override(self, action: int, source: str) -> HoldResolution: ...
    def cancel(self) -> None: ...
    def register_listener(self, callback: Callable) -> None: ...
    def current_hold(self) -> Optional[HoldPoint]: ...
    
    @property
    def auto_accept(self) -> bool: ...
    @property
    def timeout(self) -> float: ...
    def stats(self) -> Dict[str, Any]: ...
```

## Listener Pattern
```python
def my_listener(hold_point: HoldPoint):
    print(f"Received: {hold_point.id}")
    # Inspect, then call Hold().accept() or override()

Hold().register_listener(my_listener)
```
        """,
        exports=["Hold", "HoldAwareMixin"],
        imports_from=["hold.primitives", "core.adapter"],
        imported_by=["store", "brain"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # STORE MODULE
    # ═══════════════════════════════════════════════════════════
    "store": ModuleNode(
        name="store",
        full_path="cascade_lattice.store",
        icon="💾",
        category="store",
        parent="cascade_lattice",
        doc_dummy="""
# 💾 Store

**What is this?** Where all the receipts are saved.

Like a filing cabinet that:
- 📁 **Saves locally**: SQLite database on your computer
- ☁️ **Syncs to cloud**: HuggingFace datasets
- 🌐 **Pins to IPFS**: Decentralized, permanent storage

**Key functions:**
- `observe()`: Save an observation and get a receipt
- `query()`: Find observations by model name
- `stats()`: How many observations do I have?
        """,
        doc_scientist="""
# Store (`cascade.store`)

Multi-tier persistence layer: Local SQLite → HuggingFace → IPFS.

```python
# Configuration
CENTRAL_DATASET = "tostido/cascade-observations"
DEFAULT_LATTICE_DIR = Path.home() / ".cascade" / "lattice"
IPFS_GATEWAYS = [
    'https://ipfs.io/ipfs/',
    'https://dweb.link/ipfs/',
    'https://gateway.pinata.cloud/ipfs/'
]

@dataclass
class Receipt:
    cid: str              # IPFS CIDv1 (dag-cbor)
    model_id: str         # Source model identifier
    merkle_root: str      # Chain integrity hash
    timestamp: float      # Unix epoch
    data: Dict[str, Any]  # Original observation
    parent_cid: str = None

class LocalStore:
    def __init__(self, lattice_dir: Path = None): ...
    def save(self, receipt: Receipt) -> None: ...
    def get(self, cid: str) -> Optional[Receipt]: ...
    def get_latest(self, model_id: str) -> Optional[Receipt]: ...
    def query(self, model_id: str, limit: int = 100) -> List[Receipt]: ...
    def count(self) -> int: ...

# Top-level functions
def observe(model_id: str, data: Dict, parent_cid: str = None, 
            sync: bool = True) -> Receipt: ...
def query(model_id: str, limit: int = 100) -> List[Receipt]: ...
def stats() -> Dict[str, Any]: ...
def sync_all() -> None: ...
```

## CID Computation (dag-cbor)
```python
def data_to_cid(data: Dict) -> Tuple[str, bytes]:
    cbor_bytes = dag_cbor.encode(data)
    digest = multihash.digest(cbor_bytes, 'sha2-256')
    return CID('base32', 1, 'dag-cbor', digest).encode(), cbor_bytes
```
        """,
        exports=["Receipt", "LocalStore", "observe", "query", "stats", 
                 "sync_all", "compute_cid", "data_to_cid", "fetch_receipt"],
        imports_from=["core.provenance", "genesis"],
        imported_by=["hold.session", "viz"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # GENESIS MODULE
    # ═══════════════════════════════════════════════════════════
    "genesis": ModuleNode(
        name="genesis",
        full_path="cascade_lattice.genesis",
        icon="🌅",
        category="genesis",
        parent="cascade_lattice",
        doc_dummy="""
# 🌅 Genesis

**What is this?** The beginning of everything.

Like the first page of a book, or the Big Bang of the universe.
Every single observation in cascade-lattice can trace its lineage
back to ONE root hash: the Genesis Block.

**The Genesis Message:**
> "In the beginning was the hash, and the hash was with the chain, 
>  and the hash was the chain."

**Genesis Root:** `89f940c1a4b7aa65`

This is your cryptographic anchor. If you can verify lineage to 
genesis, you KNOW the data hasn't been tampered with.
        """,
        doc_scientist="""
# Genesis (`cascade.genesis`)

Root provenance anchor with deterministic initialization.

```python
GENESIS_INPUT = "In the beginning was the hash, and the hash was with the chain, and the hash was the chain."
GENESIS_MODEL_ID = "cascade_genesis"
GENESIS_SESSION_ID = "genesis_0"

def create_genesis() -> ProvenanceChain:
    '''
    Create the root provenance chain.
    Deterministic: always produces merkle_root = 89f940c1a4b7aa65
    '''

def get_genesis_root() -> str:
    '''Return the canonical genesis merkle root'''
    return "89f940c1a4b7aa65"

def verify_lineage_to_genesis(
    chain: ProvenanceChain, 
    known_chains: Dict[str, ProvenanceChain]
) -> bool:
    '''
    Verify that a chain can trace its lineage to genesis.
    Walks external_roots until genesis is reached.
    '''

def link_to_genesis(chain: ProvenanceChain) -> ProvenanceChain:
    '''Add genesis as external root'''

def save_genesis(path: Path) -> None: ...
def load_genesis(path: Path) -> ProvenanceChain: ...
```

## Genesis Chain Structure
```json
{
  "model_id": "cascade_genesis",
  "session_id": "genesis_0",
  "merkle_root": "89f940c1a4b7aa65",
  "finalized": true,
  "records": [{
    "input_hash": "<hash of GENESIS_INPUT>",
    "output_hash": "<hash of GENESIS_INPUT>",
    "model_hash": "<hash of 'genesis'>",
    "merkle_root": "89f940c1a4b7aa65"
  }]
}
```
        """,
        exports=["create_genesis", "get_genesis_root", "verify_lineage_to_genesis",
                 "link_to_genesis", "ProvenanceChain", "GENESIS_INPUT"],
        imports_from=["core.provenance"],
        imported_by=["store"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # VIZ MODULE
    # ═══════════════════════════════════════════════════════════
    "viz": ModuleNode(
        name="viz",
        full_path="cascade_lattice.viz",
        icon="🎬",
        category="viz",
        parent="cascade_lattice",
        doc_dummy="""
# 🎬 Viz - Visualization

**What is this?** A VCR for AI decisions.

Record everything that happens, then play it back later.
Like watching game replays, but for AI behavior.

**Features:**
- 📼 **Tape**: Record events to a file
- ⏪ **Playback**: Scrub through history
- 🔍 **Inspection**: See exactly what happened at any moment
        """,
        doc_scientist="""
# Viz (`cascade.viz`)

Event tape recording and playback for debugging and analysis.

```python
# Tape I/O
def create_tape_path(prefix: str = "tape") -> str:
    '''Generate timestamped tape filename'''

def write_tape_event(tape_path: str, event: Dict) -> None:
    '''Append JSONL event to tape file'''

def load_tape_file(tape_path: str) -> List[Dict]:
    '''Load all events from tape'''

def list_tape_files(directory: str = ".") -> List[str]:
    '''Find all tape files'''

def find_latest_tape(directory: str = ".") -> Optional[str]:
    '''Get most recent tape file'''

@dataclass
class PlaybackEvent:
    timestamp: float
    event_type: str
    data: Dict[str, Any]

@dataclass
class PlaybackBuffer:
    events: List[PlaybackEvent]
    current_index: int = 0
    is_complete: bool = False
    
    def add(self, event: PlaybackEvent) -> None: ...
    def get_events_up_to(self, index: int) -> List[PlaybackEvent]: ...
    
    @classmethod
    def from_tape(cls, tape_path: str) -> 'PlaybackBuffer': ...
```
        """,
        exports=["PlaybackBuffer", "PlaybackEvent", "create_tape_path",
                 "write_tape_event", "load_tape_file", "list_tape_files"],
        children=["viz.tape"],
        imports_from=["hold.primitives"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # DIAGNOSTICS MODULE
    # ═══════════════════════════════════════════════════════════
    "diagnostics": ModuleNode(
        name="diagnostics",
        full_path="cascade_lattice.diagnostics",
        icon="🔬",
        category="diagnostics",
        parent="cascade_lattice",
        doc_dummy="""
# 🔬 Diagnostics

**What is this?** A doctor for your code.

It scans your code looking for problems, bugs, and weird patterns.
Like a health checkup, but for software.

**Tools:**
- 🐛 **BugDetector**: Find common bug patterns
- 🏥 **DiagnosticEngine**: Comprehensive code analysis
- 📊 **ExecutionMonitor**: Watch code as it runs
        """,
        doc_scientist="""
# Diagnostics (`cascade.diagnostics`)

Static analysis, runtime monitoring, and bug pattern detection.

```python
class BugDetector:
    def __init__(self): ...
    def register_pattern(self, pattern: BugPattern) -> None: ...
    def scan_file(self, path: Path) -> List[DetectedIssue]: ...
    def scan_directory(self, path: Path) -> List[DetectedIssue]: ...
    def get_summary(self) -> Dict[str, int]: ...
    def get_report(self) -> DiagnosticReport: ...

class DiagnosticEngine:
    def analyze_file(self, path: Path) -> DiagnosticReport: ...
    def analyze_directory(self, path: Path) -> DiagnosticReport: ...
    def analyze_execution(self, trace: List[ExecutionFrame]) -> DiagnosticReport: ...
    def to_markdown(self) -> str: ...

class ExecutionMonitor:
    def __init__(self): ...
    def start(self) -> None: ...
    def stop(self) -> List[ExecutionFrame]: ...
    def get_hot_paths(self) -> List[Tuple[str, int]]: ...

@dataclass
class BugPattern:
    name: str
    regex: str
    severity: str  # info, warning, error, critical
    description: str
    fix_suggestion: str

@dataclass
class DetectedIssue:
    pattern: BugPattern
    file: Path
    line: int
    context: str
```
        """,
        exports=["BugDetector", "DiagnosticEngine", "ExecutionMonitor",
                 "BugPattern", "BugSignature", "DetectedIssue", "DiagnosticReport"],
        children=["diagnostics.bug_detector", "diagnostics.execution_monitor"],
        imports_from=["core.graph"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # FORENSICS MODULE
    # ═══════════════════════════════════════════════════════════
    "forensics": ModuleNode(
        name="forensics",
        full_path="cascade_lattice.forensics",
        icon="🔎",
        category="forensics",
        parent="cascade_lattice",
        doc_dummy="""
# 🔎 Forensics

**What is this?** Digital archaeology for data.

When you find mysterious data, forensics helps you figure out:
- 🕵️ What created this data?
- 📅 When was it created?
- 🔧 What tools/frameworks were used?
- 🚨 Are there any security concerns?

**Think of it like:** CSI for code and data.
        """,
        doc_scientist="""
# Forensics (`cascade.forensics`)

Data archaeology and tech stack fingerprinting.

```python
class DataForensics:
    def analyze(self, data: Any) -> ForensicsReport: ...
    def analyze_file(self, path: Path) -> ForensicsReport: ...

class TechFingerprinter:
    PATTERNS: Dict[str, str]  # tech_name → regex
    COMPOUND_PATTERNS: Dict[str, List[str]]  # framework → components
    
    def analyze(self, text: str) -> List[Fingerprint]: ...
    def get_likely_stack(self) -> List[str]: ...
    def get_security_concerns(self) -> List[str]: ...

class ArtifactDetector:
    def detect_timestamps(self, data: Any) -> TimestampArtifacts: ...
    def detect_ids(self, data: Any) -> IDPatternArtifacts: ...
    def detect_schemas(self, data: Any) -> SchemaArtifacts: ...
    def detect_text_patterns(self, text: str) -> TextArtifacts: ...
    def detect_numeric_patterns(self, numbers: List) -> NumericArtifacts: ...

@dataclass
class Fingerprint:
    tech: str
    confidence: float
    evidence: List[str]

@dataclass
class ForensicsReport:
    fingerprints: List[Fingerprint]
    artifacts: Dict[str, Any]
    inferred_operations: List[InferredOperation]
    ghost_logs: List[GhostLog]  # Traces of deleted data
```
        """,
        exports=["DataForensics", "TechFingerprinter", "ArtifactDetector",
                 "Fingerprint", "ForensicsReport", "GhostLog"],
        children=["forensics.analyzer", "forensics.fingerprints", "forensics.artifacts"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # LISTEN MODULE
    # ═══════════════════════════════════════════════════════════
    "listen": ModuleNode(
        name="listen",
        full_path="cascade_lattice.listen",
        icon="👂",
        category="core",
        parent="cascade_lattice",
        doc_dummy="""
# 👂 Listen

**What is this?** A passive observer for HOLD events.

Like having a security camera that records everything without 
interfering. Events flow through and you can watch them later.

**The event_queue:** A line where events wait to be processed.
        """,
        doc_scientist="""
# Listen (`cascade.listen`)

Passive event monitoring via thread-safe queue.

```python
event_queue: Queue  # Thread-safe event queue

def main():
    '''CLI entry point for passive monitoring'''
    monitor = Monitor("listener")
    while True:
        try:
            event = event_queue.get(timeout=1.0)
            print(json.dumps(event.to_dict()))
        except Empty:
            continue
```

Usage:
```bash
python -m cascade.listen
```
        """,
        exports=["event_queue", "Monitor"],
        imports_from=["core.event"],
    ),
    
    # ═══════════════════════════════════════════════════════════
    # MONITOR (top-level)
    # ═══════════════════════════════════════════════════════════
    "monitor": ModuleNode(
        name="Monitor",
        full_path="cascade_lattice.Monitor",
        icon="📡",
        category="core",
        parent="cascade_lattice",
        doc_dummy="""
# 📡 Monitor

**What is this?** Your eyes and ears inside the system.

It watches everything happening and can:
- 📝 Record observations
- 🔍 Trace cause and effect
- 🔮 Predict what might happen next
- 🕵️ Find root causes of problems

**Like:** A flight recorder (black box) for AI systems.
        """,
        doc_scientist="""
# Monitor (`cascade_lattice.Monitor`)

Unified observation and causation tracking facade.

```python
class Monitor:
    def __init__(self, component: str): 
        self.component = component
        self._graph = CausationGraph()
        self._adapter = SymbioticAdapter()
    
    def observe(self, signal: Any) -> Event:
        '''Interpret signal and add to causation graph'''
        event = self._adapter.interpret(signal)
        self._graph.add_event(event)
        return event
    
    def analyze_impact(self, event_id: str, max_depth: int = 20) -> ImpactReport:
        '''Forward trace: what did this event cause?'''
    
    def trace_backwards(self, event_id: str, max_depth: int = 10) -> List[CausationChain]:
        '''Backward trace: what caused this event?'''
    
    def trace_forwards(self, event_id: str, max_depth: int = 10) -> List[CausationChain]:
        '''Forward trace: what effects followed?'''
    
    def predict_cascade(self, event: Event) -> List[Event]:
        '''Predict likely downstream effects'''
    
    def find_root_causes(self, event_id: str) -> List[Event]:
        '''Find events with no causes in the subgraph'''
```
        """,
        exports=["Monitor"],
        imports_from=["core.graph", "core.adapter", "core.event"],
        imported_by=["hold.session", "store"],
    ),
}


# ═══════════════════════════════════════════════════════════════
# NAVIGATION STATE
# ═══════════════════════════════════════════════════════════════

@dataclass
class NavState:
    """Navigation breadcrumb trail."""
    path: List[str] = field(default_factory=lambda: ["cascade_lattice"])
    
    @property
    def current(self) -> str:
        return self.path[-1] if self.path else "cascade_lattice"
    
    def push(self, module: str) -> None:
        if module not in self.path:
            self.path.append(module)
    
    def pop(self) -> Optional[str]:
        if len(self.path) > 1:
            return self.path.pop()
        return None
    
    def jump_to(self, module: str) -> None:
        """Jump directly to a module (creative routing)."""
        if module in self.path:
            # Already visited - trim path to that point
            idx = self.path.index(module)
            self.path = self.path[:idx + 1]
        else:
            # New destination - add to path
            self.path.append(module)
    
    def reset(self) -> None:
        self.path = ["cascade_lattice"]


# Global nav state
_nav = NavState()


# ═══════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════

class BreadcrumbWidget(Static):
    """Navigation breadcrumb trail."""
    
    path = reactive(["cascade_lattice"])
    
    def render(self) -> Text:
        text = Text()
        text.append("📍 ", style="bold")
        
        for i, module in enumerate(self.path):
            node = MODULE_GRAPH.get(module)
            icon = node.icon if node else "📦"
            
            if i > 0:
                text.append(" → ", style="dim")
            
            if i == len(self.path) - 1:
                # Current module (highlighted)
                text.append(f"{icon} {module}", style="bold cyan")
            else:
                # Previous modules (clickable look)
                text.append(f"{icon} {module}", style="blue underline")
        
        return text


class ModuleCard(Static):
    """A clickable module card."""
    
    def __init__(self, module_key: str, **kwargs):
        super().__init__(**kwargs)
        self.module_key = module_key
        self.node = MODULE_GRAPH.get(module_key, ModuleNode(name=module_key, full_path=module_key))
    
    def compose(self) -> ComposeResult:
        yield Static(self._render_card(), id=f"card-content-{self.module_key}")
    
    def _render_card(self) -> Text:
        text = Text()
        text.append(f"{self.node.icon} ", style="bold")
        text.append(f"{self.node.name}\n", style="bold cyan")
        
        # Category badge
        cat_colors = {
            "root": "magenta",
            "core": "blue", 
            "hold": "yellow",
            "store": "green",
            "genesis": "red",
            "viz": "cyan",
            "diagnostics": "orange1",
            "forensics": "purple",
        }
        color = cat_colors.get(self.node.category, "white")
        text.append(f"[{self.node.category}]", style=f"bold {color}")
        
        # Export count
        if self.node.exports:
            text.append(f" • {len(self.node.exports)} exports", style="dim")
        
        return text


class RelatedModulesPanel(Vertical):
    """Shows related modules for creative navigation - now with clickable buttons!"""
    
    module_key = reactive("cascade_lattice")
    
    class ModuleClicked(Message):
        """Emitted when a related module is clicked."""
        def __init__(self, module_key: str) -> None:
            self.module_key = module_key
            super().__init__()
    
    def compose(self) -> ComposeResult:
        yield Label("🔗 CONNECTIONS", classes="panel-title")
        yield Vertical(id="related-buttons")
    
    def watch_module_key(self, module_key: str) -> None:
        """Rebuild buttons when module changes."""
        self._rebuild_buttons()
    
    def on_mount(self) -> None:
        self._rebuild_buttons()
    
    def _rebuild_buttons(self) -> None:
        """Rebuild the related module buttons."""
        try:
            container = self.query_one("#related-buttons", Vertical)
            container.remove_children()
        except NoMatches:
            return
        
        node = MODULE_GRAPH.get(self.module_key)
        if not node:
            return
        
        added_keys = set()  # Track what we've added to avoid duplicates
        
        # Parent button
        if node.parent and node.parent not in added_keys:
            parent = MODULE_GRAPH.get(node.parent)
            if parent:
                btn = Button(f"⬆️ {parent.icon} {parent.name}", variant="default", classes="related-btn")
                btn.tooltip = node.parent  # Store module key in tooltip
                container.mount(btn)
                added_keys.add(node.parent)
        
        # Children buttons
        for child_key in node.children:
            if child_key not in added_keys:
                child = MODULE_GRAPH.get(child_key)
                if child:
                    btn = Button(f"⬇️ {child.icon} {child.name}", variant="primary", classes="related-btn")
                    btn.tooltip = child_key
                    container.mount(btn)
                    added_keys.add(child_key)
        
        # Imports from
        for imp in node.imports_from[:3]:
            if imp not in added_keys:
                imp_node = MODULE_GRAPH.get(imp)
                if imp_node:
                    btn = Button(f"📥 {imp_node.icon} {imp_node.name}", variant="success", classes="related-btn")
                    btn.tooltip = imp
                    container.mount(btn)
                    added_keys.add(imp)
        
        # Imported by
        for imp in node.imported_by[:3]:
            if imp not in added_keys:
                imp_node = MODULE_GRAPH.get(imp)
                if imp_node:
                    btn = Button(f"📤 {imp_node.icon} {imp_node.name}", variant="warning", classes="related-btn")
                    btn.tooltip = imp
                    container.mount(btn)
                    added_keys.add(imp)
    
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle related module button click."""
        # Get module key from button tooltip
        module_key = event.button.tooltip
        if module_key and module_key in MODULE_GRAPH:
            self.post_message(self.ModuleClicked(module_key))


class ExportsPanel(Static):
    """Shows exports of current module."""
    
    module_key = reactive("cascade_lattice")
    
    def render(self) -> Text:
        node = MODULE_GRAPH.get(self.module_key)
        if not node or not node.exports:
            return Text("No exports")
        
        text = Text()
        text.append("📦 EXPORTS\n\n", style="bold green")
        
        for exp in node.exports:
            # Guess type from name
            if exp[0].isupper():
                text.append("  ● ", style="cyan")
                text.append(f"{exp}\n", style="bold cyan")
            else:
                text.append("  ○ ", style="yellow")
                text.append(f"{exp}()\n", style="yellow")
        
        return text


class LiveStatsWidget(Static):
    """Live statistics from cascade-lattice store."""
    
    def on_mount(self) -> None:
        self.set_interval(5.0, self._refresh_stats)
        self._refresh_stats()
    
    def _refresh_stats(self) -> None:
        try:
            from cascade_lattice.store import stats
            s = stats()
            self._stats = s
        except Exception as e:
            self._stats = {"error": str(e)}
        self.refresh()
    
    def render(self) -> Text:
        text = Text()
        text.append("📊 LIVE STATS\n\n", style="bold magenta")
        
        if not hasattr(self, '_stats'):
            text.append("Loading...", style="dim")
            return text
        
        s = self._stats
        if "error" in s:
            text.append(f"Error: {s['error']}", style="red")
            return text
        
        text.append(f"Total Observations: ", style="dim")
        text.append(f"{s.get('total_observations', 0):,}\n", style="bold cyan")
        
        text.append(f"Pinned: ", style="dim")
        text.append(f"{s.get('pinned_observations', 0):,}\n", style="green")
        
        text.append(f"Genesis Root: ", style="dim")
        text.append(f"{s.get('genesis_root', 'unknown')}\n", style="bold yellow")
        
        models = s.get('models', {})
        if models:
            text.append(f"\nTop Models:\n", style="dim")
            sorted_models = sorted(models.items(), key=lambda x: x[1], reverse=True)[:5]
            for name, count in sorted_models:
                short_name = name[:25] + "..." if len(name) > 25 else name
                text.append(f"  {short_name}: ", style="white")
                text.append(f"{count:,}\n", style="cyan")
        
        return text


# ═══════════════════════════════════════════════════════════════
# EXPLORER SCREEN
# ═══════════════════════════════════════════════════════════════

class ExplorerScreen(Screen):
    """Main module explorer with graph navigation."""
    
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("h", "go_home", "Home"),
        Binding("t", "toggle_mode", "Toggle Explanation"),
        Binding("s", "go_stats", "Stats"),
        Binding("d", "go_demo", "Demo"),
    ]
    
    # Explanation mode
    scientist_mode = reactive(False)
    current_module = reactive("cascade_lattice")
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="explorer-main"):
            # Top bar with breadcrumb and toggle
            with Horizontal(id="top-bar"):
                yield BreadcrumbWidget(id="breadcrumb")
                yield Switch(value=False, id="mode-toggle")
                yield Label("🧪 Scientist Mode", id="mode-label")
            
            with Horizontal(id="content-area"):
                # Left: Module tree
                with Vertical(id="left-panel"):
                    yield Label("🗂️ MODULES", classes="panel-title")
                    yield Tree("cascade-lattice", id="module-tree")
                
                # Center: Documentation
                with Vertical(id="center-panel"):
                    yield Label("📖 DOCUMENTATION", classes="panel-title")
                    with ScrollableContainer(id="doc-scroll"):
                        yield Markdown("", id="doc-content")
                
                # Right: Related + Exports
                with Vertical(id="right-panel"):
                    yield RelatedModulesPanel(id="related-panel")
                    yield Rule()
                    yield ExportsPanel(id="exports-panel")
        
        yield Footer()
    
    def on_mount(self) -> None:
        self._build_tree()
        self._update_view()
    
    def _build_tree(self) -> None:
        """Build the module tree."""
        tree = self.query_one("#module-tree", Tree)
        tree.clear()
        tree.root.expand()
        tree.show_root = True
        tree.guide_depth = 4
        
        def add_children(parent_node: TreeNode, parent_key: str):
            node = MODULE_GRAPH.get(parent_key)
            if not node:
                return
            
            for child_key in node.children:
                child = MODULE_GRAPH.get(child_key)
                if child:
                    child_node = parent_node.add(
                        f"{child.icon} {child.name}",
                        data=child_key
                    )
                    add_children(child_node, child_key)
        
        # Start with root
        root = MODULE_GRAPH.get("cascade_lattice")
        if root:
            tree.root.set_label(f"{root.icon} cascade_lattice")
            tree.root.data = "cascade_lattice"
            add_children(tree.root, "cascade_lattice")
    
    def _update_view(self) -> None:
        """Update all panels for current module."""
        node = MODULE_GRAPH.get(self.current_module)
        if not node:
            return
        
        # Update breadcrumb
        try:
            self.query_one("#breadcrumb", BreadcrumbWidget).path = list(_nav.path)
        except NoMatches:
            pass
        
        # Update documentation
        doc = node.doc_scientist if self.scientist_mode else node.doc_dummy
        try:
            self.query_one("#doc-content", Markdown).update(doc)
        except NoMatches:
            pass
        
        # Update related panel
        try:
            self.query_one("#related-panel", RelatedModulesPanel).module_key = self.current_module
        except NoMatches:
            pass
        
        # Update exports panel
        try:
            self.query_one("#exports-panel", ExportsPanel).module_key = self.current_module
        except NoMatches:
            pass
    
    @on(Tree.NodeSelected)
    def on_tree_select(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if event.node.data:
            _nav.jump_to(event.node.data)
            self.current_module = event.node.data
            self._update_view()
    
    @on(Switch.Changed, "#mode-toggle")
    def on_mode_toggle(self, event: Switch.Changed) -> None:
        """Toggle scientist/dummy mode."""
        self.scientist_mode = event.value
        self._update_view()
    
    @on(RelatedModulesPanel.ModuleClicked)
    def on_related_clicked(self, event: RelatedModulesPanel.ModuleClicked) -> None:
        """Handle click on related module - creative navigation!"""
        _nav.jump_to(event.module_key)
        self.current_module = event.module_key
        self._update_view()
        # Also expand/select in tree
        self._select_in_tree(event.module_key)
    
    def _select_in_tree(self, module_key: str) -> None:
        """Find and select a module in the tree."""
        try:
            tree = self.query_one("#module-tree", Tree)
            def find_node(node: TreeNode, key: str) -> Optional[TreeNode]:
                if node.data == key:
                    return node
                for child in node.children:
                    found = find_node(child, key)
                    if found:
                        return found
                return None
            
            target = find_node(tree.root, module_key)
            if target:
                target.expand()
                tree.select_node(target)
        except NoMatches:
            pass
    
    def watch_scientist_mode(self, value: bool) -> None:
        """React to mode change."""
        try:
            label = self.query_one("#mode-label", Label)
            if value:
                label.update("🧪 Scientist Mode")
            else:
                label.update("📚 For Dummies")
        except NoMatches:
            pass
    
    def action_go_back(self) -> None:
        """Go back in navigation."""
        popped = _nav.pop()
        if popped:
            self.current_module = _nav.current
            self._update_view()
    
    def action_go_home(self) -> None:
        """Go to root module."""
        _nav.reset()
        self.current_module = "cascade_lattice"
        self._update_view()
    
    def action_toggle_mode(self) -> None:
        """Toggle explanation mode."""
        toggle = self.query_one("#mode-toggle", Switch)
        toggle.value = not toggle.value
    
    def action_go_stats(self) -> None:
        """Switch to stats screen."""
        self.app.switch_mode("stats")
    
    def action_go_demo(self) -> None:
        """Switch to demo screen."""
        self.app.switch_mode("demo")


# ═══════════════════════════════════════════════════════════════
# STATS SCREEN
# ═══════════════════════════════════════════════════════════════

class StatsScreen(Screen):
    """Live statistics dashboard."""
    
    BINDINGS = [
        Binding("escape", "go_explorer", "Explorer"),
        Binding("r", "refresh", "Refresh"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="stats-main"):
            yield Label("📊 CASCADE-LATTICE STATISTICS", classes="screen-title")
            
            with Horizontal(id="stats-row"):
                with Vertical(id="stats-left", classes="panel"):
                    yield LiveStatsWidget(id="live-stats")
                
                with Vertical(id="stats-right", classes="panel"):
                    yield Label("🌅 GENESIS", classes="panel-title")
                    yield Static(id="genesis-info")
                    yield Rule()
                    yield Label("📁 STORE", classes="panel-title")
                    yield Static(id="store-info")
        
        yield Footer()
    
    def on_mount(self) -> None:
        self._load_genesis_info()
        self._load_store_info()
    
    def _load_genesis_info(self) -> None:
        try:
            import cascade_lattice as cl
            text = Text()
            text.append("Genesis Root: ", style="dim")
            text.append(f"{cl.genesis.get_genesis_root()}\n\n", style="bold yellow")
            text.append("Genesis Message:\n", style="dim")
            text.append(f'"{cl.genesis.GENESIS_INPUT}"', style="italic cyan")
            self.query_one("#genesis-info", Static).update(text)
        except Exception as e:
            self.query_one("#genesis-info", Static).update(f"Error: {e}")
    
    def _load_store_info(self) -> None:
        try:
            from cascade_lattice.store import DEFAULT_LATTICE_DIR, CENTRAL_DATASET
            text = Text()
            text.append("Local Store: ", style="dim")
            text.append(f"{DEFAULT_LATTICE_DIR}\n\n", style="cyan")
            text.append("Central Dataset: ", style="dim")
            text.append(f"{CENTRAL_DATASET}\n", style="green")
            self.query_one("#store-info", Static).update(text)
        except Exception as e:
            self.query_one("#store-info", Static).update(f"Error: {e}")
    
    def action_go_explorer(self) -> None:
        self.app.switch_mode("explorer")
    
    def action_refresh(self) -> None:
        self._load_genesis_info()
        self._load_store_info()
        self.notify("Refreshed")


# ═══════════════════════════════════════════════════════════════
# DEMO SCREEN
# ═══════════════════════════════════════════════════════════════

class DemoScreen(Screen):
    """Interactive demo playground."""
    
    BINDINGS = [
        Binding("escape", "go_explorer", "Explorer"),
        Binding("1", "demo_hold", "HOLD Demo"),
        Binding("2", "demo_observe", "Observe Demo"),
        Binding("3", "demo_genesis", "Genesis Demo"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="demo-main"):
            yield Label("🎮 INTERACTIVE DEMOS", classes="screen-title")
            
            with Horizontal(id="demo-buttons"):
                yield Button("⏸️ HOLD Demo", id="btn-hold", variant="primary")
                yield Button("👁️ Observe Demo", id="btn-observe", variant="success")
                yield Button("🌅 Genesis Demo", id="btn-genesis", variant="warning")
                yield Button("🔐 Provenance Demo", id="btn-provenance", variant="default")
            
            with Horizontal(id="demo-content"):
                with Vertical(id="demo-code", classes="panel"):
                    yield Label("📝 CODE", classes="panel-title")
                    yield Static(id="code-display")
                
                with Vertical(id="demo-output", classes="panel"):
                    yield Label("📤 OUTPUT", classes="panel-title")
                    yield RichLog(id="output-log", max_lines=100)
        
        yield Footer()
    
    @on(Button.Pressed, "#btn-hold")
    def on_hold_demo(self) -> None:
        self._run_hold_demo()
    
    @on(Button.Pressed, "#btn-observe")
    def on_observe_demo(self) -> None:
        self._run_observe_demo()
    
    @on(Button.Pressed, "#btn-genesis")
    def on_genesis_demo(self) -> None:
        self._run_genesis_demo()
    
    @on(Button.Pressed, "#btn-provenance")
    def on_provenance_demo(self) -> None:
        self._run_provenance_demo()
    
    def _show_code(self, code: str) -> None:
        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
        self.query_one("#code-display", Static).update(syntax)
    
    def _log(self, message: str, style: str = "white") -> None:
        log = self.query_one("#output-log", RichLog)
        log.write(Text(message, style=style))
    
    def _run_hold_demo(self) -> None:
        code = '''from cascade_lattice import Hold, HoldPoint, HoldState
import numpy as np

# Create a HoldPoint (freeze-frame snapshot)
hp = HoldPoint(
    action_probs=np.array([0.1, 0.3, 0.6]),
    value=0.75,
    observation={"screen": "game_frame_42"},
    brain_id="demo_agent"
)

print(f"HoldPoint ID: {hp.id}")
print(f"Merkle Root: {hp.merkle_root}")
print(f"State: {hp.state}")
print(f"Action Labels: Jump, Duck, Run")'''
        
        self._show_code(code)
        self._log("═══ HOLD DEMO ═══", "bold magenta")
        
        try:
            from cascade_lattice import Hold, HoldPoint, HoldState
            import numpy as np
            
            hp = HoldPoint(
                action_probs=np.array([0.1, 0.3, 0.6]),
                value=0.75,
                observation={"screen": "game_frame_42"},
                brain_id="demo_agent",
                action_labels=["Jump", "Duck", "Run"]
            )
            
            self._log(f"✓ Created HoldPoint", "green")
            self._log(f"  ID: {hp.id}", "cyan")
            self._log(f"  Merkle: {hp.merkle_root}", "yellow")
            self._log(f"  State: {hp.state.value}", "white")
            self._log(f"  Best Action: Run (60%)", "bold cyan")
        except Exception as e:
            self._log(f"✗ Error: {e}", "red")
    
    def _run_observe_demo(self) -> None:
        code = '''from cascade_lattice.store import observe, query, stats

# Create an observation
receipt = observe(
    model_id="demo_model",
    data={"action": "explore", "reward": 1.0},
    sync=False  # Don't sync to HuggingFace
)

print(f"CID: {receipt.cid}")
print(f"Merkle: {receipt.merkle_root}")

# Query recent observations
recent = query("demo_model", limit=5)
print(f"Found {len(recent)} observations")'''
        
        self._show_code(code)
        self._log("═══ OBSERVE DEMO ═══", "bold magenta")
        
        try:
            from cascade_lattice.store import observe, query
            import time
            
            receipt = observe(
                model_id="tui_demo",
                data={"action": "explore", "reward": 1.0, "timestamp": time.time()},
                sync=False
            )
            
            self._log(f"✓ Created Receipt", "green")
            self._log(f"  CID: {receipt.cid[:40]}...", "cyan")
            self._log(f"  Merkle: {receipt.merkle_root}", "yellow")
            
            recent = query("tui_demo", limit=5)
            self._log(f"  Found {len(recent)} total observations", "white")
        except Exception as e:
            self._log(f"✗ Error: {e}", "red")
    
    def _run_genesis_demo(self) -> None:
        code = '''import cascade_lattice as cl

# Get the genesis root
root = cl.genesis.get_genesis_root()
print(f"Genesis Root: {root}")

# The genesis message
print(f"Message: {cl.genesis.GENESIS_INPUT}")

# Create a provenance chain
chain = cl.genesis.create_genesis()
print(f"Chain verified: {chain.verify()}")'''
        
        self._show_code(code)
        self._log("═══ GENESIS DEMO ═══", "bold magenta")
        
        try:
            import cascade_lattice as cl
            
            root = cl.genesis.get_genesis_root()
            self._log(f"✓ Genesis Root: {root}", "bold yellow")
            self._log(f"  \"{cl.genesis.GENESIS_INPUT}\"", "italic cyan")
            
            chain = cl.genesis.create_genesis()
            self._log(f"  Chain Merkle: {chain.merkle_root}", "green")
            self._log(f"  Finalized: {chain.finalized}", "white")
        except Exception as e:
            self._log(f"✗ Error: {e}", "red")
    
    def _run_provenance_demo(self) -> None:
        code = '''from cascade_lattice.core.provenance import (
    hash_tensor, hash_input, compute_merkle_root
)
import numpy as np

# Hash a tensor
tensor = np.random.randn(100).astype(np.float32)
t_hash = hash_tensor(tensor)

# Hash an input
input_data = {"query": "What is 2+2?", "context": []}
i_hash = hash_input(input_data)

# Compute merkle root
root = compute_merkle_root([t_hash, i_hash])
print(f"Merkle Root: {root}")'''
        
        self._show_code(code)
        self._log("═══ PROVENANCE DEMO ═══", "bold magenta")
        
        try:
            from cascade_lattice.core.provenance import (
                hash_tensor, hash_input, compute_merkle_root
            )
            import numpy as np
            
            tensor = np.random.randn(100).astype(np.float32)
            t_hash = hash_tensor(tensor)
            self._log(f"✓ Tensor hash: {t_hash}", "cyan")
            
            input_data = {"query": "What is 2+2?", "context": []}
            i_hash = hash_input(input_data)
            self._log(f"✓ Input hash: {i_hash}", "yellow")
            
            root = compute_merkle_root([t_hash, i_hash])
            self._log(f"✓ Merkle root: {root}", "bold green")
        except Exception as e:
            self._log(f"✗ Error: {e}", "red")
    
    def action_go_explorer(self) -> None:
        self.app.switch_mode("explorer")
    
    def action_demo_hold(self) -> None:
        self._run_hold_demo()
    
    def action_demo_observe(self) -> None:
        self._run_observe_demo()
    
    def action_demo_genesis(self) -> None:
        self._run_genesis_demo()


# ═══════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════

class CascadeLatticeTUI(App):
    """The Cascade-Lattice Explorer TUI."""
    
    TITLE = "🌐 CASCADE-LATTICE"
    SUB_TITLE = "even still, i grow, and yet, I grow still"
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #explorer-main, #stats-main, #demo-main {
        layout: vertical;
        padding: 1;
    }
    
    #top-bar {
        height: 3;
        padding: 0 1;
        align: left middle;
        background: $surface-darken-1;
    }
    
    #breadcrumb {
        width: 1fr;
    }
    
    #mode-toggle {
        width: auto;
        margin-right: 1;
    }
    
    #mode-label {
        width: auto;
    }
    
    #content-area {
        height: 1fr;
    }
    
    #left-panel {
        width: 25%;
        min-width: 30;
        border: solid $primary;
        padding: 1;
    }
    
    #center-panel {
        width: 50%;
        border: solid $secondary;
        padding: 1;
    }
    
    #right-panel {
        width: 25%;
        min-width: 25;
        border: solid $accent;
        padding: 1;
    }
    
    #doc-scroll {
        height: 1fr;
    }
    
    .panel-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }
    
    .screen-title {
        text-style: bold;
        text-align: center;
        color: $primary;
        padding: 1;
    }
    
    #module-tree {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    
    .related-btn {
        width: 100%;
        margin: 0 0 1 0;
    }
    
    #related-buttons {
        height: auto;
        padding: 1 0;
    }
    
    /* Stats screen */
    #stats-row {
        height: 1fr;
    }
    
    #stats-left, #stats-right {
        width: 1fr;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    /* Demo screen */
    #demo-buttons {
        height: auto;
        padding: 1;
        align: center middle;
    }
    
    #demo-buttons Button {
        margin: 0 1;
    }
    
    #demo-content {
        height: 1fr;
    }
    
    #demo-code, #demo-output {
        width: 1fr;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    #code-display {
        height: 1fr;
    }
    
    #output-log {
        height: 1fr;
    }
    
    .panel {
        border: solid $surface-lighten-1;
        padding: 1;
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("e", "go_explorer", "Explorer", show=True),
        Binding("s", "go_stats", "Stats", show=True),
        Binding("d", "go_demo", "Demo", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]
    
    MODES = {
        "explorer": ExplorerScreen,
        "stats": StatsScreen,
        "demo": DemoScreen,
    }
    
    def on_mount(self) -> None:
        """Start on explorer."""
        self.switch_mode("explorer")
    
    def action_go_explorer(self) -> None:
        self.switch_mode("explorer")
    
    def action_go_stats(self) -> None:
        self.switch_mode("stats")
    
    def action_go_demo(self) -> None:
        self.switch_mode("demo")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    """Run the TUI."""
    app = CascadeLatticeTUI()
    app.run()


if __name__ == "__main__":
    main()
