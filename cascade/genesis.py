"""
CASCADE Genesis - The origin node of the neural internetwork.

Every chain begins here. Systems link to genesis (or to any
descendant of genesis) to join the lattice.

The chain IS the registry. No separate discovery needed.

Usage:
    # Create genesis (done once, published to well-known location)
    genesis = create_genesis()
    
    # Any system joins by linking to genesis
    my_chain.link_external(genesis.merkle_root)
    
    # Or by linking to any existing node in the lattice
    my_chain.link_external(some_other_chain.merkle_root)
    
    # The lattice grows. Discovery = reading the chain.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

from cascade.core.provenance import ProvenanceChain, ProvenanceRecord


# Well-known genesis identifiers
GENESIS_SESSION_ID = "genesis_0"
GENESIS_MODEL_ID = "cascade_genesis"
GENESIS_INPUT = "In the beginning was the hash, and the hash was with the chain, and the hash was the chain."


def create_genesis() -> ProvenanceChain:
    """
    Create the genesis chain - origin of the neural internetwork.
    
    This is deterministic. Anyone running this gets the same genesis.
    That's the point - it's the Schelling point for the lattice.
    """
    # Deterministic input hash
    input_hash = hashlib.sha256(GENESIS_INPUT.encode()).hexdigest()[:16]
    
    # Deterministic model hash (hash of the genesis concept itself)
    model_hash = hashlib.sha256(b"cascade_neural_internetwork_v1").hexdigest()[:16]
    
    chain = ProvenanceChain(
        session_id=GENESIS_SESSION_ID,
        model_id=GENESIS_MODEL_ID,
        model_hash=model_hash,
        input_hash=input_hash,
    )
    
    # The genesis record - the first node
    # Its parent is itself (bootstrap)
    genesis_record = ProvenanceRecord(
        layer_name="genesis",
        layer_idx=0,
        state_hash=input_hash,  # Self-referential
        parent_hashes=[input_hash],  # Points to itself
        params_hash=model_hash,
        shape=[1],
        dtype="genesis",
        stats={"created": time.time()},
        execution_order=0,
    )
    
    chain.add_record(genesis_record)
    chain.finalize()
    
    return chain


def get_genesis_root() -> str:
    """
    Get the genesis merkle root.
    
    This is a constant - the Schelling point.
    Any system can compute it and know they're linking to the same origin.
    """
    return create_genesis().merkle_root


def save_genesis(path: Path) -> str:
    """
    Save genesis chain to file.
    
    This file can be published to a well-known location
    (HuggingFace dataset, IPFS, etc.)
    """
    genesis = create_genesis()
    
    with open(path, 'w') as f:
        json.dump(genesis.to_dict(), f, indent=2)
    
    return genesis.merkle_root


def load_genesis(path: Path) -> ProvenanceChain:
    """Load genesis from file and verify it's authentic."""
    with open(path, 'r') as f:
        data = json.load(f)
    
    chain = ProvenanceChain.from_dict(data)
    
    # Verify this is actually genesis
    expected_root = get_genesis_root()
    if chain.merkle_root != expected_root:
        raise ValueError(
            f"Invalid genesis: root {chain.merkle_root} != expected {expected_root}"
        )
    
    return chain


def link_to_genesis(chain: ProvenanceChain) -> None:
    """
    Link a chain to genesis, joining the neural internetwork.
    
    This is the simplest way to join - link directly to the origin.
    Alternatively, link to any other chain that traces back to genesis.
    """
    chain.link_external(get_genesis_root(), source_id="genesis")


def verify_lineage_to_genesis(chain: ProvenanceChain, known_chains: Dict[str, ProvenanceChain]) -> bool:
    """
    Verify that a chain traces back to genesis through external_roots.
    
    Args:
        chain: The chain to verify
        known_chains: Dict mapping merkle_root -> chain for lookup
        
    Returns:
        True if chain traces to genesis, False otherwise
    """
    genesis_root = get_genesis_root()
    visited = set()
    
    def trace(root: str) -> bool:
        if root in visited:
            return False
        visited.add(root)
        
        # Found genesis!
        if root == genesis_root:
            return True
        
        # Look up this chain
        if root not in known_chains:
            return False  # Can't verify - chain not known
        
        c = known_chains[root]
        
        # Check if any external root leads to genesis
        for ext_root in c.external_roots:
            if trace(ext_root):
                return True
        
        return False
    
    # Start from the chain's own root
    return trace(chain.merkle_root) or any(trace(r) for r in chain.external_roots)


# =============================================================================
# CLI for genesis operations
# =============================================================================

if __name__ == "__main__":
    import sys
    
    genesis = create_genesis()
    
    print("=" * 60)
    print("CASCADE GENESIS")
    print("=" * 60)
    print(f"Merkle Root: {genesis.merkle_root}")
    print(f"Session ID:  {genesis.session_id}")
    print(f"Model ID:    {genesis.model_id}")
    print(f"Input Hash:  {genesis.input_hash}")
    print("=" * 60)
    print()
    print("This is the origin of the neural internetwork.")
    print("Any system can link to this root to join the lattice.")
    print()
    print("To join:")
    print("    from cascade.genesis import get_genesis_root")
    print("    my_chain.link_external(get_genesis_root())")
    print()
    
    # Save if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("genesis.json")
        root = save_genesis(out_path)
        print(f"Genesis saved to: {out_path}")
        print(f"Root: {root}")
