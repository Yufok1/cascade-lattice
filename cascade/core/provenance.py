"""
CASCADE // PROVENANCE ENGINE
Cryptographic lineage tracking for neural network activations.

Due process infrastructure for AI - immutable evidence chains
that enable governance without prescribing decisions.

Architecture:
    Input → [Layer₀] → [Layer₁] → ... → [Layerₙ] → Output
              │          │                │
              ▼          ▼                ▼
            Hash₀ ──► Hash₁ ──► ... ──► Hashₙ
              │                           │
              └───────── Merkle Root ─────┘

Each hash includes:
    - Tensor state (sampled for efficiency)
    - Parent hashes (inputs to this layer)
    - Layer identity (name, params hash)
    - Execution context (order, timestamp)

This creates verifiable, tamper-evident records of
what happened inside the network.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict
import numpy as np


@dataclass
class ProvenanceRecord:
    """Immutable record of a single layer's activation state."""
    
    # Identity
    layer_name: str
    layer_idx: int
    
    # Lineage
    state_hash: str                    # Hash of this layer's output
    parent_hashes: List[str]           # Hashes of inputs (usually 1, but attention has multiple)
    params_hash: Optional[str] = None  # Hash of layer weights (frozen reference)
    
    # Tensor metadata
    shape: List[int] = field(default_factory=list)
    dtype: str = "float32"
    
    # Statistics (for visualization, not hashed)
    stats: Dict[str, float] = field(default_factory=dict)
    
    # Execution context
    execution_order: int = 0
    timestamp: float = field(default_factory=time.time)
    
    # Merkle tree position
    merkle_depth: int = 0
    merkle_path: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON export."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProvenanceRecord':
        """Deserialize from JSON."""
        return cls(**data)


@dataclass  
class ProvenanceChain:
    """Complete provenance chain for a forward pass."""
    
    # Session identity
    session_id: str
    model_id: str
    model_hash: str
    
    # Input/output
    input_hash: str
    output_hash: Optional[str] = None
    
    # The chain itself
    records: Dict[str, ProvenanceRecord] = field(default_factory=OrderedDict)
    
    # External system roots (for inter-system linking)
    # When this chain depends on another system's computation,
    # include their merkle_root here. This creates the lattice.
    external_roots: List[str] = field(default_factory=list)
    
    # Merkle root (computed after chain complete)
    merkle_root: Optional[str] = None
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    finalized: bool = False
    
    def add_record(self, record: ProvenanceRecord) -> None:
        """Add a record to the chain. Chain must not be finalized."""
        if self.finalized:
            raise ValueError("Cannot add to finalized chain")
        self.records[record.layer_name] = record
    
    def finalize(self) -> str:
        """Compute Merkle root and lock the chain."""
        if self.finalized:
            return self.merkle_root
        
        # Build Merkle tree from record hashes + external roots
        # External roots create cryptographic proof of inter-system dependency
        hashes = [r.state_hash for r in self.records.values()]
        hashes.extend(self.external_roots)  # Include external system roots
        self.merkle_root = compute_merkle_root(hashes)
        self.finalized = True
        return self.merkle_root
    
    def verify(self) -> Tuple[bool, Optional[str]]:
        """Verify chain integrity."""
        if not self.finalized:
            return False, "Chain not finalized"
        
        # Recompute Merkle root (including external roots)
        hashes = [r.state_hash for r in self.records.values()]
        hashes.extend(self.external_roots)  # Must include external roots
        computed_root = compute_merkle_root(hashes)
        
        if computed_root != self.merkle_root:
            return False, f"Merkle root mismatch: {computed_root} != {self.merkle_root}"
        
        return True, None
    
    def link_external(self, external_merkle_root: str, source_id: str = None) -> None:
        """
        Link this chain to another system's merkle root.
        
        This creates the neural internetwork - cryptographic proof
        that this computation depended on another system's output.
        
        Args:
            external_merkle_root: The merkle root from the external system
            source_id: Optional identifier of the source system
        """
        if self.finalized:
            raise ValueError("Cannot link external root to finalized chain")
        self.external_roots.append(external_merkle_root)
    
    def get_lineage(self, layer_name: str) -> List[ProvenanceRecord]:
        """Trace back from a layer to its ancestors."""
        if layer_name not in self.records:
            return []
        
        lineage = []
        current = self.records[layer_name]
        visited = set()
        
        def trace_back(record: ProvenanceRecord):
            if record.layer_name in visited:
                return
            visited.add(record.layer_name)
            lineage.append(record)
            
            for parent_hash in record.parent_hashes:
                # Find record with this hash
                for r in self.records.values():
                    if r.state_hash == parent_hash:
                        trace_back(r)
                        break
        
        trace_back(current)
        return lineage
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize entire chain."""
        return {
            "session_id": self.session_id,
            "model_id": self.model_id,
            "model_hash": self.model_hash,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "external_roots": self.external_roots,  # Inter-system links
            "merkle_root": self.merkle_root,
            "created_at": self.created_at,
            "finalized": self.finalized,
            "records": {k: v.to_dict() for k, v in self.records.items()}
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Export as JSON."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProvenanceChain':
        """Deserialize from dict."""
        records = OrderedDict()
        for k, v in data.get("records", {}).items():
            records[k] = ProvenanceRecord.from_dict(v)
        
        chain = cls(
            session_id=data["session_id"],
            model_id=data["model_id"],
            model_hash=data["model_hash"],
            input_hash=data["input_hash"],
            output_hash=data.get("output_hash"),
            external_roots=data.get("external_roots", []),  # Inter-system links
            merkle_root=data.get("merkle_root"),
            created_at=data.get("created_at", time.time()),
            finalized=data.get("finalized", False),
        )
        chain.records = records
        return chain


# =============================================================================
# HASHING FUNCTIONS
# =============================================================================

def hash_tensor(tensor, sample_size: int = 1000) -> str:
    """
    Compute deterministic hash of tensor state.
    
    Samples tensor for efficiency - full hash would be too slow
    for large activations. Sample is deterministic (first N elements
    after flatten) so hash is reproducible.
    
    Args:
        tensor: PyTorch tensor or numpy array
        sample_size: Number of elements to sample
        
    Returns:
        16-character hex hash
    """
    # Convert to numpy if needed
    if hasattr(tensor, 'detach'):
        # PyTorch tensor
        arr = tensor.detach().cpu().float().numpy()
    elif hasattr(tensor, 'numpy'):
        arr = tensor.numpy()
    else:
        arr = np.array(tensor)
    
    # Flatten and sample
    flat = arr.flatten()
    sample = flat[:min(sample_size, len(flat))]
    
    # Hash the bytes
    # Include shape in hash so same values in different shapes hash differently
    shape_bytes = str(arr.shape).encode('utf-8')
    tensor_bytes = sample.astype(np.float32).tobytes()
    
    combined = shape_bytes + tensor_bytes
    return hashlib.sha256(combined).hexdigest()[:16]


def hash_params(module) -> str:
    """
    Hash a module's parameters (weights, biases).
    
    This creates a frozen reference to the model state at observation time.
    If weights change, this hash changes.
    """
    param_hashes = []
    
    for name, param in module.named_parameters(recurse=False):
        if param is not None:
            h = hash_tensor(param.data, sample_size=500)
            param_hashes.append(f"{name}:{h}")
    
    if not param_hashes:
        return "no_params"
    
    combined = "|".join(sorted(param_hashes))
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def hash_model(model) -> str:
    """
    Hash entire model state.
    
    This is the model's identity hash - changes if any weight changes.
    """
    all_hashes = []
    
    for name, param in model.named_parameters():
        h = hash_tensor(param.data, sample_size=100)
        all_hashes.append(f"{name}:{h}")
    
    combined = "|".join(all_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def hash_input(data: Any) -> str:
    """
    Hash input data (text, tokens, images, etc).
    """
    if isinstance(data, str):
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
    elif hasattr(data, 'detach'):
        return hash_tensor(data)
    elif isinstance(data, dict):
        # Tokenizer output
        combined = json.dumps({k: str(v) for k, v in sorted(data.items())})
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    else:
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]


def compute_merkle_root(hashes: List[str]) -> str:
    """
    Compute Merkle root from list of hashes.
    
    Standard Merkle tree construction - pairs hashes bottom-up
    until single root remains.
    """
    if not hashes:
        return hashlib.sha256(b"empty").hexdigest()[:16]
    
    if len(hashes) == 1:
        return hashes[0]
    
    # Pad to even length
    if len(hashes) % 2 == 1:
        hashes = hashes + [hashes[-1]]
    
    # Compute next level
    next_level = []
    for i in range(0, len(hashes), 2):
        combined = hashes[i] + hashes[i + 1]
        next_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        next_level.append(next_hash)
    
    return compute_merkle_root(next_level)


# =============================================================================
# PROVENANCE TRACKER (attaches to model)
# =============================================================================

class ProvenanceTracker:
    """
    Tracks provenance during model forward pass.
    
    Usage:
        tracker = ProvenanceTracker(model, model_id="gpt2")
        tracker.start_session(input_text)
        
        # Run forward pass - hooks capture everything
        output = model(**inputs)
        
        chain = tracker.finalize_session()
        print(chain.merkle_root)
    
    NEW: Now writes to tape file (JSONL) for redundant logging!
    Correlative with the Live Tracer - both systems log independently.
    """
    
    def __init__(self, model, model_id: str, log_dir: str = "./logs"):
        self.model = model
        self.model_id = model_id
        self.model_hash = hash_model(model)
        
        self.hooks = []
        self.current_chain: Optional[ProvenanceChain] = None
        self.execution_counter = 0
        self.last_hash = None  # Track for parent linking
        self.layer_hashes: Dict[str, str] = {}  # layer_name -> hash
        
        # === TAPE FILE FOR REDUNDANT LOGGING ===
        from pathlib import Path
        from threading import Lock
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = int(time.time())
        self._tape_path = self._log_dir / f"provenance_tape_{self._session_id}.jsonl"
        self._tape_file = None
        self._tape_lock = Lock()
        self._record_count = 0
        
    def start_session(self, input_data: Any) -> str:
        """Start a new provenance tracking session."""
        import uuid
        
        session_id = str(uuid.uuid4())[:8]
        input_hash = hash_input(input_data)
        
        self.current_chain = ProvenanceChain(
            session_id=session_id,
            model_id=self.model_id,
            model_hash=self.model_hash,
            input_hash=input_hash
        )
        
        self.execution_counter = 0
        self.last_hash = input_hash
        self.layer_hashes = {"input": input_hash}
        
        # Register hooks
        self._register_hooks()
        
        return session_id
    
    def _register_hooks(self):
        """Register forward hooks on all modules."""
        self._remove_hooks()  # Clean up any existing
        
        for name, module in self.model.named_modules():
            if name:  # Skip root
                hook = module.register_forward_hook(
                    self._make_hook(name)
                )
                self.hooks.append(hook)
    
    def _make_hook(self, layer_name: str):
        """Create a forward hook for a specific layer."""
        def hook(module, inp, out):
            # Extract tensor
            tensor = None
            if hasattr(out, 'detach'):
                tensor = out
            elif isinstance(out, tuple) and len(out) > 0 and hasattr(out[0], 'detach'):
                tensor = out[0]
            elif hasattr(out, 'last_hidden_state'):
                tensor = out.last_hidden_state
            elif hasattr(out, 'logits'):
                tensor = out.logits
            
            if tensor is None or not hasattr(tensor, 'numel') or tensor.numel() == 0:
                return
            
            # Compute hashes
            state_hash = hash_tensor(tensor)
            params_hash = hash_params(module)
            
            # Determine parent hashes
            # For now, use last layer's hash. More sophisticated: track actual data flow.
            parent_hashes = [self.last_hash] if self.last_hash else []
            
            # Compute stats
            t = tensor.float()
            stats = {
                "mean": t.mean().item(),
                "std": t.std().item(),
                "min": t.min().item(),
                "max": t.max().item(),
                "sparsity": (tensor == 0).float().mean().item(),
            }
            
            # Create record
            record = ProvenanceRecord(
                layer_name=layer_name,
                layer_idx=self.execution_counter,
                state_hash=state_hash,
                parent_hashes=parent_hashes,
                params_hash=params_hash,
                shape=list(tensor.shape),
                dtype=str(tensor.dtype),
                stats=stats,
                execution_order=self.execution_counter,
            )
            
            # Add to chain
            if self.current_chain:
                self.current_chain.add_record(record)
            
            # === WRITE TO TAPE (REDUNDANT LOGGING) ===
            self._write_to_tape(record)
            
            # Update tracking
            self.last_hash = state_hash
            self.layer_hashes[layer_name] = state_hash
            self.execution_counter += 1
            self._record_count += 1
        
        return hook
    
    def _write_to_tape(self, record: ProvenanceRecord):
        """Write provenance record to tape file for redundant logging."""
        import json
        try:
            with self._tape_lock:
                if self._tape_file is None:
                    self._tape_file = open(self._tape_path, "a", encoding="utf-8")
                    print(f"[CASCADE] 📼 Provenance tape started: {self._tape_path}")
                
                tape_record = {
                    "seq": self._record_count,
                    "record": record.to_dict(),
                    "session_id": self._session_id,
                    "model_id": self.model_id,
                }
                self._tape_file.write(json.dumps(tape_record, default=str) + "\n")
                self._tape_file.flush()
        except Exception as e:
            pass  # Don't let tape errors break the main flow
    
    def close_tape(self):
        """Close the tape file."""
        with self._tape_lock:
            if self._tape_file:
                self._tape_file.close()
                self._tape_file = None
                print(f"[CASCADE] 📼 Provenance tape closed: {self._record_count} records → {self._tape_path}")
    
    def get_tape_path(self):
        """Get the current tape file path."""
        return self._tape_path
    
    def _remove_hooks(self):
        """Remove all registered hooks."""
        for hook in self.hooks:
            hook.remove()
        self.hooks = []
    
    def finalize_session(self, output_data: Any = None) -> ProvenanceChain:
        """Finalize session, compute Merkle root, return chain."""
        self._remove_hooks()
        
        if self.current_chain is None:
            raise ValueError("No active session")
        
        if output_data is not None:
            self.current_chain.output_hash = hash_input(output_data)
        
        self.current_chain.finalize()
        
        # Close tape (session complete)
        self.close_tape()
        
        chain = self.current_chain
        self.current_chain = None
        
        return chain


# =============================================================================
# VERIFICATION & COMPARISON
# =============================================================================

def verify_chain(chain: ProvenanceChain) -> Tuple[bool, str]:
    """Verify a provenance chain's integrity."""
    return chain.verify()


def compare_chains(chain_a: ProvenanceChain, chain_b: ProvenanceChain) -> Dict[str, Any]:
    """
    Compare two provenance chains.
    
    Useful for:
    - Same model, different inputs (where did outputs diverge?)
    - Different models, same input (structural comparison)
    - Same everything (reproducibility check)
    """
    result = {
        "model_match": chain_a.model_hash == chain_b.model_hash,
        "input_match": chain_a.input_hash == chain_b.input_hash,
        "output_match": chain_a.output_hash == chain_b.output_hash,
        "merkle_match": chain_a.merkle_root == chain_b.merkle_root,
        "divergence_points": [],
        "a_only_layers": [],
        "b_only_layers": [],
        "matching_layers": [],
    }
    
    a_layers = set(chain_a.records.keys())
    b_layers = set(chain_b.records.keys())
    
    result["a_only_layers"] = list(a_layers - b_layers)
    result["b_only_layers"] = list(b_layers - a_layers)
    
    # Compare matching layers
    for layer in a_layers & b_layers:
        rec_a = chain_a.records[layer]
        rec_b = chain_b.records[layer]
        
        if rec_a.state_hash == rec_b.state_hash:
            result["matching_layers"].append(layer)
        else:
            result["divergence_points"].append({
                "layer": layer,
                "hash_a": rec_a.state_hash,
                "hash_b": rec_b.state_hash,
                "stats_a": rec_a.stats,
                "stats_b": rec_b.stats,
            })
    
    return result


def export_chain_for_audit(chain: ProvenanceChain, filepath: str) -> None:
    """Export chain to file for external audit."""
    with open(filepath, 'w') as f:
        f.write(chain.to_json(indent=2))


def import_chain_for_audit(filepath: str) -> ProvenanceChain:
    """Import chain from audit file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return ProvenanceChain.from_dict(data)
