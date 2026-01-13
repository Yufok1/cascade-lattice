"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██████╗ █████╗ ███████╗ ██████╗ █████╗ ██████╗ ███████╗                  ║
║    ██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝                  ║
║    ██║     ███████║███████╗██║     ███████║██║  ██║█████╗                    ║
║    ██║     ██╔══██║╚════██║██║     ██╔══██║██║  ██║██╔══╝                    ║
║    ╚██████╗██║  ██║███████║╚██████╗██║  ██║██████╔╝███████╗                  ║
║     ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝                  ║
║                                                                               ║
║    Symbiotic Causation Monitoring for Neural Networks                        ║
║                                                                               ║
║    "even still, i grow, and yet, I grow still"                               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Cascade is a self-interpreting causation monitor that symbiotically adapts to
any system architecture through Kleene fixed-point convergence.

Feed it ANY signal format. It learns your system's patterns. It traces cause
and effect bidirectionally through time. It predicts cascading failures before
they complete.

Quick Start:
    >>> import cascade
    >>> monitor = cascade.Monitor()
    >>> monitor.observe({"loss": 0.5, "epoch": 10})
    >>> monitor.observe("ERROR: gradient exploded at layer 5")
    >>> 
    >>> # What caused this?
    >>> monitor.trace_backwards("gradient_explosion")
    >>> 
    >>> # What will this cause?
    >>> monitor.trace_forwards("learning_rate_spike")
"""

__version__ = "0.6.0"
__author__ = "Cascade Team"
__license__ = "MIT"

from cascade.core.event import Event, CausationLink
from cascade.core.graph import CausationGraph
from cascade.core.adapter import SymbioticAdapter
from cascade.analysis.tracer import Tracer
from cascade.analysis.metrics import MetricsEngine

# Primary API
class Monitor:
    """
    The main entry point for Cascade monitoring.
    
    A symbiotic observer that acclimate to any system architecture.
    Feed it signals in any format — it adapts and builds a causation graph.
    
    Example:
        >>> monitor = cascade.Monitor()
        >>> 
        >>> # Feed it anything - dicts, strings, tensors, whatever
        >>> monitor.observe({"loss": 0.5, "epoch": 10})
        >>> monitor.observe("2024-01-01 12:00:00 INFO training started")
        >>> monitor.observe(torch.tensor([0.1, 0.2, 0.3]))
        >>> 
        >>> # Trace causation backwards (what caused this?)
        >>> causes = monitor.trace_backwards(event_id)
        >>> 
        >>> # Trace causation forwards (what will this cause?)
        >>> effects = monitor.trace_forwards(event_id)
        >>> 
        >>> # Get the full causation graph
        >>> graph = monitor.graph
    """
    
    def __init__(self, name: str = "default"):
        """
        Initialize a new Cascade monitor.
        
        Args:
            name: Optional name for this monitor instance
        """
        self.name = name
        self.adapter = SymbioticAdapter()
        self.graph = CausationGraph()
        self.tracer = Tracer(self.graph)
        self.metrics = MetricsEngine(self.graph)
        self._event_count = 0
    
    def observe(self, signal) -> Event:
        """
        Observe a signal from the host system.
        
        The signal can be in ANY format:
        - dict: {"loss": 0.5, "epoch": 10}
        - str: "ERROR: gradient exploded"
        - tensor: torch.tensor([...])
        - protobuf, JSON, log line, etc.
        
        Cascade will automatically adapt to your signal format.
        
        Args:
            signal: Any signal from the host system
            
        Returns:
            Event: The interpreted event added to the causation graph
        """
        event = self.adapter.interpret(signal)
        self.graph.add_event(event)
        self.metrics.ingest(event)
        self._event_count += 1
        return event
    
    def trace_backwards(self, event_id: str, max_depth: int = 10):
        """
        Trace causation backwards: what caused this event?
        
        Args:
            event_id: ID of the event to trace from
            max_depth: Maximum depth to trace (default: 10)
            
        Returns:
            List of CausationChain objects showing the causal history
        """
        return self.tracer.trace_backwards(event_id, max_depth)
    
    def trace_forwards(self, event_id: str, max_depth: int = 10):
        """
        Trace causation forwards: what did this event cause?
        
        Args:
            event_id: ID of the event to trace from
            max_depth: Maximum depth to trace (default: 10)
            
        Returns:
            List of CausationChain objects showing the effects
        """
        return self.tracer.trace_forwards(event_id, max_depth)
    
    def find_root_causes(self, event_id: str):
        """
        Find the ultimate root causes of an event.
        
        Goes all the way back to find the origin points.
        
        Args:
            event_id: ID of the event to analyze
            
        Returns:
            List of root cause events with their causal chains
        """
        return self.tracer.find_root_causes(event_id)
    
    def analyze_impact(self, event_id: str, max_depth: int = 20):
        """
        Analyze the downstream impact of an event.
        
        Traces forward to find everything this event set in motion.
        
        Args:
            event_id: ID of the event to analyze
            max_depth: Maximum depth to search
            
        Returns:
            ImpactAnalysis with effects and severity score
        """
        return self.tracer.analyze_impact(event_id, max_depth)
    
    def predict_cascade(self, event_id: str):
        """
        Predict the likely future cascade from this event.
        
        Uses learned patterns to forecast effects before they happen.
        
        Args:
            event_id: ID of the event to predict from
            
        Returns:
            CascadePrediction with risk scores and intervention points
        """
        return self.tracer.predict_cascade(event_id)
    
    def __repr__(self):
        return f"<Cascade Monitor '{self.name}' | {self._event_count} events>"


# Convenience function for quick setup
def observe() -> Monitor:
    """
    Create a new Cascade monitor ready for observation.
    
    This is the simplest way to get started:
    
        >>> import cascade
        >>> monitor = cascade.observe()
        >>> monitor.observe({"loss": 0.5})
    
    Returns:
        Monitor: A new monitor instance
    """
    return Monitor()


# Tape utilities for event storage
from cascade.viz.tape import (
    load_tape_file,
    find_latest_tape,
    list_tape_files,
    PlaybackBuffer,
)

# SDK - Universal AI Observation Layer
from cascade.sdk import init, observe as sdk_observe, shutdown

# Store - Simple observe/query with HuggingFace sync
from cascade.store import (
    observe as store_observe,
    query as store_query,
    get as store_get,
    stats as store_stats,
    sync_all,
    pull_from_hf,
    Receipt,
    # Discovery - find other users' lattices
    discover_models,
    discover_datasets,
    discover_live,
    dataset_info,
)

# Convenience aliases
auto_observe = init  # cascade.auto_observe() is clearer for some users

# HOLD - Inference-Level Halt Protocol
from cascade import hold as hold_module
from cascade.hold import (
    Hold,
    HoldPoint,
    HoldResolution,
    HoldState,
    HoldAwareMixin,
    CausationHold,
    InferenceStep,
    HoldSession,
    ArcadeFeedback,
)

# DIAGNOSTICS - Code Bug Exposure System
from cascade import diagnostics


__all__ = [
    # SDK - Primary Interface
    "init",
    "auto_observe",
    "shutdown",
    # Store - HuggingFace-backed storage
    "store_observe",
    "store_query",
    "store_get",
    "store_stats",
    "sync_all",
    "pull_from_hf",
    "Receipt",
    # Discovery
    "discover_models",
    "discover_datasets",
    "discover_live",
    "dataset_info",
    # Monitor (causation tracking)
    "Monitor",
    "observe",
    "Event",
    "CausationLink", 
    "CausationGraph",
    "SymbioticAdapter",
    "Tracer",
    "MetricsEngine",
    # Tape playback
    "load_tape_file",
    "find_latest_tape",
    "list_tape_files",
    "PlaybackBuffer",
    # HOLD - Inference Halt Protocol
    "Hold",
    "HoldPoint",
    "HoldResolution",
    "HoldState",
    "HoldAwareMixin",
    "CausationHold",
    "InferenceStep",
    "HoldSession",
    "ArcadeFeedback",
    "hold_module",
    # Diagnostics - Code Bug Exposure
    "diagnostics",
    "__version__",
]
