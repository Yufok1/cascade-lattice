"""
CASCADE SDK - Universal AI Observation Layer

Usage:
    import cascade
    cascade.init()
    
    # Now every call emits a receipt automatically
    import openai
    response = openai.chat.completions.create(...)  # Receipt emitted
"""

import threading
import queue
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# Import our observation infrastructure
from .observation import ObservationManager
from .identity import ModelRegistry
from .genesis import ProvenanceChain


class CascadeSDK:
    """Main SDK singleton - manages patching and emission."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if CascadeSDK._initialized:
            return
            
        self.observation_manager = ObservationManager()
        self.model_registry = ModelRegistry()
        self.emission_queue = queue.Queue()
        self.background_thread = None
        self.running = False
        self.patched_providers = set()
        self.config = {
            "emit_async": True,
            "lattice_path": "lattice/observations",
            "verbose": False,
        }
        CascadeSDK._initialized = True
    
    def init(self, **kwargs):
        """
        Initialize CASCADE and auto-patch available providers.
        
        Args:
            emit_async: Whether to emit receipts in background (default: True)
            verbose: Print when receipts are emitted (default: False)
            providers: List of providers to patch, or 'all' (default: 'all')
        """
        self.config.update(kwargs)
        
        # Start background emission thread
        if self.config["emit_async"] and not self.running:
            self.running = True
            self.background_thread = threading.Thread(
                target=self._emission_worker,
                daemon=True
            )
            self.background_thread.start()
        
        # Auto-patch available providers
        providers = kwargs.get("providers", "all")
        self._patch_providers(providers)
        
        if self.config["verbose"]:
            print(f"[CASCADE] Initialized. Patched: {self.patched_providers}")
        
        return self
    
    def _patch_providers(self, providers):
        """Patch LLM provider libraries."""
        from .patches import (
            patch_openai,
            patch_anthropic,
            patch_huggingface,
            patch_ollama,
            patch_litellm,
        )
        
        patch_map = {
            "openai": patch_openai,
            "anthropic": patch_anthropic,
            "huggingface": patch_huggingface,
            "ollama": patch_ollama,
            "litellm": patch_litellm,
        }
        
        if providers == "all":
            providers = list(patch_map.keys())
        
        for provider in providers:
            if provider in patch_map:
                try:
                    patch_map[provider](self)
                    self.patched_providers.add(provider)
                except ImportError:
                    # Provider not installed, skip
                    pass
                except Exception as e:
                    if self.config["verbose"]:
                        print(f"[CASCADE] Failed to patch {provider}: {e}")
    
    def _emission_worker(self):
        """Background thread that processes emission queue."""
        while self.running:
            try:
                receipt_data = self.emission_queue.get(timeout=1.0)
                self._emit_receipt(receipt_data)
            except queue.Empty:
                continue
            except Exception as e:
                if self.config["verbose"]:
                    print(f"[CASCADE] Emission error: {e}")
    
    def _emit_receipt(self, receipt_data: Dict[str, Any]):
        """Actually write the receipt to lattice."""
        import hashlib
        import uuid
        
        try:
            # Create provenance chain for this observation
            model_id = receipt_data["model_id"]
            input_text = receipt_data["input"][:1000]  # Truncate
            output_text = receipt_data["output"][:2000]  # Truncate
            
            # Compute hashes
            input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]
            model_hash = hashlib.sha256(model_id.encode()).hexdigest()[:16]
            session_id = str(uuid.uuid4())[:8]
            
            chain = ProvenanceChain(
                session_id=session_id,
                model_id=model_id,
                model_hash=model_hash,
                input_hash=input_hash,
            )
            
            # Add inference record
            from cascade.core.provenance import ProvenanceRecord
            import time
            
            record = ProvenanceRecord(
                layer_name="inference",
                layer_idx=0,
                state_hash=hashlib.sha256(output_text.encode()).hexdigest()[:16],
                parent_hashes=[input_hash],
                params_hash=model_hash,
                shape=[len(output_text)],
                dtype="text",
                stats={
                    **receipt_data.get("metrics", {}),
                    "provider": receipt_data.get("context", {}).get("provider", "unknown"),
                    "timestamp": receipt_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                },
                execution_order=0,
            )
            chain.add_record(record)
            chain.finalize()
            
            observation = self.observation_manager.observe_model(
                model_id=model_id,
                chain=chain,
                user_hash=receipt_data.get("user_hash"),
            )
            
            if self.config["verbose"]:
                print(f"[CASCADE] Receipt: {observation.merkle_root[:16]}... -> {model_id}")
            
            return observation
        except Exception as e:
            if self.config["verbose"]:
                import traceback
                print(f"[CASCADE] Failed to emit: {e}")
                traceback.print_exc()
            return None
    
    def observe(
        self,
        model_id: str,
        input_data: Any,
        output_data: Any,
        metrics: Optional[Dict] = None,
        context: Optional[Dict] = None
    ):
        """
        Manually emit an observation receipt.
        
        Called automatically by patches, but can be called directly.
        """
        receipt_data = {
            "model_id": model_id,
            "input": str(input_data),
            "output": str(output_data),
            "metrics": metrics or {},
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if self.config["emit_async"]:
            self.emission_queue.put(receipt_data)
        else:
            self._emit_receipt(receipt_data)
    
    def shutdown(self):
        """Stop background emission and flush queue."""
        self.running = False
        if self.background_thread:
            self.background_thread.join(timeout=5.0)
        
        # Flush remaining items
        while not self.emission_queue.empty():
            try:
                receipt_data = self.emission_queue.get_nowait()
                self._emit_receipt(receipt_data)
            except queue.Empty:
                break


# Global SDK instance
_sdk = CascadeSDK()


def init(**kwargs):
    """Initialize CASCADE observation layer."""
    return _sdk.init(**kwargs)


def observe(model_id: str, input_data: Any, output_data: Any, **kwargs):
    """Manually emit an observation."""
    return _sdk.observe(model_id, input_data, output_data, **kwargs)


def shutdown():
    """Shutdown CASCADE (flush pending receipts)."""
    return _sdk.shutdown()


# Convenience: allow `import cascade; cascade.init()`
__all__ = ["init", "observe", "shutdown", "CascadeSDK"]
