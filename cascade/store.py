"""
CASCADE Store - Simple observe/query interface with HuggingFace

The goal: make it as easy as possible to store and retrieve provenance.

    from cascade.store import observe, query
    
    # Write - saves locally + syncs to HuggingFace
    receipt = observe(model_id="crafter", data={"reward": 2.1, "step": 100})
    print(receipt.cid)  # bafyrei... (content hash for verification)
    
    # Read - queries local store + HuggingFace
    past = query(model_id="crafter")
    for obs in past:
        print(obs["reward"], obs["cid"])

Architecture:
    1. Local SQLite index (fast queries)
    2. CBOR files for full data (content-addressed)
    3. HuggingFace datasets for sync (unlimited, free)
    4. CIDs computed for verification (no IPFS daemon needed)

Dual-write model:
    - User's own HF dataset (they own their data)
    - Central cascade-observations dataset (Dreamer sees everything)

No daemon. No server. Just `huggingface-cli login` once.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import dag_cbor
from multiformats import CID, multihash

from cascade.genesis import get_genesis_root


# =============================================================================
# CONSTANTS
# =============================================================================

# HuggingFace datasets - UNLIMITED FREE STORAGE
CENTRAL_DATASET = "tostido/cascade-observations"  # Dreamer reads this
USER_DATASET = os.environ.get("CASCADE_USER_DATASET")  # Optional: user's own dataset

# Default lattice directory (local cache)
DEFAULT_LATTICE_DIR = Path.home() / ".cascade" / "lattice"

# IPFS gateways for fallback
IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://dweb.link/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
]


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Receipt:
    """
    A provenance receipt - proof that an observation happened.
    
    Content-addressed via CID. Can be verified by anyone.
    """
    cid: str                    # IPFS content identifier
    model_id: str               # What model/system was observed
    merkle_root: str            # Chain hash (legacy compat)
    timestamp: float            # When
    data: Dict[str, Any]        # The observation data
    parent_cid: Optional[str] = None  # Links to previous observation
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cid": self.cid,
            "model_id": self.model_id,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "data": self.data,
            "parent_cid": self.parent_cid,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Receipt":
        return cls(
            cid=d["cid"],
            model_id=d["model_id"],
            merkle_root=d["merkle_root"],
            timestamp=d["timestamp"],
            data=d["data"],
            parent_cid=d.get("parent_cid"),
        )


# =============================================================================
# CONTENT ADDRESSING
# =============================================================================

def compute_cid(data: bytes) -> str:
    """
    Compute CIDv1 (base32) from bytes.
    
    CID = multicodec(dag-cbor) + multihash(sha256(data))
    """
    digest = hashlib.sha256(data).digest()
    mh = multihash.wrap(digest, "sha2-256")
    cid = CID("base32", 1, "dag-cbor", mh)
    return str(cid)


def data_to_cid(data: Dict[str, Any]) -> tuple[str, bytes]:
    """Convert dict to (CID, encoded bytes)."""
    encoded = dag_cbor.encode(data)
    cid = compute_cid(encoded)
    return cid, encoded


# =============================================================================
# LOCAL STORE
# =============================================================================

class LocalStore:
    """
    SQLite-backed local store with CBOR files.
    
    Fast queries via SQLite index.
    Full data in content-addressed CBOR files.
    """
    
    def __init__(self, lattice_dir: Path = None):
        self.lattice_dir = lattice_dir or DEFAULT_LATTICE_DIR
        self.lattice_dir.mkdir(parents=True, exist_ok=True)
        
        self.cbor_dir = self.lattice_dir / "cbor"
        self.cbor_dir.mkdir(exist_ok=True)
        
        self.db_path = self.lattice_dir / "index.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                cid TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                merkle_root TEXT NOT NULL,
                timestamp REAL NOT NULL,
                parent_cid TEXT,
                pinned INTEGER DEFAULT 0,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_id ON observations(model_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON observations(timestamp DESC)
        """)
        conn.commit()
        conn.close()
    
    def save(self, receipt: Receipt) -> str:
        """Save receipt to local store. Returns CID."""
        # Save CBOR file
        data = receipt.to_dict()
        cid, encoded = data_to_cid(data)
        
        cbor_path = self.cbor_dir / f"{cid}.cbor"
        cbor_path.write_bytes(encoded)
        
        # Update receipt with computed CID (may differ if data changed)
        receipt.cid = cid
        
        # Index in SQLite
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO observations 
            (cid, model_id, merkle_root, timestamp, parent_cid)
            VALUES (?, ?, ?, ?, ?)
        """, (cid, receipt.model_id, receipt.merkle_root, 
              receipt.timestamp, receipt.parent_cid))
        conn.commit()
        conn.close()
        
        return cid
    
    def get(self, cid: str) -> Optional[Receipt]:
        """Get receipt by CID."""
        cbor_path = self.cbor_dir / f"{cid}.cbor"
        if not cbor_path.exists():
            return None
        
        data = dag_cbor.decode(cbor_path.read_bytes())
        return Receipt.from_dict(data)
    
    def query(
        self,
        model_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[Receipt]:
        """Query receipts with filters."""
        conn = sqlite3.connect(self.db_path)
        
        sql = "SELECT cid FROM observations WHERE 1=1"
        params = []
        
        if model_id:
            sql += " AND model_id = ?"
            params.append(model_id)
        
        if since:
            sql += " AND timestamp > ?"
            params.append(since)
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(sql, params)
        cids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Load full receipts
        receipts = []
        for cid in cids:
            receipt = self.get(cid)
            if receipt:
                receipts.append(receipt)
        
        return receipts
    
    def get_latest(self, model_id: str) -> Optional[Receipt]:
        """Get most recent receipt for a model."""
        results = self.query(model_id=model_id, limit=1)
        return results[0] if results else None
    
    def count(self, model_id: Optional[str] = None) -> int:
        """Count observations."""
        conn = sqlite3.connect(self.db_path)
        if model_id:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM observations WHERE model_id = ?",
                (model_id,)
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM observations")
        count = cursor.fetchone()[0]
        conn.close()
        return count


# =============================================================================
# IPFS GATEWAY ACCESS
# =============================================================================

def fetch_from_gateway(cid: str, timeout: float = 10.0) -> Optional[bytes]:
    """
    Fetch data from public IPFS gateways.
    
    Tries multiple gateways in sequence.
    No daemon needed.
    """
    import requests
    
    for gateway in IPFS_GATEWAYS:
        url = f"{gateway}{cid}"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            continue
    
    return None


def fetch_receipt(cid: str, local_store: LocalStore = None) -> Optional[Receipt]:
    """
    Fetch receipt by CID, checking local store first, then IPFS.
    """
    # Check local first
    if local_store:
        receipt = local_store.get(cid)
        if receipt:
            return receipt
    
    # Try IPFS gateways
    data = fetch_from_gateway(cid)
    if data:
        try:
            decoded = dag_cbor.decode(data)
            receipt = Receipt.from_dict(decoded)
            
            # Cache locally
            if local_store:
                local_store.save(receipt)
            
            return receipt
        except Exception:
            pass
    
    return None


# =============================================================================
# HUGGINGFACE SYNC - Unlimited free storage
# =============================================================================

# (Uses constants from top of file: CENTRAL_DATASET, USER_DATASET)


def _upload_to_hf(filepath: Path, cid: str, dataset_id: str) -> bool:
    """Upload a single observation to a HuggingFace dataset."""
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        api.upload_file(
            path_or_fileobj=str(filepath),
            path_in_repo=f"observations/{cid}.cbor",
            repo_id=dataset_id,
            repo_type="dataset",
        )
        return True
    except Exception:
        return False


def sync_observation(cid: str, filepath: Path) -> dict:
    """
    Sync a single observation to HuggingFace.
    
    Dual-write:
    1. Central dataset (jtwspace/cascade-observations) - Dreamer sees all
    2. User's dataset (if CASCADE_USER_DATASET set) - they own their data
    """
    results = {"central": False, "user": False}
    
    # Always sync to central
    results["central"] = _upload_to_hf(filepath, cid, CENTRAL_DATASET)
    
    # Optionally sync to user's dataset
    if USER_DATASET:
        results["user"] = _upload_to_hf(filepath, cid, USER_DATASET)
    
    return results


def sync_all() -> dict:
    """
    Sync all local observations to HuggingFace.
    
    Returns:
        {"synced": count, "failed": count}
    """
    store = _get_store()
    cbor_files = list(store.cbor_dir.glob("*.cbor"))
    
    synced = 0
    failed = 0
    
    for cbor_path in cbor_files:
        cid = cbor_path.stem
        results = sync_observation(cid, cbor_path)
        
        if results["central"]:
            synced += 1
            conn = sqlite3.connect(store.db_path)
            conn.execute("UPDATE observations SET pinned = 1 WHERE cid = ?", (cid,))
            conn.commit()
            conn.close()
        else:
            failed += 1
    
    return {"synced": synced, "failed": failed}


def pull_from_hf(dataset_id: str = None) -> int:
    """
    Pull observations from a HuggingFace dataset.
    
    Args:
        dataset_id: HF dataset (default: central dataset)
    
    Returns:
        Number of observations pulled
    """
    try:
        from huggingface_hub import HfApi, hf_hub_download, list_repo_files
    except ImportError:
        print("pip install huggingface_hub")
        return 0
    
    store = _get_store()
    dataset_id = dataset_id or CENTRAL_DATASET
    
    # List observation files
    try:
        files = list_repo_files(dataset_id, repo_type="dataset")
        obs_files = [f for f in files if f.startswith("observations/") and f.endswith(".cbor")]
    except Exception as e:
        print(f"Could not list dataset: {e}")
        return 0
    
    pulled = 0
    for file_path in obs_files:
        cid = file_path.replace("observations/", "").replace(".cbor", "")
        
        local_path = store.cbor_dir / f"{cid}.cbor"
        if local_path.exists():
            continue
        
        try:
            downloaded = hf_hub_download(
                repo_id=dataset_id,
                filename=file_path,
                repo_type="dataset",
                local_dir=str(store.lattice_dir / "_hf_cache"),
            )
            
            import shutil
            shutil.copy(downloaded, local_path)
            
            data = dag_cbor.decode(local_path.read_bytes())
            receipt = Receipt.from_dict(data)
            
            conn = sqlite3.connect(store.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO observations 
                (cid, model_id, merkle_root, timestamp, parent_cid, pinned)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (cid, receipt.model_id, receipt.merkle_root, 
                  receipt.timestamp, receipt.parent_cid))
            conn.commit()
            conn.close()
            
            pulled += 1
            
        except Exception as e:
            print(f"Pull error for {cid[:16]}: {e}")
    
    return pulled


# =============================================================================
# PUBLIC API
# =============================================================================

# Global store instance
_store: Optional[LocalStore] = None


def _get_store() -> LocalStore:
    """Get or create global store."""
    global _store
    if _store is None:
        _store = LocalStore()
    return _store


def _json_default(obj):
    """Handle non-serializable types like numpy scalars."""
    if hasattr(obj, "item") and callable(obj.item):
        return obj.item()
    return str(obj)


def _sanitize(data: Any) -> Any:
    """Recursively convert numpy types to python types."""
    if isinstance(data, dict):
        return {k: _sanitize(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_sanitize(x) for x in data]
    elif hasattr(data, "item") and callable(data.item):
        return data.item()
    return data


def observe(
    model_id: str,
    data: Dict[str, Any],
    parent_cid: Optional[str] = None,
    sync: bool = True,
) -> Receipt:
    """
    Record an observation.
    
    Args:
        model_id: Identifier for the model/system (e.g., "crafter", "gpt-4")
        data: Observation data (any JSON-serializable dict)
        parent_cid: Optional CID of previous observation (for chains)
        sync: Whether to sync to HuggingFace (default: True)
    
    Returns:
        Receipt with CID
    
    Example:
        receipt = observe("crafter", {"reward": 2.1, "step": 100})
        print(receipt.cid)  # bafyrei...
    """
    store = _get_store()
    
    # Sanitize data to ensure JSON/CBOR serializability (numpy types -> python)
    data = _sanitize(data)
    
    # Get parent if chaining
    if parent_cid is None:
        latest = store.get_latest(model_id)
        if latest:
            parent_cid = latest.cid
    
    # Compute merkle root (legacy compat)
    # Using default=_json_default to handle numpy types often found in AI systems
    merkle_data = f"{model_id}:{json.dumps(data, sort_keys=True, default=_json_default)}:{time.time()}"
    merkle_root = hashlib.sha256(merkle_data.encode()).hexdigest()[:16]
    
    # Link to genesis
    genesis_root = get_genesis_root()
    data["_genesis"] = genesis_root
    data["_model_id"] = model_id
    
    # Create receipt
    receipt = Receipt(
        cid="",  # Will be computed
        model_id=model_id,
        merkle_root=merkle_root,
        timestamp=time.time(),
        data=data,
        parent_cid=parent_cid,
    )
    
    # Save locally (computes CID)
    cid = store.save(receipt)
    receipt.cid = cid
    
    # Auto-sync to HuggingFace (best-effort, non-blocking)
    if sync:
        try:
            sync_observation(cid, store.cbor_dir / f"{cid}.cbor")
        except Exception:
            pass  # Local save succeeded, that's what matters
    
    return receipt


def query(
    model_id: Optional[str] = None,
    since: Optional[float] = None,
    limit: int = 100,
    include_remote: bool = False,
) -> List[Receipt]:
    """
    Query observations.
    
    Args:
        model_id: Filter by model ID
        since: Only observations after this timestamp
        limit: Maximum results
        include_remote: Also search IPFS gateways (slower)
    
    Returns:
        List of receipts
    
    Example:
        # Get all crafter observations
        for receipt in query(model_id="crafter"):
            print(receipt.data["reward"])
    """
    store = _get_store()
    return store.query(model_id=model_id, since=since, limit=limit)


def get(cid: str) -> Optional[Receipt]:
    """
    Get a specific observation by CID.
    
    Checks local store first, then IPFS gateways.
    """
    store = _get_store()
    return fetch_receipt(cid, store)


# =============================================================================
# DISCOVERY - Leverages HuggingFace's catalog
# =============================================================================

def discover_models(dataset_id: str = None) -> Dict[str, int]:
    """
    Discover all model_ids in the lattice by scanning HuggingFace.
    
    HuggingFace IS the catalog - we just read it.
    
    Returns:
        Dict mapping model_id -> observation count
    """
    dataset_id = dataset_id or CENTRAL_DATASET
    
    try:
        from huggingface_hub import list_repo_files
        files = list_repo_files(dataset_id, repo_type="dataset")
        
        # Parse model_ids from observation files
        # Files are stored as: observations/{cid}.cbor
        # We need to actually read to get model_id, OR
        # use a manifest/index file
        
        # For now, return local knowledge + count remote files
        store = _get_store()
        local_models = {}
        
        conn = sqlite3.connect(store.db_path)
        rows = conn.execute(
            "SELECT model_id, COUNT(*) FROM observations GROUP BY model_id"
        ).fetchall()
        conn.close()
        
        for model_id, count in rows:
            local_models[model_id] = count
        
        # Count total remote files
        remote_count = len([f for f in files if f.startswith("observations/") and f.endswith(".cbor")])
        
        return {
            "local_models": local_models,
            "remote_observation_count": remote_count,
            "dataset": dataset_id,
        }
        
    except ImportError:
        # No huggingface_hub - return local only
        store = _get_store()
        conn = sqlite3.connect(store.db_path)
        rows = conn.execute(
            "SELECT model_id, COUNT(*) FROM observations GROUP BY model_id"
        ).fetchall()
        conn.close()
        return {"local_models": {m: c for m, c in rows}, "remote": "unavailable"}
    
    except Exception as e:
        return {"error": str(e)}


def discover_datasets(query_str: str = "cascade") -> List[Dict[str, Any]]:
    """
    Search HuggingFace for cascade-related datasets.
    
    This is how users FIND each other's lattices.
    
    Returns:
        List of dataset info dicts
    """
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        
        # Search for cascade datasets
        datasets = api.list_datasets(search=query_str, limit=50)
        
        results = []
        for ds in datasets:
            results.append({
                "id": ds.id,
                "author": ds.author,
                "downloads": ds.downloads,
                "likes": ds.likes,
                "last_modified": str(ds.last_modified) if ds.last_modified else None,
                "tags": ds.tags if hasattr(ds, 'tags') else [],
            })
        
        return results
        
    except ImportError:
        return [{"error": "huggingface_hub not installed"}]
    except Exception as e:
        return [{"error": str(e)}]


def discover_live(dataset_id: str = None) -> Dict[str, Any]:
    """
    Get LIVE activity on a dataset - who's observing right now?
    
    Uses HuggingFace's commit history as activity feed.
    
    Returns:
        Recent commits/updates to the dataset
    """
    dataset_id = dataset_id or CENTRAL_DATASET
    
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        
        # Get recent commits
        commits = api.list_repo_commits(
            repo_id=dataset_id,
            repo_type="dataset",
        )
        
        # Take last 20
        recent = []
        for i, commit in enumerate(commits):
            if i >= 20:
                break
            recent.append({
                "commit_id": commit.commit_id,
                "created_at": str(commit.created_at),
                "title": commit.title,
                "authors": [a for a in (commit.authors or [])],
            })
        
        return {
            "dataset": dataset_id,
            "recent_commits": recent,
            "total_commits": len(list(commits)) if hasattr(commits, '__len__') else "unknown",
        }
        
    except ImportError:
        return {"error": "huggingface_hub not installed"}
    except Exception as e:
        return {"error": str(e)}


def dataset_info(dataset_id: str = None) -> Dict[str, Any]:
    """
    Get full metadata for a dataset from HuggingFace.
    
    Returns:
        Dataset metadata including size, downloads, etc.
    """
    dataset_id = dataset_id or CENTRAL_DATASET
    
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        
        info = api.dataset_info(dataset_id)
        
        return {
            "id": info.id,
            "author": info.author,
            "downloads": info.downloads,
            "likes": info.likes,
            "created_at": str(info.created_at) if info.created_at else None,
            "last_modified": str(info.last_modified) if info.last_modified else None,
            "private": info.private,
            "tags": info.tags,
            "card_data": info.card_data if hasattr(info, 'card_data') else None,
        }
        
    except ImportError:
        return {"error": "huggingface_hub not installed"}
    except Exception as e:
        return {"error": str(e)}


def stats() -> Dict[str, Any]:
    """Get store statistics."""
    store = _get_store()
    
    conn = sqlite3.connect(store.db_path)
    
    total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    pinned = conn.execute("SELECT COUNT(*) FROM observations WHERE pinned = 1").fetchone()[0]
    
    models = conn.execute(
        "SELECT model_id, COUNT(*) FROM observations GROUP BY model_id"
    ).fetchall()
    
    conn.close()
    
    return {
        "total_observations": total,
        "pinned_observations": pinned,
        "models": {m: c for m, c in models},
        "genesis_root": get_genesis_root(),
        "lattice_dir": str(_get_store().lattice_dir),
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CASCADE Store")
    parser.add_argument("command", choices=["stats", "query", "get", "push", "pull", "sync"])
    parser.add_argument("--model", help="Model ID filter")
    parser.add_argument("--cid", help="CID to fetch")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dataset", help="HF dataset (default: jtwspace/cascade-observations)")
    
    args = parser.parse_args()
    
    if args.command == "stats":
        s = stats()
        print(f"Total: {s['total_observations']}")
        print(f"Synced: {s['pinned_observations']}")
        print(f"Genesis: {s['genesis_root']}")
        print(f"Central dataset: {CENTRAL_DATASET}")
        if USER_DATASET:
            print(f"User dataset: {USER_DATASET}")
        print(f"Models:")
        for model, count in s["models"].items():
            print(f"  {model}: {count}")
    
    elif args.command == "query":
        receipts = query(model_id=args.model, limit=args.limit)
        for r in receipts:
            print(f"{r.cid[:20]}... | {r.model_id} | {r.data}")
    
    elif args.command == "get":
        if not args.cid:
            print("--cid required")
        else:
            r = get(args.cid)
            if r:
                print(json.dumps(r.to_dict(), indent=2, default=str))
            else:
                print("Not found")
    
    elif args.command == "push":
        print(f"Pushing to HuggingFace: {CENTRAL_DATASET}")
        result = sync_all()
        print(f"Synced {result['synced']}, Failed {result['failed']}")
    
    elif args.command == "pull":
        dataset = args.dataset or CENTRAL_DATASET
        print(f"Pulling from: {dataset}")
        count = pull_from_hf(dataset)
        print(f"Pulled {count} observations")
    
    elif args.command == "sync":
        # Bidirectional sync
        print(f"Syncing with HuggingFace...")
        pulled = pull_from_hf()
        result = sync_all()
        print(f"Pulled {pulled}, Pushed {result['synced']}")
