"""
CASCADE IPLD - InterPlanetary Linked Data Integration

Native IPLD encoding for provenance chains. Merkle roots become CIDs.
The lattice goes interplanetary.

CIDs (Content IDentifiers) are self-describing, content-addressed identifiers.
When we encode a chain as IPLD, its CID is derived from its content.
Anyone with the CID can fetch and verify.

Architecture:
    ProvenanceChain ──encode──► DAG-CBOR ──hash──► CID
                                                    │
                                     bafyreif...xyz (interplanetary address)
"""

import json
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

# IPLD encoding
import dag_cbor
from multiformats import CID, multihash

# CASCADE core
from cascade.core.provenance import ProvenanceChain, ProvenanceRecord


# =============================================================================
# IPLD ENCODING
# =============================================================================

def chain_to_ipld(chain: ProvenanceChain) -> Dict[str, Any]:
    """
    Convert a ProvenanceChain to IPLD-compatible format.
    
    IPLD format uses:
    - Lowercase keys
    - CID links for references
    - DAG-CBOR encoding
    """
    # Convert records to IPLD format
    records = {}
    for name, record in chain.records.items():
        records[name] = {
            "layer_name": record.layer_name,
            "layer_idx": record.layer_idx,
            "state_hash": record.state_hash,
            "parent_hashes": record.parent_hashes,
            "params_hash": record.params_hash,
            "shape": record.shape,
            "dtype": record.dtype,
            "stats": record.stats,
            "execution_order": record.execution_order,
            "timestamp": record.timestamp,
        }
    
    # Convert external_roots to CID links if they look like CIDs
    external_links = []
    for root in chain.external_roots:
        if root.startswith("bafy") or root.startswith("Qm"):
            # Already a CID - create a link
            external_links.append({"/": root})
        else:
            # Legacy merkle root - keep as string
            external_links.append({"legacy_root": root})
    
    return {
        "session_id": chain.session_id,
        "model_id": chain.model_id,
        "model_hash": chain.model_hash,
        "input_hash": chain.input_hash,
        "output_hash": chain.output_hash,
        "records": records,
        "external_roots": chain.external_roots,  # Keep for verification
        "external_links": external_links,        # IPLD links
        "merkle_root": chain.merkle_root,
        "created_at": chain.created_at,
        "finalized": chain.finalized,
        "ipld_version": 1,
    }


def encode_to_dag_cbor(data: Dict[str, Any]) -> bytes:
    """Encode data as DAG-CBOR (canonical CBOR for IPLD)."""
    return dag_cbor.encode(data)


def decode_from_dag_cbor(raw: bytes) -> Dict[str, Any]:
    """Decode DAG-CBOR data."""
    return dag_cbor.decode(raw)


def compute_cid(data: bytes, codec: str = "dag-cbor") -> str:
    """
    Compute CID (Content IDentifier) from data.
    
    CID = multicodec(codec) + multihash(sha256(data))
    
    Returns CIDv1 in base32 (bafyrei...)
    """
    # SHA-256 hash of the data
    digest = hashlib.sha256(data).digest()
    
    # Create multihash (0x12 = sha2-256, 0x20 = 32 bytes)
    mh = multihash.wrap(digest, "sha2-256")
    
    # Create CID v1 with dag-cbor codec (0x71)
    cid = CID("base32", 1, "dag-cbor", mh)
    
    return str(cid)


def chain_to_cid(chain: ProvenanceChain) -> tuple[str, bytes]:
    """
    Convert chain to CID.
    
    Returns:
        (cid_string, encoded_bytes)
    """
    ipld_data = chain_to_ipld(chain)
    encoded = encode_to_dag_cbor(ipld_data)
    cid = compute_cid(encoded)
    return cid, encoded


# =============================================================================
# IPLD CHAIN - Native CID-based chain
# =============================================================================

@dataclass
class IPLDChain:
    """
    A provenance chain with native CID support.
    
    Instead of custom merkle roots, uses CIDs.
    Links to other chains via CID references.
    """
    chain: ProvenanceChain
    cid: Optional[str] = None
    encoded: Optional[bytes] = None
    
    @classmethod
    def from_chain(cls, chain: ProvenanceChain) -> 'IPLDChain':
        """Create IPLD chain from regular chain."""
        cid, encoded = chain_to_cid(chain)
        return cls(chain=chain, cid=cid, encoded=encoded)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'IPLDChain':
        """Deserialize from DAG-CBOR bytes."""
        ipld_data = decode_from_dag_cbor(data)
        chain = ipld_to_chain(ipld_data)
        cid = compute_cid(data)
        return cls(chain=chain, cid=cid, encoded=data)
    
    def link_to(self, other: 'IPLDChain') -> None:
        """Link this chain to another via CID."""
        if other.cid is None:
            raise ValueError("Cannot link to chain without CID")
        self.chain.link_external(other.cid, source_id=other.chain.model_id)
        # Recompute our CID since we changed
        self.cid, self.encoded = chain_to_cid(self.chain)
    
    def save(self, path: Path) -> None:
        """Save as DAG-CBOR file."""
        if self.encoded is None:
            self.cid, self.encoded = chain_to_cid(self.chain)
        with open(path, 'wb') as f:
            f.write(self.encoded)
    
    @classmethod
    def load(cls, path: Path) -> 'IPLDChain':
        """Load from DAG-CBOR file."""
        with open(path, 'rb') as f:
            data = f.read()
        return cls.from_bytes(data)
    
    def to_json(self) -> str:
        """Export as JSON (for human inspection)."""
        ipld_data = chain_to_ipld(self.chain)
        ipld_data["_cid"] = self.cid
        return json.dumps(ipld_data, indent=2, default=str)


def ipld_to_chain(ipld_data: Dict[str, Any]) -> ProvenanceChain:
    """Convert IPLD data back to ProvenanceChain."""
    # Reconstruct records
    records = {}
    for name, rec_data in ipld_data.get("records", {}).items():
        records[name] = ProvenanceRecord(
            layer_name=rec_data["layer_name"],
            layer_idx=rec_data["layer_idx"],
            state_hash=rec_data["state_hash"],
            parent_hashes=rec_data["parent_hashes"],
            params_hash=rec_data.get("params_hash"),
            shape=rec_data.get("shape", []),
            dtype=rec_data.get("dtype", "float32"),
            stats=rec_data.get("stats", {}),
            execution_order=rec_data.get("execution_order", 0),
            timestamp=rec_data.get("timestamp", 0),
        )
    
    chain = ProvenanceChain(
        session_id=ipld_data["session_id"],
        model_id=ipld_data["model_id"],
        model_hash=ipld_data["model_hash"],
        input_hash=ipld_data["input_hash"],
        output_hash=ipld_data.get("output_hash"),
        external_roots=ipld_data.get("external_roots", []),
        merkle_root=ipld_data.get("merkle_root"),
        created_at=ipld_data.get("created_at", 0),
        finalized=ipld_data.get("finalized", False),
    )
    chain.records = records
    
    return chain


# =============================================================================
# IPFS PUBLISHING (requires running IPFS daemon)
# =============================================================================

def publish_to_ipfs(chain: IPLDChain, ipfs_api: str = "/ip4/127.0.0.1/tcp/5001") -> str:
    """
    Publish chain to IPFS network.
    
    Requires IPFS daemon running locally.
    Returns the CID (which should match our computed CID).
    
    Args:
        chain: IPLDChain to publish
        ipfs_api: IPFS API multiaddr
        
    Returns:
        CID from IPFS (for verification)
    """
    try:
        import ipfshttpclient
        client = ipfshttpclient.connect(ipfs_api)
        
        # Add the raw DAG-CBOR data
        result = client.dag.put(
            chain.encoded,
            store_codec="dag-cbor",
            input_codec="dag-cbor"
        )
        
        ipfs_cid = result["Cid"]["/"]
        
        # Verify CIDs match
        if ipfs_cid != chain.cid:
            print(f"[WARN] CID mismatch: computed={chain.cid}, ipfs={ipfs_cid}")
        
        return ipfs_cid
        
    except Exception as e:
        print(f"[ERROR] IPFS publish failed: {e}")
        print("        Make sure IPFS daemon is running: ipfs daemon")
        raise


def fetch_from_ipfs(cid: str, ipfs_api: str = "/ip4/127.0.0.1/tcp/5001") -> IPLDChain:
    """
    Fetch chain from IPFS network by CID.
    
    Args:
        cid: Content identifier
        ipfs_api: IPFS API multiaddr
        
    Returns:
        IPLDChain
    """
    try:
        import ipfshttpclient
        client = ipfshttpclient.connect(ipfs_api)
        
        # Get the DAG node
        data = client.dag.get(cid)
        
        # Convert to chain
        chain = ipld_to_chain(data)
        encoded = encode_to_dag_cbor(data)
        
        return IPLDChain(chain=chain, cid=cid, encoded=encoded)
        
    except Exception as e:
        print(f"[ERROR] IPFS fetch failed: {e}")
        raise


# =============================================================================
# GENESIS IN IPLD
# =============================================================================

def get_genesis_cid() -> tuple[str, IPLDChain]:
    """
    Get genesis as IPLD chain with CID.
    
    The genesis CID is deterministic - anyone computing it gets the same result.
    This is the interplanetary Schelling point.
    """
    from cascade.genesis import create_genesis
    
    genesis = create_genesis()
    ipld_genesis = IPLDChain.from_chain(genesis)
    
    return ipld_genesis.cid, ipld_genesis


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("CASCADE IPLD - InterPlanetary Linked Data")
    print("=" * 60)
    
    # Get genesis CID
    genesis_cid, genesis_ipld = get_genesis_cid()
    print(f"\nGenesis CID: {genesis_cid}")
    print(f"Genesis merkle_root: {genesis_ipld.chain.merkle_root}")
    
    # Load cascade_alpha and convert to IPLD
    alpha_path = Path("lattice/cascade_alpha.json")
    if alpha_path.exists():
        with open(alpha_path) as f:
            alpha_data = json.load(f)
        alpha_chain = ProvenanceChain.from_dict(alpha_data)
        alpha_ipld = IPLDChain.from_chain(alpha_chain)
        
        print(f"\ncascade_alpha CID: {alpha_ipld.cid}")
        print(f"cascade_alpha merkle_root: {alpha_chain.merkle_root}")
        
        # Save as DAG-CBOR
        out_dir = Path("lattice/ipld")
        out_dir.mkdir(exist_ok=True)
        
        genesis_ipld.save(out_dir / "genesis.cbor")
        alpha_ipld.save(out_dir / "cascade_alpha.cbor")
        
        # Also save JSON for inspection
        with open(out_dir / "genesis.ipld.json", 'w') as f:
            f.write(genesis_ipld.to_json())
        with open(out_dir / "cascade_alpha.ipld.json", 'w') as f:
            f.write(alpha_ipld.to_json())
        
        print(f"\nSaved to {out_dir}/")
        print(f"  - genesis.cbor")
        print(f"  - cascade_alpha.cbor")
        print(f"  - genesis.ipld.json")
        print(f"  - cascade_alpha.ipld.json")
    
    print("\n" + "=" * 60)
    print("INTERPLANETARY ADDRESSES")
    print("=" * 60)
    print(f"""
Genesis:       {genesis_cid}
cascade_alpha: {alpha_ipld.cid if alpha_path.exists() else 'N/A'}

These CIDs are content-addressed. Anyone with the CID can:
1. Fetch the data from IPFS (if pinned)
2. Verify the content matches the CID
3. Trust the chain without trusting the source

To publish to IPFS:
    ipfs daemon  # Start IPFS
    python -c "
    from cascade.ipld import publish_to_ipfs, get_genesis_cid
    _, genesis = get_genesis_cid()
    cid = publish_to_ipfs(genesis)
    print(f'Published: {{cid}}')
    "
    """)
