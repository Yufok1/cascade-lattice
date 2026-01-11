"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║    ██╗  ██╗ ██████╗ ██╗     ██████╗                                          ║
║    ██║  ██║██╔═══██╗██║     ██╔══██╗                                         ║
║    ███████║██║   ██║██║     ██║  ██║                                         ║
║    ██╔══██║██║   ██║██║     ██║  ██║                                         ║
║    ██║  ██║╚██████╔╝███████╗██████╔╝                                         ║
║    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═════╝                                          ║
║                                                                               ║
║    Inference-Level Halt Protocol for CASCADE-LATTICE                         ║
║                                                                               ║
║    "Pause the machine. See what it sees. Choose what it chooses."            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

HOLD is MODEL-AGNOSTIC. Works with ANY framework:
    - PyTorch, JAX, TensorFlow, scikit-learn
    - Hugging Face, OpenAI API, Anthropic API
    - Stable Baselines3, RLlib, custom RL
    - Any function that outputs probabilities

USAGE:
    >>> from cascade.hold import Hold
    >>> 
    >>> # Your model (any framework)
    >>> probs = your_model.predict(obs)
    >>> 
    >>> # HOLD at decision point
    >>> hold = Hold.get()
    >>> resolution = hold.yield_point(
    ...     action_probs=probs,
    ...     value=value_estimate,
    ...     observation=obs,
    ...     brain_id="my_model",
    ...     # Optional informational wealth:
    ...     action_labels=["up", "down", "left", "right"],
    ...     latent=model.get_latent(),
    ...     attention=model.get_attention(),
    ...     features=model.get_features(),
    ...     imagination=model.imagine_futures(),
    ... )
    >>> 
    >>> # Use resolved action
    >>> action = resolution.action
    >>> was_override = resolution.was_override

CLI:
    $ cascade hold           # Start HOLD interface
    $ cascade hold-status    # Show HOLD system status
"""

# Primitives - the core API
from cascade.hold.primitives import (
    HoldState,
    HoldPoint,
    HoldResolution,
    Hold,
    HoldAwareMixin,
)

# Session Layer - arcade-style history and time travel
from cascade.hold.session import (
    InferenceStep,
    HoldSession,
    ArcadeFeedback,
    CausationHold,
)

__all__ = [
    # Primitives
    "HoldState",
    "HoldPoint",
    "HoldResolution",
    "Hold",
    "HoldAwareMixin",
    # Session
    "InferenceStep",
    "HoldSession",
    "ArcadeFeedback",
    "CausationHold",
]
