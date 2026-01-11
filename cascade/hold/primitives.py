"""
HOLD Primitives - Core Data Structures and Singleton
═══════════════════════════════════════════════════════════

The primitive layer of HOLD:
- HoldPoint: A frozen moment in inference
- HoldResolution: The outcome of a hold
- Hold: Singleton system managing inference-level halts

HOLD is a CASCADE-LATTICE primitive.
No cascade = No HOLD.
"""

import time
import hashlib
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

# CASCADE-LATTICE is REQUIRED
try:
    from cascade import sdk_observe
    from cascade.core.event import CausationLink
    from cascade.core.graph import CausationGraph
    HAS_CASCADE = True
except ImportError:
    HAS_CASCADE = False
    # Stubs for when imported standalone (testing)
    def sdk_observe(*args, **kwargs): pass
    class CausationLink:
        def __init__(self, **kwargs): pass
    class CausationGraph:
        def add_link(self, link): pass


class HoldState(Enum):
    """State of a hold point."""
    PENDING = "pending"      # Waiting for resolution
    ACCEPTED = "accepted"    # AI choice was accepted
    OVERRIDDEN = "overridden"  # Human override
    TIMEOUT = "timeout"      # Timed out, fell back to AI
    CANCELLED = "cancelled"  # Hold was cancelled


def _sanitize(data: Any) -> Any:
    """Recursively convert numpy types to python types."""
    if isinstance(data, dict):
        return {k: _sanitize(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_sanitize(x) for x in data]
    elif isinstance(data, np.generic):
        return data.item()
    return data


@dataclass
class HoldPoint:
    """
    A decision point where inference yields for potential human intervention.
    
    This is the "freeze frame" - the moment before commitment.
    The decision matrix is exposed, the merkle chain awaits.
    
    INFORMATIONAL WEALTH - everything a human needs to understand the decision:
    - action_labels: What each action means ("FORWARD", "ATTACK", etc.)
    - latent: The model's internal representation (for inspection)
    - attention: What the model is attending to
    - features: Extracted feature activations
    - imagination: Per-action trajectory predictions and expected values
    - logits: Raw logits before softmax (for temperature analysis)
    - reasoning: Text explanations if available
    """
    # Decision matrix
    action_probs: np.ndarray       # The probability distribution
    value: float                   # Predicted value
    
    # Context
    observation: Dict[str, Any]    # What the brain saw
    brain_id: str                  # Which brain is holding
    
    # === INFORMATIONAL WEALTH ===
    
    # Action labels - CRITICAL for human understanding
    action_labels: Optional[List[str]] = None  # ["NOOP", "FORWARD", "BACK", ...]
    
    # Internal state
    latent: Optional[np.ndarray] = None        # Latent activations (any shape)
    attention: Optional[Dict[str, float]] = None  # {"position": 0.7, "health": 0.3, ...}
    features: Optional[Dict[str, float]] = None   # {"spatial_attn": 0.8, "danger": 0.2, ...}
    
    # Per-action deep data
    imagination: Optional[Dict[int, Dict]] = None  # {0: {"trajectory": [...], "expected_value": 0.5}, ...}
    
    # Logits (pre-softmax)
    logits: Optional[np.ndarray] = None        # Raw logits for each action
    
    # Reasoning chain (if model provides explanations)
    reasoning: Optional[List[str]] = None      # ["High reward expected", "Low risk path", ...]
    
    # World model predictions (if available)
    world_prediction: Optional[Dict[str, Any]] = None  # {"pos_delta": [1,0,0], "health_delta": -2, ...}
    
    # === END WEALTH ===
    
    # Identity
    id: str = field(default_factory=lambda: hashlib.sha256(str(time.time()).encode()).hexdigest()[:16])
    timestamp: float = field(default_factory=time.time)
    
    # Merkle linkage
    parent_merkle: Optional[str] = None  # Previous hold point
    merkle_root: Optional[str] = None    # Computed on creation
    
    # State
    state: HoldState = HoldState.PENDING
    
    def __post_init__(self):
        """Compute merkle root on creation."""
        if self.merkle_root is None:
            data = f"{self.id}:{self.brain_id}:{self.action_probs.tobytes().hex()}:{self.timestamp}"
            if self.parent_merkle:
                data = f"{self.parent_merkle}:{data}"
            self.merkle_root = hashlib.sha256(data.encode()).hexdigest()[:16]
    
    @property
    def ai_choice(self) -> int:
        """What the AI would choose."""
        return int(np.argmax(self.action_probs))
    
    @property
    def ai_confidence(self) -> float:
        """Confidence in AI's top choice."""
        return float(np.max(self.action_probs))
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for CASCADE observation - includes full informational wealth."""
        d = {
            'id': self.id,
            'brain_id': self.brain_id,
            'action_probs': self.action_probs.tolist(),
            'ai_choice': self.ai_choice,
            'ai_confidence': self.ai_confidence,
            'value': self.value,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'parent_merkle': self.parent_merkle,
            'state': self.state.value,
            'observation': self.observation,
        }
        
        # Include all available wealth
        if self.action_labels is not None:
            d['action_labels'] = self.action_labels
        if self.latent is not None:
            d['latent'] = self.latent.tolist() if hasattr(self.latent, 'tolist') else self.latent
        if self.attention is not None:
            d['attention'] = self.attention
        if self.features is not None:
            d['features'] = self.features
        if self.imagination is not None:
            d['imagination'] = self.imagination
        if self.logits is not None:
            d['logits'] = self.logits.tolist() if hasattr(self.logits, 'tolist') else self.logits
        if self.reasoning is not None:
            d['reasoning'] = self.reasoning
        if self.world_prediction is not None:
            d['world_prediction'] = self.world_prediction
            
        return _sanitize(d)


@dataclass
class HoldResolution:
    """
    The resolution of a hold point.
    
    Either the human accepted, overrode, or it timed out.
    Links back to the hold point, forming a provenance chain.
    """
    hold_point: HoldPoint          # The hold that was resolved
    action: int                    # Final action taken
    
    # Resolution details
    was_override: bool             # True if human overrode AI
    override_source: Optional[str] = None  # Who/what overrode ("human", "policy", etc.)
    
    # Timing
    hold_duration: float = 0.0     # How long was held
    timestamp: float = field(default_factory=time.time)
    
    # Merkle linkage
    merkle_root: Optional[str] = None
    
    def __post_init__(self):
        """Compute merkle root."""
        if self.merkle_root is None:
            data = f"{self.hold_point.merkle_root}:{self.action}:{self.was_override}:{self.timestamp}"
            self.merkle_root = hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for CASCADE observation."""
        d = {
            'hold_id': self.hold_point.id,
            'hold_merkle': self.hold_point.merkle_root,
            'action': self.action,
            'ai_choice': self.hold_point.ai_choice,
            'was_override': self.was_override,
            'override_source': self.override_source,
            'hold_duration': self.hold_duration,
            'merkle_root': self.merkle_root,
            'timestamp': self.timestamp,
        }
        return _sanitize(d)


class Hold:
    """
    The HOLD system - manages inference-level halts.
    
    Singleton pattern - one Hold system per process.
    
    Usage:
        hold = Hold.get()
        
        # Register listeners (for UI, visualization, etc.)
        hold.register_listener(my_callback)
        
        # From within a brain's forward() method:
        resolution = hold.yield_point(
            action_probs=probs,
            value=value,
            observation=obs,
            brain_id="brain_001"
        )
        # Blocks until resolution!
        
        # From UI/control thread:
        hold.accept()  # or
        hold.override(action=3, source="human")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # State
        self._current_hold: Optional[HoldPoint] = None
        self._resolution_event = threading.Event()
        self._resolution: Optional[HoldResolution] = None
        
        # Chain
        self._last_merkle: Optional[str] = None
        self._hold_count = 0
        self._override_count = 0
        
        # Callbacks - interfaces register here to receive hold points
        self._listeners: List[Callable[[HoldPoint], None]] = []
        
        # Settings
        self.timeout: float = 30.0  # Default timeout (seconds)
        self.auto_accept: bool = False  # If True, don't block, just observe
        
        # CASCADE graph for this session
        self._causation_graph = CausationGraph()
        
        self._initialized = True
        print("[HOLD] system initialized (cascade-lattice)")
    
    @classmethod
    def get(cls) -> 'Hold':
        """Get the singleton instance."""
        return cls()
    
    def register_listener(self, callback: Callable[[HoldPoint], None]):
        """
        Register a listener for hold points.
        
        The callback receives HoldPoint when inference halts.
        Use this to connect visualizations, UIs, etc.
        """
        self._listeners.append(callback)
        print(f"[REGISTER] Registered HOLD listener: {callback.__name__ if hasattr(callback, '__name__') else callback}")
    
    def unregister_listener(self, callback: Callable):
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def yield_point(
        self,
        action_probs: np.ndarray,
        value: float,
        observation: Dict[str, Any],
        brain_id: str,
        # === INFORMATIONAL WEALTH ===
        action_labels: Optional[List[str]] = None,
        latent: Optional[np.ndarray] = None,
        attention: Optional[Dict[str, float]] = None,
        features: Optional[Dict[str, float]] = None,
        imagination: Optional[Dict[int, Dict]] = None,
        logits: Optional[np.ndarray] = None,
        reasoning: Optional[List[str]] = None,
        world_prediction: Optional[Dict[str, Any]] = None,
        # === END WEALTH ===
        blocking: bool = True,
    ) -> HoldResolution:
        """
        Create a hold point and yield for resolution.
        
        This is called from within a brain's forward() method.
        Blocks until resolved (or timeout).
        
        Args:
            action_probs: The decision matrix (probability distribution)
            value: Predicted value
            observation: What the brain observed
            brain_id: Identifier for the brain
            
            INFORMATIONAL WEALTH (all optional, but improves human understanding):
            action_labels: Names for each action ["FORWARD", "BACK", "LEFT", ...]
            latent: Model's latent state/activations
            attention: Attention weights {"position": 0.7, "health": 0.3}
            features: Feature activations {"spatial": 0.8, "danger": 0.2}
            imagination: Per-action predictions {0: {"trajectory": [...], "expected_value": 0.5}}
            logits: Raw pre-softmax logits
            reasoning: Text explanations ["High reward expected", ...]
            world_prediction: World model predictions {"pos_delta": [1,0,0]}
            
            blocking: If False, returns immediately with AI choice
            
        Returns:
            HoldResolution with the final action
        """
        # Create hold point with full wealth
        hold = HoldPoint(
            action_probs=action_probs,
            value=value,
            observation=observation,
            brain_id=brain_id,
            action_labels=action_labels,
            latent=latent,
            attention=attention,
            features=features,
            imagination=imagination,
            logits=logits,
            reasoning=reasoning,
            world_prediction=world_prediction,
            parent_merkle=self._last_merkle,
        )
        
        # Observe the hold point in CASCADE
        sdk_observe(
            model_id=brain_id,
            input_data=observation,
            output_data={**hold.to_dict(), 'event_type': 'hold_point'},
        )
        
        self._hold_count += 1
        
        # Non-blocking mode - just observe and return AI choice
        if not blocking or self.auto_accept:
            resolution = HoldResolution(
                hold_point=hold,
                action=hold.ai_choice,
                was_override=False,
                hold_duration=0.0,
            )
            self._observe_resolution(resolution)
            return resolution
        
        # Set as current hold
        self._current_hold = hold
        self._resolution_event.clear()
        self._resolution = None
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(hold)
            except Exception as e:
                print(f"⚠️ HOLD listener error: {e}")
        
        # Print hold info
        print(f"\n{'═' * 50}")
        print(f"🛑 HOLD #{self._hold_count}")
        print(f"   Merkle: {hold.merkle_root}")
        ai_label = hold.action_labels[hold.ai_choice] if hold.action_labels else str(hold.ai_choice)
        print(f"   AI Choice: {ai_label} (confidence: {hold.ai_confidence:.2%})")
        print(f"   Value: {hold.value:.4f}")
        
        # Show probabilities with labels
        if hold.action_labels:
            prob_str = ', '.join(f'{hold.action_labels[i]}:{p:.2f}' for i, p in enumerate(hold.action_probs))
        else:
            prob_str = ', '.join(f'{i}:{p:.2f}' for i, p in enumerate(hold.action_probs))
        print(f"   Probabilities: {prob_str}")
        
        # Show available wealth
        wealth = []
        if hold.latent is not None: wealth.append("latent")
        if hold.attention is not None: wealth.append("attention")
        if hold.features is not None: wealth.append("features")
        if hold.imagination is not None: wealth.append("imagination")
        if hold.reasoning is not None: wealth.append("reasoning")
        if wealth:
            print(f"   Wealth: {', '.join(wealth)}")
        
        print(f"   Waiting for resolution (timeout: {self.timeout}s)...")
        print(f"{'═' * 50}")
        
        # Block until resolution or timeout
        start_time = time.time()
        resolved = self._resolution_event.wait(timeout=self.timeout)
        hold_duration = time.time() - start_time
        
        if resolved and self._resolution:
            resolution = self._resolution
            resolution.hold_duration = hold_duration
        else:
            # Timeout - use AI choice
            hold.state = HoldState.TIMEOUT
            resolution = HoldResolution(
                hold_point=hold,
                action=hold.ai_choice,
                was_override=False,
                override_source="timeout",
                hold_duration=hold_duration,
            )
            print(f"[TIMEOUT] HOLD timeout - accepting AI choice: {hold.ai_choice}")
        
        # Observe resolution
        self._observe_resolution(resolution)
        
        # Clear state
        self._current_hold = None
        self._resolution = None
        
        return resolution
    
    def resolve(self, action: int, source: str = "human"):
        """
        Resolve the current hold with an action.
        
        Called by UI/interface when human makes a choice.
        
        Args:
            action: The chosen action
            source: Who resolved it ("human", "policy", etc.)
        """
        if self._current_hold is None:
            print("[WARN] No active hold to resolve")
            return
        
        hold = self._current_hold
        was_override = (action != hold.ai_choice)
        
        if was_override:
            hold.state = HoldState.OVERRIDDEN
            self._override_count += 1
        else:
            hold.state = HoldState.ACCEPTED
        
        self._resolution = HoldResolution(
            hold_point=hold,
            action=action,
            was_override=was_override,
            override_source=source if was_override else None,
        )
        
        print(f"[RESOLVE] HOLD resolved: action={action}, override={was_override}")
        self._resolution_event.set()
    
    def accept(self):
        """Accept AI's choice for current hold."""
        if self._current_hold:
            self.resolve(self._current_hold.ai_choice, source="accept")
    
    def override(self, action: int, source: str = "human"):
        """Override with a different action."""
        self.resolve(action, source)
    
    def cancel(self):
        """Cancel current hold without resolution."""
        if self._current_hold:
            self._current_hold.state = HoldState.CANCELLED
            self._resolution = HoldResolution(
                hold_point=self._current_hold,
                action=self._current_hold.ai_choice,
                was_override=False,
                override_source="cancelled",
            )
            self._resolution_event.set()
    
    def _observe_resolution(self, resolution: HoldResolution):
        """Record resolution to CASCADE."""
        sdk_observe(
            model_id=resolution.hold_point.brain_id,
            input_data=resolution.hold_point.to_dict(),
            output_data={**resolution.to_dict(), 'event_type': 'hold_resolution'},
        )
        
        # Update chain
        self._last_merkle = resolution.merkle_root
        
        # Add to causation graph
        link = CausationLink(
            from_event=resolution.hold_point.merkle_root,
            to_event=resolution.merkle_root,
            causation_type="hold_resolved",
            strength=1.0 if resolution.was_override else 0.5,
            explanation=f"Override: {resolution.was_override}, Action: {resolution.action}",
        )
        self._causation_graph.add_link(link)
    
    @property
    def current_hold(self) -> Optional[HoldPoint]:
        """Get current active hold point (if any)."""
        return self._current_hold
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get hold statistics."""
        return {
            'total_holds': self._hold_count,
            'overrides': self._override_count,
            'override_rate': self._override_count / max(self._hold_count, 1),
            'last_merkle': self._last_merkle,
        }


class HoldAwareMixin:
    """
    Mixin for brains that support HOLD.
    
    Add this to your Brain class to enable inference-level halts.
    
    Usage:
        class MyBrain(HoldAwareMixin, BaseBrain):
            def forward(self, inputs):
                # Your inference code
                return {"action_probs": probs, "value": value}
        
        brain = MyBrain()
        brain.enable_hold()
        
        # Now forward_with_hold() will pause for human input
        output = brain.forward_with_hold(inputs)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hold_system = Hold.get()
        self._hold_enabled = True
        self._brain_id = getattr(self, 'id', hashlib.sha256(str(id(self)).encode()).hexdigest()[:16])
    
    def forward_with_hold(
        self,
        inputs: Dict[str, Any],
        blocking: bool = True,
    ) -> Dict[str, Any]:
        """
        Forward pass with HOLD support.
        
        Call this instead of forward() to enable hold points.
        """
        # Get decision matrix from normal forward
        output = self.forward(inputs)
        
        if not self._hold_enabled:
            return output
        
        action_probs = output.get('action_probs', None)
        if action_probs is None:
            return output
        
        # Get imagination if available (DreamerBrain, etc.)
        imagined = None
        if hasattr(self, 'imagine'):
            try:
                imagined = self.imagine(horizon=15)
            except:
                pass
        
        # Yield to hold system
        resolution = self._hold_system.yield_point(
            action_probs=np.array(action_probs),
            value=float(output.get('value', 0.0)),
            observation=inputs,
            brain_id=self._brain_id,
            imagined_futures=imagined,
            blocking=blocking,
        )
        
        # Update output with resolved action
        output['action'] = resolution.action
        output['hold_resolution'] = resolution.to_dict()
        output['was_override'] = resolution.was_override
        
        return output
    
    def enable_hold(self):
        """Enable HOLD for this brain."""
        self._hold_enabled = True
    
    def disable_hold(self):
        """Disable HOLD (normal inference)."""
        self._hold_enabled = False


# Demo
def _demo_hold():
    """Demonstrate HOLD system."""
    print("=" * 60)
    print("HOLD SYSTEM DEMO")
    print("=" * 60)
    
    # Get hold system
    hold = Hold.get()
    hold.timeout = 10.0
    
    def on_hold(point: HoldPoint):
        print(f"\n🔔 Listener received hold: {point.id}")
    
    hold.register_listener(on_hold)
    
    def brain_loop():
        for step in range(3):
            probs = np.random.dirichlet(np.ones(8))
            resolution = hold.yield_point(
                action_probs=probs,
                value=np.random.random(),
                observation={'step': step},
                brain_id='demo_brain',
            )
            print(f"Brain received: action={resolution.action}, override={resolution.was_override}")
    
    def human_input():
        for i in range(3):
            time.sleep(2)
            if hold.current_hold:
                if i % 2 == 0:
                    hold.accept()
                else:
                    hold.override(7, source="demo_human")
    
    brain_thread = threading.Thread(target=brain_loop)
    human_thread = threading.Thread(target=human_input)
    
    brain_thread.start()
    human_thread.start()
    
    brain_thread.join()
    human_thread.join()
    
    print(f"\n{'=' * 60}")
    print("SESSION STATS")
    print(hold.stats)


if __name__ == "__main__":
    _demo_hold()
