"""
cascade_lattice - Alias module for cascade

This module exists so that `import cascade_lattice` works as expected
when you `pip install cascade-lattice`.

The actual implementation lives in the `cascade` package.
Both import styles work:
    >>> import cascade
    >>> import cascade_lattice  # Same thing!
    >>> from cascade_lattice.core.provenance import ProvenanceChain  # Works!
"""

import sys
import importlib

# Re-export everything from cascade
from cascade import *
from cascade import (
    __version__,
    __author__,
    __license__,
    # Core
    Event,
    CausationLink,
    CausationGraph,
    SymbioticAdapter,
    Tracer,
    MetricsEngine,
    Monitor,
    # Provenance
    Receipt,
    # HOLD protocol
    Hold,
    HoldPoint,
    HoldState,
    HoldResolution,
    HoldAwareMixin,
    CausationHold,
    InferenceStep,
    # SDK
    observe,
    auto_observe,
    sdk_observe,
    # Store
    store_observe,
    store_get,
    store_query,
    store_stats,
    # Analysis
    PlaybackBuffer,
    ArcadeFeedback,
    # Genesis
    genesis,
    # Sync
    sync_all,
    pull_from_hf,
    discover_datasets,
    discover_models,
    discover_live,
    dataset_info,
    # Viz
    viz,
    find_latest_tape,
    list_tape_files,
    load_tape_file,
    # Core functions
    init,
    shutdown,
)

# Make cascade_lattice.store, cascade_lattice.hold, etc. work
from cascade import store
from cascade import hold_module as hold
from cascade import core
from cascade import analysis
from cascade import diagnostics
from cascade import forensics
from cascade import observation
from cascade import identity
from cascade import sdk


def __getattr__(name):
    """
    Lazy import handler - redirects cascade_lattice.X to cascade.X
    
    This allows `from cascade_lattice.core.provenance import ProvenanceChain`
    to work by dynamically importing from cascade.
    """
    try:
        # Try to import from cascade
        cascade_module = importlib.import_module(f"cascade.{name}")
        # Cache it in sys.modules so future imports are fast
        sys.modules[f"cascade_lattice.{name}"] = cascade_module
        return cascade_module
    except ImportError:
        raise AttributeError(f"module 'cascade_lattice' has no attribute '{name}'")
