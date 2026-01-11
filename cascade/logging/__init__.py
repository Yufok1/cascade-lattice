"""
CASCADE Logging System
Industry-standard dual-layer logging for mathematical precision and human clarity.

Two modes:
1. Kleene Mode: Mathematical fixed point logs for debugging and verification
2. Interpretive Mode: Human-readable causation stories for operators

Use together for complete system observability.
"""

from .kleene_logger import (
    KleeneLogger, 
    LogLevel, 
    get_kleene_logger,
    log_fixed_point,
    log_iterations
)

from .interpretive_logger import (
    InterpretiveLogger,
    ImpactLevel,
    get_interpretive_logger,
    translate_kleene_to_interpretive
)

from .log_manager import (
    LogMode,
    LogConfig,
    CascadeLogManager,
    init_logging,
    get_log_manager,
    log
)


def init_cascade_logging(component: str, system: str):
    """Initialize both logging layers for a component"""
    kleene = get_kleene_logger(component)
    interpretive = get_interpretive_logger(system)
    
    # Bridge automatic translation
    def bridge_log(entry):
        translate_kleene_to_interpretive(entry, interpretive)
    
    kleene._emit_to_container = lambda entry: (
        print(kleene._format_container(entry)),
        bridge_log(entry)
    )
    
    return kleene, interpretive


# Convenience for quick setup
def setup_logging(component: str, system: str = "CASCADE"):
    """Quick setup for both loggers"""
    return init_cascade_logging(component, system)


# Export main interfaces
__all__ = [
    # Kleene (mathematical)
    'KleeneLogger',
    'LogLevel', 
    'get_kleene_logger',
    'log_fixed_point',
    'log_iterations',
    
    # Interpretive (human)
    'InterpretiveLogger',
    'ImpactLevel',
    'get_interpretive_logger',
    'translate_kleene_to_interpretive',
    
    # Log Manager (orchestrator)
    'LogMode',
    'LogConfig',
    'CascadeLogManager',
    'init_logging',
    'get_log_manager',
    'log',
    
    # Unified
    'init_cascade_logging',
    'setup_logging'
]
