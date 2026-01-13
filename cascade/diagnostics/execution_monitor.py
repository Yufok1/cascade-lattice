"""
CASCADE Execution Monitor - Monitor live code execution.

Wraps Python execution similar to how cascade.observe wraps processes.
Captures execution flow, exceptions, and anomalies in real-time.
"""

import sys
import time
import threading
import traceback
import functools
from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager
import queue

from cascade.core.event import Event, CausationLink
from cascade.core.graph import CausationGraph
from cascade.core.adapter import SymbioticAdapter


@dataclass
class ExecutionFrame:
    """A frame in the execution trace."""
    frame_id: str
    function_name: str
    file_path: str
    line_number: int
    local_vars: Dict[str, str]  # Sanitized string representations
    timestamp: float
    duration_ms: Optional[float] = None
    exception: Optional[str] = None


@dataclass
class Anomaly:
    """An execution anomaly detected during monitoring."""
    anomaly_type: str
    description: str
    severity: str
    frame_id: str
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)


class ExecutionMonitor:
    """
    Monitor live code execution and capture anomalies.
    
    Uses sys.settrace to capture every function call, return, and exception.
    Integrates with cascade-lattice's causation graph for tracing.
    
    Usage:
        monitor = ExecutionMonitor()
        
        with monitor.monitoring():
            # Your code here
            result = my_function()
        
        # After execution:
        monitor.get_anomalies()
        monitor.get_execution_trace()
    """
    
    def __init__(self, 
                 capture_locals: bool = True,
                 max_depth: int = 100,
                 exclude_modules: Optional[Set[str]] = None):
        self.capture_locals = capture_locals
        self.max_depth = max_depth
        self.exclude_modules = exclude_modules or {
            'cascade', 'threading', 'queue', 'logging',
            'importlib', '_frozen_importlib', 'posixpath', 'genericpath',
        }
        
        # Execution tracking
        self.frames: List[ExecutionFrame] = []
        self.anomalies: List[Anomaly] = []
        self.call_stack: List[str] = []
        
        # Causation graph
        self.graph = CausationGraph()
        self.adapter = SymbioticAdapter()
        
        # Thresholds for anomaly detection
        self.slow_threshold_ms = 100
        self.deep_recursion_threshold = 50
        
        # State
        self._monitoring = False
        self._lock = threading.RLock()
        self._frame_counter = 0
        self._function_times: Dict[str, List[float]] = {}
        self._prev_trace = None
    
    @contextmanager
    def monitoring(self):
        """Context manager for monitoring execution."""
        self.start()
        try:
            yield self
        finally:
            self.stop()
    
    def start(self):
        """Start execution monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._prev_trace = sys.gettrace()
        sys.settrace(self._trace_calls)
        threading.settrace(self._trace_calls)
    
    def stop(self):
        """Stop execution monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        sys.settrace(self._prev_trace)
        threading.settrace(None)
        
        # Analyze collected data for anomalies
        self._analyze_for_anomalies()
    
    def _trace_calls(self, frame, event, arg):
        """Trace function for sys.settrace."""
        if not self._monitoring:
            return None
        
        # Filter out excluded modules
        code = frame.f_code
        module = frame.f_globals.get('__name__', '')
        
        if any(module.startswith(exc) for exc in self.exclude_modules):
            return None
        
        # Check depth
        if len(self.call_stack) > self.max_depth:
            return None
        
        try:
            if event == 'call':
                self._handle_call(frame, code)
            elif event == 'return':
                self._handle_return(frame, code, arg)
            elif event == 'exception':
                self._handle_exception(frame, code, arg)
        except Exception:
            # Don't let tracing errors affect the program
            pass
        
        return self._trace_calls
    
    def _handle_call(self, frame, code):
        """Handle function call event."""
        with self._lock:
            self._frame_counter += 1
            frame_id = f"frame_{self._frame_counter}"
            
            # Capture local variables
            local_vars = {}
            if self.capture_locals:
                for name, value in list(frame.f_locals.items())[:20]:
                    local_vars[name] = self._sanitize_value(value)
            
            exec_frame = ExecutionFrame(
                frame_id=frame_id,
                function_name=code.co_name,
                file_path=code.co_filename,
                line_number=frame.f_lineno,
                local_vars=local_vars,
                timestamp=time.time(),
            )
            
            self.frames.append(exec_frame)
            
            # Create causation link to caller
            if self.call_stack:
                caller_id = self.call_stack[-1]
                link = CausationLink(
                    from_event=caller_id,
                    to_event=frame_id,
                    causation_type="call",
                    strength=1.0,
                    explanation=f"Called {code.co_name}"
                )
                self.graph.add_link(link)
            
            self.call_stack.append(frame_id)
            
            # Track function timing
            func_key = f"{code.co_filename}:{code.co_name}"
            if func_key not in self._function_times:
                self._function_times[func_key] = []
    
    def _handle_return(self, frame, code, return_value):
        """Handle function return event."""
        with self._lock:
            if not self.call_stack:
                return
            
            frame_id = self.call_stack.pop()
            
            # Find the frame and update duration
            for exec_frame in reversed(self.frames):
                if exec_frame.frame_id == frame_id:
                    exec_frame.duration_ms = (time.time() - exec_frame.timestamp) * 1000
                    
                    # Track timing
                    func_key = f"{code.co_filename}:{code.co_name}"
                    if func_key in self._function_times:
                        self._function_times[func_key].append(exec_frame.duration_ms)
                    break
    
    def _handle_exception(self, frame, code, arg):
        """Handle exception event."""
        exc_type, exc_value, exc_tb = arg
        
        with self._lock:
            frame_id = self.call_stack[-1] if self.call_stack else f"frame_{self._frame_counter}"
            
            # Update frame with exception
            for exec_frame in reversed(self.frames):
                if exec_frame.frame_id == frame_id:
                    exec_frame.exception = f"{exc_type.__name__}: {exc_value}"
                    break
            
            # Record as anomaly
            self.anomalies.append(Anomaly(
                anomaly_type="exception",
                description=f"{exc_type.__name__}: {exc_value}",
                severity="error",
                frame_id=frame_id,
                timestamp=time.time(),
                context={
                    "exception_type": exc_type.__name__,
                    "exception_message": str(exc_value),
                    "function": code.co_name,
                    "file": code.co_filename,
                    "line": frame.f_lineno,
                },
            ))
    
    def _analyze_for_anomalies(self):
        """Analyze collected data for additional anomalies."""
        # Check for slow functions
        for func_key, times in self._function_times.items():
            if times:
                avg_time = sum(times) / len(times)
                max_time = max(times)
                
                if max_time > self.slow_threshold_ms:
                    self.anomalies.append(Anomaly(
                        anomaly_type="slow_execution",
                        description=f"Slow function: {func_key} (max: {max_time:.1f}ms, avg: {avg_time:.1f}ms)",
                        severity="warning",
                        frame_id="",
                        timestamp=time.time(),
                        context={
                            "function": func_key,
                            "max_time_ms": max_time,
                            "avg_time_ms": avg_time,
                            "call_count": len(times),
                        },
                    ))
        
        # Check for deep recursion
        max_depth = max((len(self.call_stack) for f in self.frames), default=0)
        if max_depth > self.deep_recursion_threshold:
            self.anomalies.append(Anomaly(
                anomaly_type="deep_recursion",
                description=f"Deep call stack detected: {max_depth} frames",
                severity="warning",
                frame_id="",
                timestamp=time.time(),
                context={"max_depth": max_depth},
            ))
        
        # Check for repeated exceptions
        exception_counts: Dict[str, int] = {}
        for anomaly in self.anomalies:
            if anomaly.anomaly_type == "exception":
                exc_type = anomaly.context.get("exception_type", "unknown")
                exception_counts[exc_type] = exception_counts.get(exc_type, 0) + 1
        
        for exc_type, count in exception_counts.items():
            if count > 3:
                self.anomalies.append(Anomaly(
                    anomaly_type="repeated_exception",
                    description=f"{exc_type} occurred {count} times",
                    severity="error",
                    frame_id="",
                    timestamp=time.time(),
                    context={"exception_type": exc_type, "count": count},
                ))
    
    def _sanitize_value(self, value: Any, max_len: int = 100) -> str:
        """Convert value to safe string representation."""
        try:
            if value is None:
                return "None"
            
            # Numpy arrays
            if hasattr(value, 'shape'):
                return f"<array {value.shape}>"
            
            # Tensors
            if hasattr(value, 'size') and callable(value.size):
                return f"<tensor {value.size()}>"
            
            # Large collections
            if isinstance(value, (list, dict, set)):
                s = str(value)
                if len(s) > max_len:
                    return s[:max_len] + "..."
                return s
            
            # Strings
            if isinstance(value, str):
                if len(value) > max_len:
                    return value[:max_len] + "..."
                return repr(value)
            
            # Primitives
            if isinstance(value, (int, float, bool)):
                return str(value)
            
            # Fallback
            return f"<{type(value).__name__}>"
        except Exception:
            return "<error>"
    
    # =========================================================================
    # QUERIES
    # =========================================================================
    
    def get_anomalies(self, severity: Optional[str] = None) -> List[Anomaly]:
        """Get detected anomalies, optionally filtered by severity."""
        if severity:
            return [a for a in self.anomalies if a.severity == severity]
        return list(self.anomalies)
    
    def get_execution_trace(self) -> List[ExecutionFrame]:
        """Get the execution trace."""
        return list(self.frames)
    
    def get_call_graph(self) -> Dict[str, List[str]]:
        """Get the call graph as adjacency list."""
        graph: Dict[str, List[str]] = {}
        
        for link in self.graph._links:
            if link.from_event not in graph:
                graph[link.from_event] = []
            graph[link.from_event].append(link.to_event)
        
        return graph
    
    def get_hotspots(self, top_n: int = 10) -> List[Tuple[str, float, int]]:
        """Get the hottest functions by total time spent."""
        totals: Dict[str, Tuple[float, int]] = {}
        
        for func_key, times in self._function_times.items():
            if times:
                totals[func_key] = (sum(times), len(times))
        
        sorted_funcs = sorted(totals.items(), key=lambda x: x[1][0], reverse=True)
        return [(func, total, count) for func, (total, count) in sorted_funcs[:top_n]]
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary."""
        return {
            "total_frames": len(self.frames),
            "total_anomalies": len(self.anomalies),
            "anomalies_by_type": self._count_by_key(self.anomalies, lambda a: a.anomaly_type),
            "anomalies_by_severity": self._count_by_key(self.anomalies, lambda a: a.severity),
            "functions_traced": len(self._function_times),
        }
    
    def _count_by_key(self, items, key_func) -> Dict[str, int]:
        """Count items by key function."""
        counts: Dict[str, int] = {}
        for item in items:
            key = key_func(item)
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    def get_report(self) -> str:
        """Generate a human-readable report."""
        lines = [
            "EXECUTION MONITORING REPORT",
            "=" * 60,
            f"Frames captured: {len(self.frames)}",
            f"Functions traced: {len(self._function_times)}",
            f"Anomalies detected: {len(self.anomalies)}",
            "",
        ]
        
        # Anomalies by severity
        if self.anomalies:
            lines.append("ANOMALIES")
            lines.append("-" * 40)
            
            severity_icons = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
            
            for anomaly in sorted(self.anomalies, key=lambda a: 
                                  ["critical", "error", "warning", "info"].index(a.severity)
                                  if a.severity in ["critical", "error", "warning", "info"] else 99):
                icon = severity_icons.get(anomaly.severity, "•")
                lines.append(f"  {icon} [{anomaly.anomaly_type}] {anomaly.description}")
            
            lines.append("")
        
        # Hotspots
        hotspots = self.get_hotspots(5)
        if hotspots:
            lines.append("PERFORMANCE HOTSPOTS")
            lines.append("-" * 40)
            
            for func, total_ms, count in hotspots:
                avg_ms = total_ms / count if count else 0
                lines.append(f"  {func}")
                lines.append(f"    Total: {total_ms:.1f}ms | Calls: {count} | Avg: {avg_ms:.1f}ms")
            
            lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# CONVENIENCE DECORATORS
# =============================================================================

def monitor(func: Callable = None, **kwargs) -> Callable:
    """
    Decorator to monitor a function's execution.
    
    Usage:
        @monitor
        def my_function():
            ...
        
        # Access monitoring results
        my_function._monitor_results
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **call_kwargs):
            monitor = ExecutionMonitor(**kwargs)
            with monitor.monitoring():
                result = fn(*args, **call_kwargs)
            
            # Attach results to function
            wrapper._monitor_results = {
                "anomalies": monitor.get_anomalies(),
                "summary": monitor.get_summary(),
                "report": monitor.get_report(),
            }
            
            return result
        
        wrapper._monitor_results = None
        return wrapper
    
    if func is not None:
        return decorator(func)
    return decorator
