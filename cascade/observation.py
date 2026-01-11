"""
CASCADE Observation Manager

Connects the detective tabs (Observatory, Unity, System) to the lattice.

Flow:
1. User runs observation through any tab
2. Observation creates provenance chain
3. Chain links to model identity (for model obs) or genesis (for data/system)
4. Chain saved to lattice
5. Optionally pinned to IPFS

This is the integration layer between UI and lattice.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from cascade.core.provenance import ProvenanceChain
from cascade.identity import ModelRegistry, ModelIdentity, create_model_identity
from cascade.genesis import get_genesis_root, link_to_genesis


@dataclass
class Observation:
    """
    A single observation record in the lattice.
    
    Can be:
    - Model observation (inference through Observatory)
    - Data observation (entity resolution through Unity)
    - System observation (log analysis through System tab)
    """
    observation_id: str
    observation_type: str  # "model", "data", "system"
    
    # What was observed
    source_id: str  # Model ID, dataset ID, or log source
    source_root: str  # Merkle root of source identity
    
    # The observation data
    chain: ProvenanceChain
    merkle_root: str
    
    # Metadata
    user_hash: Optional[str] = None  # Anonymous user identifier
    created_at: float = field(default_factory=time.time)
    
    # IPFS
    cid: Optional[str] = None


class ObservationManager:
    """
    Manages observations across all CASCADE tabs.
    
    Responsibilities:
    - Link observations to model identities or genesis
    - Save observations to lattice
    - Track observation history
    - Provide stats for lattice gateway
    """
    
    def __init__(self, lattice_dir: Path = None):
        self.lattice_dir = lattice_dir or Path(__file__).parent.parent / "lattice"
        self.observations_dir = self.lattice_dir / "observations"
        self.observations_dir.mkdir(parents=True, exist_ok=True)
        
        # Model registry for linking model observations
        self.model_registry = ModelRegistry(self.lattice_dir)
        
        # Genesis root
        self.genesis_root = get_genesis_root()
        
        # In-memory observation index
        self._observations: Dict[str, Observation] = {}
        self._load_index()
    
    def _load_index(self):
        """Load observation index from disk."""
        index_file = self.lattice_dir / "observation_index.json"
        if index_file.exists():
            try:
                index = json.loads(index_file.read_text())
                # Just load metadata, not full chains
                for obs_id, meta in index.items():
                    self._observations[obs_id] = meta
            except:
                pass
    
    def _save_index(self):
        """Save observation index to disk."""
        index_file = self.lattice_dir / "observation_index.json"
        # Save lightweight index
        index = {}
        for obs_id, obs in self._observations.items():
            if isinstance(obs, Observation):
                index[obs_id] = {
                    "observation_id": obs.observation_id,
                    "observation_type": obs.observation_type,
                    "source_id": obs.source_id,
                    "source_root": obs.source_root,
                    "merkle_root": obs.merkle_root,
                    "created_at": obs.created_at,
                    "cid": obs.cid,
                }
            else:
                index[obs_id] = obs
        index_file.write_text(json.dumps(index, indent=2))
    
    def observe_model(
        self,
        model_id: str,
        chain: ProvenanceChain,
        user_hash: Optional[str] = None,
        **model_kwargs,
    ) -> Observation:
        """
        Record a model observation.
        
        Args:
            model_id: HuggingFace model ID or local path
            chain: Provenance chain from Observatory
            user_hash: Anonymous user identifier
            **model_kwargs: Additional model info (parameters, etc.)
        
        Returns:
            Observation linked to model identity
        """
        # Get or create model identity
        identity = self.model_registry.get_or_create(model_id, **model_kwargs)
        
        # Link chain to model identity
        if not chain.external_roots:
            chain.external_roots = []
        if identity.merkle_root not in chain.external_roots:
            chain.external_roots.append(identity.merkle_root)
        
        # Finalize chain if not already
        if not chain.finalized:
            chain.finalize()
        
        # Create observation record
        obs_id = f"model_{chain.merkle_root}"
        observation = Observation(
            observation_id=obs_id,
            observation_type="model",
            source_id=model_id,
            source_root=identity.merkle_root,
            chain=chain,
            merkle_root=chain.merkle_root,
            user_hash=user_hash,
        )
        
        # Save chain to disk
        self._save_observation(observation)
        
        return observation
    
    def observe_data(
        self,
        dataset_a: str,
        dataset_b: str,
        chain: ProvenanceChain,
        user_hash: Optional[str] = None,
    ) -> Observation:
        """
        Record a data unity observation.
        
        Links directly to genesis (data doesn't have model identity).
        """
        # Link to genesis
        if not chain.external_roots:
            chain.external_roots = []
        if self.genesis_root not in chain.external_roots:
            chain.external_roots.append(self.genesis_root)
        
        if not chain.finalized:
            chain.finalize()
        
        # Create observation
        source_id = f"{dataset_a}::{dataset_b}"
        obs_id = f"data_{chain.merkle_root}"
        
        observation = Observation(
            observation_id=obs_id,
            observation_type="data",
            source_id=source_id,
            source_root=self.genesis_root,
            chain=chain,
            merkle_root=chain.merkle_root,
            user_hash=user_hash,
        )
        
        self._save_observation(observation)
        return observation
    
    def observe_system(
        self,
        source_name: str,
        chain: ProvenanceChain,
        user_hash: Optional[str] = None,
    ) -> Observation:
        """
        Record a system log observation.
        
        Links directly to genesis.
        """
        # Link to genesis
        if not chain.external_roots:
            chain.external_roots = []
        if self.genesis_root not in chain.external_roots:
            chain.external_roots.append(self.genesis_root)
        
        if not chain.finalized:
            chain.finalize()
        
        obs_id = f"system_{chain.merkle_root}"
        
        observation = Observation(
            observation_id=obs_id,
            observation_type="system",
            source_id=source_name,
            source_root=self.genesis_root,
            chain=chain,
            merkle_root=chain.merkle_root,
            user_hash=user_hash,
        )
        
        self._save_observation(observation)
        return observation
    
    def _save_observation(self, observation: Observation):
        """Save observation to disk."""
        # Save to index
        self._observations[observation.observation_id] = observation
        self._save_index()
        
        # Save full chain
        chain_file = self.observations_dir / f"{observation.merkle_root}.json"
        chain_data = {
            "observation_id": observation.observation_id,
            "observation_type": observation.observation_type,
            "source_id": observation.source_id,
            "source_root": observation.source_root,
            "user_hash": observation.user_hash,
            "created_at": observation.created_at,
            "cid": observation.cid,
            "chain": observation.chain.to_dict() if hasattr(observation.chain, 'to_dict') else str(observation.chain),
        }
        chain_file.write_text(json.dumps(chain_data, indent=2, default=str))
    
    def pin_observation(self, observation: Observation) -> Optional[str]:
        """
        Pin observation to IPFS.
        
        Returns CID if successful.
        """
        try:
            from cascade.ipld import chain_to_cid, encode_to_dag_cbor
            from cascade.web3_pin import pin_file
            
            # Convert to IPLD format
            chain_data = observation.chain.to_dict() if hasattr(observation.chain, 'to_dict') else {}
            cbor_data = encode_to_dag_cbor(chain_data)
            
            # Save CBOR
            cbor_file = self.observations_dir / f"{observation.merkle_root}.cbor"
            cbor_file.write_bytes(cbor_data)
            
            # Compute CID
            cid = chain_to_cid(chain_data)
            observation.cid = cid
            
            # Update index
            self._save_observation(observation)
            
            return cid
        except Exception as e:
            print(f"Failed to pin observation: {e}")
            return None
    
    def get_observation(self, merkle_root: str) -> Optional[Observation]:
        """Get observation by merkle root."""
        for obs in self._observations.values():
            if isinstance(obs, Observation) and obs.merkle_root == merkle_root:
                return obs
            elif isinstance(obs, dict) and obs.get("merkle_root") == merkle_root:
                return obs
        return None
    
    def list_observations(
        self,
        observation_type: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List observations with optional filters."""
        results = []
        
        for obs in self._observations.values():
            if isinstance(obs, Observation):
                obs_dict = {
                    "observation_id": obs.observation_id,
                    "observation_type": obs.observation_type,
                    "source_id": obs.source_id,
                    "merkle_root": obs.merkle_root,
                    "created_at": obs.created_at,
                    "cid": obs.cid,
                }
            else:
                obs_dict = obs
            
            # Apply filters
            if observation_type and obs_dict.get("observation_type") != observation_type:
                continue
            if source_id and source_id not in obs_dict.get("source_id", ""):
                continue
            
            results.append(obs_dict)
        
        # Sort by time, newest first
        results.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        return results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get lattice statistics."""
        obs_list = list(self._observations.values())
        
        model_obs = [o for o in obs_list if (isinstance(o, Observation) and o.observation_type == "model") or (isinstance(o, dict) and o.get("observation_type") == "model")]
        data_obs = [o for o in obs_list if (isinstance(o, Observation) and o.observation_type == "data") or (isinstance(o, dict) and o.get("observation_type") == "data")]
        system_obs = [o for o in obs_list if (isinstance(o, Observation) and o.observation_type == "system") or (isinstance(o, dict) and o.get("observation_type") == "system")]
        
        # Count unique models
        model_ids = set()
        for o in model_obs:
            if isinstance(o, Observation):
                model_ids.add(o.source_id)
            elif isinstance(o, dict):
                model_ids.add(o.get("source_id", ""))
        
        return {
            "total_observations": len(obs_list),
            "model_observations": len(model_obs),
            "data_observations": len(data_obs),
            "system_observations": len(system_obs),
            "unique_models": len(model_ids),
            "registered_models": len(self.model_registry.list_all()),
            "genesis_root": self.genesis_root,
        }
    
    def get_model_observations(self, model_id: str) -> List[Dict[str, Any]]:
        """Get all observations for a specific model."""
        return self.list_observations(observation_type="model", source_id=model_id)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_manager: Optional[ObservationManager] = None

def get_observation_manager() -> ObservationManager:
    """Get singleton observation manager."""
    global _manager
    if _manager is None:
        _manager = ObservationManager()
    return _manager


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    print("=== CASCADE Observation Manager ===\n")
    
    manager = get_observation_manager()
    
    # Show stats
    stats = manager.get_stats()
    print(f"Genesis: {stats['genesis_root']}")
    print(f"Registered Models: {stats['registered_models']}")
    print(f"Total Observations: {stats['total_observations']}")
    print(f"  - Model: {stats['model_observations']}")
    print(f"  - Data: {stats['data_observations']}")
    print(f"  - System: {stats['system_observations']}")
    print(f"Unique Models Observed: {stats['unique_models']}")
    
    # List recent observations
    print("\nRecent Observations:")
    for obs in manager.list_observations(limit=5):
        print(f"  [{obs['observation_type']}] {obs['source_id'][:40]}... → {obs['merkle_root']}")
