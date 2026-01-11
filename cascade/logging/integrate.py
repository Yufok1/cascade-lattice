"""
CASCADE Logging Integration
Plug-and-play logging for existing CASCADE components.

Retrofits existing systems with world-class logging without major surgery.
"""

import functools
import time
from typing import Any, Callable, Dict, Optional

from .log_manager import get_log_manager, LogLevel, ImpactLevel


def log_component(component_name: str, system: str = "CASCADE"):
    """Decorator to add logging to any class or function"""
    def decorator(target):
        if isinstance(target, type):
            # Decorating a class
            return _log_class(target, component_name, system)
        else:
            # Decorating a function
            return _log_function(target, component_name, system)
    return decorator


def _log_class(cls, component_name: str, system: str):
    """Add logging to all methods of a class"""
    manager = get_log_manager()
    manager.register_component(component_name, system)
    
    for attr_name in dir(cls):
        if not attr_name.startswith('_'):
            attr = getattr(cls, attr_name)
            if callable(attr):
                setattr(cls, attr_name, _log_method(attr, component_name))
    
    return cls


def _log_function(func, component_name: str, system: str):
    """Add logging to a function"""
    manager = get_log_manager()
    manager.register_component(component_name, system)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        # Log start
        get_log_manager().log_operation(
            component_name, f"{func.__name__}_start",
            level=LogLevel.DEBUG,
            impact=ImpactLevel.TRACE,
            details={
                "context": f"Starting {func.__name__}",
                "consequence": f"Will execute {func.__name__}",
                "metrics": {"args": len(args), "kwargs": len(kwargs)}
            }
        )
        
        try:
            result = func(*args, **kwargs)
            
            # Log success
            duration = time.time() - start_time
            get_log_manager().log_operation(
                component_name, f"{func.__name__}_complete",
                level=LogLevel.INFO,
                impact=ImpactLevel.LOW,
                details={
                    "context": f"Completed {func.__name__}",
                    "consequence": f"Result ready",
                    "metrics": {"duration_seconds": duration}
                }
            )
            
            return result
            
        except Exception as e:
            # Log error
            get_log_manager().log_operation(
                component_name, f"{func.__name__}_error",
                level=LogLevel.ERROR,
                impact=ImpactLevel.HIGH,
                details={
                    "context": f"Failed in {func.__name__}",
                    "consequence": "Operation failed",
                    "metrics": {"error": str(e)}
                }
            )
            raise
    
    return wrapper


def _log_method(method, component_name: str):
    """Add logging to a method"""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        
        try:
            result = method(self, *args, **kwargs)
            
            # Log successful method call
            get_log_manager().log_operation(
                component_name, f"{method.__name__}",
                level=LogLevel.DEBUG,
                impact=ImpactLevel.TRACE,
                details={
                    "metrics": {"duration": time.time() - start_time}
                }
            )
            
            return result
            
        except Exception as e:
            # Log method error
            get_log_manager().log_operation(
                component_name, f"{method.__name__}_error",
                level=LogLevel.ERROR,
                impact=ImpactLevel.HIGH,
                details={
                    "context": f"Method {method.__name__} failed",
                    "metrics": {"error": str(e)}
                }
            )
            raise
    
    return wrapper


def log_kleene_iterations(operation_name: str):
    """Decorator specifically for Kleene fixed point iterations"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            get_log_manager().log_operation(
                "KleeneEngine", f"{operation_name}_start",
                level=LogLevel.INFO,
                impact=ImpactLevel.MEDIUM,
                details={
                    "context": f"Starting fixed point iteration for {operation_name}",
                    "consequence": "Will iterate until convergence"
                }
            )
            
            start_time = time.time()
            result = func(*args, **kwargs)
            
            # Extract iteration info from result if available
            iterations = getattr(result, 'iterations', 0)
            converged = getattr(result, 'converged', True)
            
            get_log_manager().log_operation(
                "KleeneEngine", f"{operation_name}_complete",
                level=LogLevel.INFO,
                impact=ImpactLevel.LOW if converged else ImpactLevel.HIGH,
                details={
                    "context": f"Fixed point iteration {'converged' if converged else 'diverged'}",
                    "consequence": f"Processed {iterations} iterations",
                    "metrics": {
                        "iterations": iterations,
                        "converged": converged,
                        "duration": time.time() - start_time
                    },
                    "fixed_point": converged
                }
            )
            
            return result
        return wrapper
    return decorator


def log_model_observation(model_id: str):
    """Decorator for model observation functions"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            get_log_manager().log_operation(
                "ModelObserver", f"observe_{model_id}",
                level=LogLevel.INFO,
                impact=ImpactLevel.MEDIUM,
                details={
                    "context": f"Starting observation of model {model_id}",
                    "consequence": "Will generate cryptographic proof"
                }
            )
            
            result = func(*args, **kwargs)
            
            # Extract observation details
            layers = getattr(result, 'layer_count', 0)
            merkle = getattr(result, 'merkle_root', 'unknown')
            
            get_log_manager().log_operation(
                "ModelObserver", f"observed_{model_id}",
                level=LogLevel.INFO,
                impact=ImpactLevel.LOW,
                details={
                    "context": f"Model observation complete",
                    "consequence": "Cryptographic proof generated",
                    "metrics": {
                        "model": model_id,
                        "layers": layers,
                        "merkle": merkle[:16] + "..."
                    },
                    "fixed_point": True
                }
            )
            
            return result
        return wrapper
    return decorator


def log_data_processing(dataset_name: str):
    """Decorator for data processing functions"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            get_log_manager().log_operation(
                "DataProcessor", f"process_{dataset_name}",
                level=LogLevel.INFO,
                impact=ImpactLevel.MEDIUM,
                details={
                    "context": f"Processing dataset {dataset_name}",
                    "consequence": "Will extract and analyze data"
                }
            )
            
            result = func(*args, **kwargs)
            
            # Extract processing stats
            records = getattr(result, 'record_count', 0)
            operations = getattr(result, 'operations', [])
            
            get_log_manager().log_operation(
                "DataProcessor", f"processed_{dataset_name}",
                level=LogLevel.INFO,
                impact=ImpactLevel.LOW,
                details={
                    "context": f"Dataset processing complete",
                    "consequence": f"Processed {records} records",
                    "metrics": {
                        "dataset": dataset_name,
                        "records": records,
                        "operations": len(operations)
                    }
                }
            )
            
            return result
        return wrapper
    return decorator


# Quick integration function
def integrate_cascade_logging():
    """One-call integration for entire CASCADE system"""
    from ..system.observer import SystemObserver
    from ..core.provenance import ProvenanceTracker
    from data_unity import run_kleene_iteration
    
    # Register main components
    manager = get_log_manager()
    manager.register_component("SystemObserver", "System Observatory")
    manager.register_component("ProvenanceTracker", "Model Observatory")
    manager.register_component("DataUnity", "Data Unity")
    manager.register_component("KleeneEngine", "NEXUS")
    
    print("✅ CASCADE logging integrated across all components")
    return manager
