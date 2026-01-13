"""
CASCADE Code Tracer - Trace execution through code to find bugs.

Repurposes cascade-lattice's causation graph for code execution:
- Each function call = Event
- Each return/exception = Event  
- Control flow = CausationLinks
- Data flow = CausationLinks with different type

Enables:
- "What called this function?" (trace_backwards)
- "What did this function call?" (trace_forwards)
- "What was the root cause of this crash?" (find_root_causes)
- "What will this bug affect?" (analyze_impact)
"""

import sys
import time
import hashlib
import functools
import traceback
import threading
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from pathlib import Path

from cascade.core.event import Event, CausationLink
from cascade.core.graph import CausationGraph
from cascade.analysis.tracer import Tracer, RootCauseAnalysis, ImpactAnalysis


@dataclass
class CodeEvent(Event):
    """
    An event in code execution - extends base Event with code-specific data.
    """
    # Code location
    file_path: str = ""
    line_number: int = 0
    function_name: str = ""
    class_name: Optional[str] = None
    module_name: str = ""
    
    # Execution context
    call_stack_depth: int = 0
    thread_id: int = 0
    
    # Data snapshot
    args: Dict[str, Any] = field(default_factory=dict)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    return_value: Optional[Any] = None
    exception: Optional[str] = None
    
    # Timing
    duration_ms: float = 0.0


@dataclass
class BugSignature:
    """
    A detected bug signature - pattern that indicates a problem.
    """
    bug_type: str  # "null_reference", "type_mismatch", "infinite_loop", etc.
    severity: str  # "critical", "error", "warning", "info"
    evidence: List[str]
    affected_events: List[str]  # Event IDs
    root_cause_event: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bug_type": self.bug_type,
            "severity": self.severity,
            "evidence": self.evidence,
            "affected_events": self.affected_events,
            "root_cause_event": self.root_cause_event,
            "confidence": self.confidence,
        }


class CodeTracer:
    """
    Trace code execution using cascade-lattice causation graph.
    
    Usage:
        tracer = CodeTracer()
        
        @tracer.trace
        def my_function(x, y):
            return x + y
        
        # After execution:
        tracer.find_root_causes(error_event_id)
        tracer.analyze_impact(function_event_id)
        tracer.detect_bugs()
    """
    
    def __init__(self, name: str = "code_tracer"):
        self.name = name
        self.graph = CausationGraph()
        self.tracer = Tracer(self.graph)
        
        # Execution tracking
        self._call_stack: List[str] = []  # Stack of event IDs
        self._current_depth = 0
        self._lock = threading.RLock()
        
        # Bug detection patterns
        self._bug_patterns: List[Callable] = []
        self._detected_bugs: List[BugSignature] = []
        
        # Statistics
        self._event_count = 0
        self._error_count = 0
        
        # Register built-in bug detectors
        self._register_builtin_detectors()
    
    def _register_builtin_detectors(self):
        """Register built-in bug detection patterns."""
        self._bug_patterns.extend([
            self._detect_null_reference,
            self._detect_type_errors,
            self._detect_recursion_depth,
            self._detect_slow_functions,
            self._detect_exception_patterns,
        ])
    
    def trace(self, func: Callable = None, *, capture_args: bool = True):
        """
        Decorator to trace function execution.
        
        Usage:
            @tracer.trace
            def my_function(x, y):
                return x + y
            
            # Or with options:
            @tracer.trace(capture_args=False)
            def sensitive_function(password):
                ...
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return self._traced_call(fn, args, kwargs, capture_args)
            return wrapper
        
        if func is not None:
            # Called as @tracer.trace without parentheses
            return decorator(func)
        return decorator
    
    def _traced_call(self, func: Callable, args: tuple, kwargs: dict, capture_args: bool) -> Any:
        """Execute a traced function call."""
        # Create entry event
        entry_event = self._create_entry_event(func, args, kwargs, capture_args)
        self.graph.add_event(entry_event)
        
        # Link to caller
        with self._lock:
            if self._call_stack:
                caller_id = self._call_stack[-1]
                link = CausationLink(
                    from_event=caller_id,
                    to_event=entry_event.event_id,
                    causation_type="call",
                    strength=1.0,
                    explanation=f"{func.__name__} called"
                )
                self.graph.add_link(link)
            
            self._call_stack.append(entry_event.event_id)
            self._current_depth += 1
        
        start_time = time.perf_counter()
        exception_info = None
        return_value = None
        
        try:
            return_value = func(*args, **kwargs)
            return return_value
        except Exception as e:
            exception_info = str(e)
            # Re-raise after recording
            raise
        finally:
            duration = (time.perf_counter() - start_time) * 1000
            
            # Create exit event
            exit_event = self._create_exit_event(
                func, entry_event, return_value, exception_info, duration
            )
            self.graph.add_event(exit_event)
            
            # Link entry -> exit
            link = CausationLink(
                from_event=entry_event.event_id,
                to_event=exit_event.event_id,
                causation_type="return" if not exception_info else "exception",
                strength=1.0,
                explanation=f"{func.__name__} {'returned' if not exception_info else 'raised ' + exception_info}"
            )
            self.graph.add_link(link)
            
            with self._lock:
                self._call_stack.pop()
                self._current_depth -= 1
                if exception_info:
                    self._error_count += 1
    
    def _create_entry_event(self, func: Callable, args: tuple, kwargs: dict, capture_args: bool) -> CodeEvent:
        """Create an event for function entry."""
        # Get source location
        try:
            file_path = func.__code__.co_filename
            line_number = func.__code__.co_firstlineno
        except AttributeError:
            file_path = "unknown"
            line_number = 0
        
        # Get function info
        module_name = func.__module__ or ""
        class_name = None
        if hasattr(func, '__qualname__') and '.' in func.__qualname__:
            class_name = func.__qualname__.rsplit('.', 1)[0]
        
        # Capture arguments (sanitized)
        captured_args = {}
        captured_kwargs = {}
        if capture_args:
            try:
                # Get parameter names
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                
                for i, arg in enumerate(args):
                    key = params[i] if i < len(params) else f"arg_{i}"
                    captured_args[key] = self._sanitize_value(arg)
                
                for k, v in kwargs.items():
                    captured_kwargs[k] = self._sanitize_value(v)
            except Exception:
                pass  # Can't capture args - non-critical
        
        self._event_count += 1
        
        return CodeEvent(
            timestamp=time.time(),
            component=module_name,
            event_type="function_entry",
            data={
                "function": func.__name__,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
            },
            file_path=file_path,
            line_number=line_number,
            function_name=func.__name__,
            class_name=class_name,
            module_name=module_name,
            call_stack_depth=self._current_depth,
            thread_id=threading.current_thread().ident,
            args=captured_args,
            kwargs=captured_kwargs,
        )
    
    def _create_exit_event(self, func: Callable, entry: CodeEvent, 
                          return_value: Any, exception: Optional[str], 
                          duration_ms: float) -> CodeEvent:
        """Create an event for function exit."""
        event_type = "function_return" if not exception else "function_exception"
        
        return CodeEvent(
            timestamp=time.time(),
            component=entry.module_name,
            event_type=event_type,
            data={
                "function": func.__name__,
                "duration_ms": duration_ms,
                "exception": exception,
                "has_return": return_value is not None,
            },
            file_path=entry.file_path,
            line_number=entry.line_number,
            function_name=func.__name__,
            class_name=entry.class_name,
            module_name=entry.module_name,
            call_stack_depth=entry.call_stack_depth,
            thread_id=entry.thread_id,
            return_value=self._sanitize_value(return_value) if return_value else None,
            exception=exception,
            duration_ms=duration_ms,
        )
    
    def _sanitize_value(self, value: Any, max_len: int = 200) -> Any:
        """Sanitize a value for storage (avoid huge objects)."""
        if value is None:
            return None
        
        # Numpy arrays
        if hasattr(value, 'shape'):
            return f"<array shape={value.shape} dtype={value.dtype}>"
        
        # Tensors
        if hasattr(value, 'size') and hasattr(value, 'dtype'):
            return f"<tensor size={value.size()} dtype={value.dtype}>"
        
        # Large strings
        if isinstance(value, str) and len(value) > max_len:
            return value[:max_len] + "..."
        
        # Lists/dicts
        if isinstance(value, (list, dict)):
            s = str(value)
            if len(s) > max_len:
                return s[:max_len] + "..."
            return value
        
        # Primitives
        if isinstance(value, (int, float, bool, str)):
            return value
        
        # Fallback: type name
        return f"<{type(value).__name__}>"
    
    # =========================================================================
    # CAUSATION TRACING (via cascade-lattice)
    # =========================================================================
    
    def find_root_causes(self, event_id: str) -> RootCauseAnalysis:
        """
        Find the root causes of an event (e.g., what caused this crash?).
        
        Uses cascade-lattice's backwards tracing to find the origin.
        """
        return self.tracer.find_root_causes(event_id)
    
    def analyze_impact(self, event_id: str) -> ImpactAnalysis:
        """
        Analyze the downstream impact of an event.
        
        "What did this bug affect?"
        """
        return self.tracer.analyze_impact(event_id)
    
    def trace_backwards(self, event_id: str, max_depth: int = 100):
        """Trace what led to this event."""
        return self.tracer.trace_backwards(event_id, max_depth)
    
    def trace_forwards(self, event_id: str, max_depth: int = 100):
        """Trace what this event caused."""
        return self.tracer.trace_forwards(event_id, max_depth)
    
    # =========================================================================
    # BUG DETECTION
    # =========================================================================
    
    def detect_bugs(self) -> List[BugSignature]:
        """
        Run all bug detection patterns on collected events.
        """
        self._detected_bugs = []
        
        for detector in self._bug_patterns:
            try:
                bugs = detector()
                self._detected_bugs.extend(bugs)
            except Exception as e:
                print(f"[DIAG] Bug detector {detector.__name__} failed: {e}")
        
        return self._detected_bugs
    
    def _detect_null_reference(self) -> List[BugSignature]:
        """Detect null/None reference patterns."""
        bugs = []
        
        for event in self.graph.get_recent_events(1000):
            if event.event_type == "function_exception":
                exc = event.data.get("exception", "")
                if "NoneType" in exc or "null" in exc.lower():
                    bugs.append(BugSignature(
                        bug_type="null_reference",
                        severity="error",
                        evidence=[exc],
                        affected_events=[event.event_id],
                        confidence=0.9,
                    ))
        
        return bugs
    
    def _detect_type_errors(self) -> List[BugSignature]:
        """Detect type mismatch patterns."""
        bugs = []
        
        for event in self.graph.get_recent_events(1000):
            if event.event_type == "function_exception":
                exc = event.data.get("exception", "")
                if "TypeError" in exc or "type" in exc.lower():
                    bugs.append(BugSignature(
                        bug_type="type_mismatch",
                        severity="error",
                        evidence=[exc],
                        affected_events=[event.event_id],
                        confidence=0.85,
                    ))
        
        return bugs
    
    def _detect_recursion_depth(self) -> List[BugSignature]:
        """Detect excessive recursion."""
        bugs = []
        
        # Find events with high call depth
        for event in self.graph.get_recent_events(1000):
            if hasattr(event, 'call_stack_depth') and event.call_stack_depth > 50:
                bugs.append(BugSignature(
                    bug_type="deep_recursion",
                    severity="warning",
                    evidence=[f"Call stack depth: {event.call_stack_depth}"],
                    affected_events=[event.event_id],
                    confidence=0.7,
                ))
        
        return bugs
    
    def _detect_slow_functions(self) -> List[BugSignature]:
        """Detect unusually slow functions."""
        bugs = []
        
        for event in self.graph.get_recent_events(1000):
            if event.event_type == "function_return":
                duration = event.data.get("duration_ms", 0)
                if duration > 1000:  # > 1 second
                    bugs.append(BugSignature(
                        bug_type="slow_function",
                        severity="warning",
                        evidence=[f"Duration: {duration:.1f}ms"],
                        affected_events=[event.event_id],
                        confidence=0.8,
                    ))
        
        return bugs
    
    def _detect_exception_patterns(self) -> List[BugSignature]:
        """Detect recurring exception patterns."""
        bugs = []
        
        # Group exceptions by type
        exception_counts: Dict[str, List[str]] = {}
        
        for event in self.graph.get_recent_events(1000):
            if event.event_type == "function_exception":
                exc = event.data.get("exception", "unknown")
                if exc not in exception_counts:
                    exception_counts[exc] = []
                exception_counts[exc].append(event.event_id)
        
        # Flag recurring exceptions
        for exc_type, event_ids in exception_counts.items():
            if len(event_ids) > 3:
                bugs.append(BugSignature(
                    bug_type="recurring_exception",
                    severity="error",
                    evidence=[f"{exc_type} occurred {len(event_ids)} times"],
                    affected_events=event_ids,
                    confidence=0.9,
                ))
        
        return bugs
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            "name": self.name,
            "total_events": self._event_count,
            "error_count": self._error_count,
            "bugs_detected": len(self._detected_bugs),
            "graph_nodes": len(self.graph._events),
            "graph_links": len(self.graph._links),
        }
    
    def get_error_chain(self, error_event_id: str) -> str:
        """
        Get a human-readable error chain from root cause to error.
        """
        analysis = self.find_root_causes(error_event_id)
        
        if not analysis.chains:
            return "No causal chain found"
        
        lines = ["ERROR CHAIN ANALYSIS", "=" * 50]
        
        # Take the deepest chain (most likely root cause)
        chain = analysis.chains[0]
        
        for i, event in enumerate(chain.events):
            prefix = "  " * i
            if event.event_type == "function_exception":
                lines.append(f"{prefix}❌ {event.component}.{event.data.get('function', '?')}")
                lines.append(f"{prefix}   Exception: {event.data.get('exception', '?')}")
            elif event.event_type == "function_entry":
                lines.append(f"{prefix}→ {event.component}.{event.data.get('function', '?')}")
            elif event.event_type == "function_return":
                lines.append(f"{prefix}← {event.component}.{event.data.get('function', '?')}")
        
        return "\n".join(lines)
