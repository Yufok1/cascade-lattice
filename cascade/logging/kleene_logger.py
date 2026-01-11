"""
CASCADE Kleene Fixed Point Logger
Industry-standard mathematical logging for debugging and verification.

Each log entry is a fixed point observation - hashable, verifiable, complete.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from contextlib import contextmanager


class LogLevel(Enum):
    """Mathematical significance levels"""
    CRITICAL = "CRITICAL"  # System-breaking fixed point failure
    ERROR = "ERROR"        # Fixed point not reached
    WARNING = "WARNING"    # Unexpected state transition
    INFO = "INFO"          # Fixed point achieved
    DEBUG = "DEBUG"        # State transition details
    TRACE = "TRACE"        # Every computation step


@dataclass
class KleeneLogEntry:
    """A single fixed point observation"""
    timestamp: float = field(default_factory=time.time)
    level: LogLevel = LogLevel.INFO
    component: str = ""
    operation: str = ""
    state_before: Optional[Dict] = None
    state_after: Optional[Dict] = None
    fixed_point_reached: bool = False
    iteration_count: int = 0
    hash_value: str = field(init=False)
    
    def __post_init__(self):
        # Create content hash for verifiability
        content = {
            "timestamp": self.timestamp,
            "component": self.component,
            "operation": self.operation,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "iteration": self.iteration_count
        }
        self.hash_value = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.timestamp,
            "lvl": self.level.value,
            "comp": self.component,
            "op": self.operation,
            "before": self.state_before,
            "after": self.state_after,
            "fixed": self.fixed_point_reached,
            "iter": self.iteration_count,
            "hash": self.hash_value
        }


class KleeneLogger:
    """Mathematical logging for fixed point systems"""
    
    def __init__(self, component_name: str):
        self.component = component_name
        self.entries: List[KleeneLogEntry] = []
        self.session_start = time.time()
        self.operation_count = 0
        
    def log(self, level: LogLevel, operation: str, 
            state_before: Optional[Dict] = None,
            state_after: Optional[Dict] = None,
            fixed_point: bool = False,
            iterations: int = 0):
        """Record a state transition"""
        
        entry = KleeneLogEntry(
            level=level,
            component=self.component,
            operation=operation,
            state_before=state_before,
            state_after=state_after,
            fixed_point_reached=fixed_point,
            iteration_count=iterations
        )
        
        self.entries.append(entry)
        self._emit_to_container(entry)
        
    def _emit_to_container(self, entry: KleeneLogEntry):
        """Emit structured log to container with colors"""
        # ANSI color codes
        colors = {
            "CRITICAL": "\033[91m",  # Bright red
            "ERROR": "\033[31m",      # Red
            "WARNING": "\033[33m",    # Yellow
            "INFO": "\033[32m",       # Green
            "DEBUG": "\033[36m",      # Cyan
            "TRACE": "\033[90m",      # Gray
            "RESET": "\033[0m",       # Reset
            "BOLD": "\033[1m",        # Bold
            "DIM": "\033[2m",         # Dim
        }
        
        color = colors.get(entry.level.value, colors["RESET"])
        reset = colors["RESET"]
        dim = colors["DIM"]
        
        # Format with colors
        print(f"{color}[KLEENE]{reset} {color}{entry.level.value:8}{reset} | "
              f"{dim}{entry.component:20}{reset} | "
              f"{entry.operation:30} | "
              f"Iter:{entry.iteration_count:3} | "
              f"Fixed:{'Y' if entry.fixed_point_reached else 'N':1} | "
              f"{dim}Hash:{entry.hash_value}{reset}")
    
    @contextmanager
    def observe_operation(self, operation: str, initial_state: Dict):
        """Context manager for observing operations"""
        self.operation_count += 1
        iterations = 0
        
        try:
            self.log(LogLevel.DEBUG, f"{operation}_start", 
                    state_before=initial_state)
            
            # Yield control back to operation
            yield self
            
            # Operation completed successfully
            self.log(LogLevel.INFO, f"{operation}_complete",
                    fixed_point=True, iterations=iterations)
                    
        except Exception as e:
            self.log(LogLevel.ERROR, f"{operation}_failed",
                    state_after={"error": str(e)})
            raise
    
    def fixed_point(self, operation: str, final_state: Dict, iterations: int):
        """Log successful fixed point convergence"""
        self.log(LogLevel.INFO, f"{operation}_fixed_point",
                state_after=final_state,
                fixed_point=True,
                iterations=iterations)
    
    def divergence(self, operation: str, state: Dict):
        """Log when system diverges (no fixed point)"""
        self.log(LogLevel.WARNING, f"{operation}_divergence",
                state_after=state,
                fixed_point=False)
    
    def critical_failure(self, operation: str, error_state: Dict):
        """Log critical system failure"""
        self.log(LogLevel.CRITICAL, f"{operation}_critical",
                state_after=error_state,
                fixed_point=False)
    
    def get_session_hash(self) -> str:
        """Get hash of entire session for verification"""
        content = {
            "component": self.component,
            "start": self.session_start,
            "operations": self.operation_count,
            "entries": [e.hash_value for e in self.entries]
        }
        return hashlib.sha256(json.dumps(content).encode()).hexdigest()


# Global loggers for major components
_loggers: Dict[str, KleeneLogger] = {}


def get_kleene_logger(component: str) -> KleeneLogger:
    """Get or create logger for component"""
    if component not in _loggers:
        _loggers[component] = KleeneLogger(component)
    return _loggers[component]


# Convenience decorators
def log_fixed_point(operation: str):
    """Decorator to automatically log fixed point operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_kleene_logger(func.__module__)
            start_state = {"args": str(args), "kwargs": str(kwargs)}
            
            try:
                result = func(*args, **kwargs)
                logger.fixed_point(operation, {"result": str(result)}, 1)
                return result
            except Exception as e:
                logger.critical_failure(operation, {"error": str(e)})
                raise
        return wrapper
    return decorator


def log_iterations(operation: str):
    """Decorator for operations that iterate to fixed points"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_kleene_logger(func.__module__)
            
            # Simulate iteration counting (real implementation would track)
            result = func(*args, **kwargs)
            iterations = getattr(result, 'iterations', 1)
            
            logger.fixed_point(operation, {"converged": True}, iterations)
            return result
        return wrapper
    return decorator
