"""
CASCADE DIAGNOSTICS - Code Bug Exposure System

A novel application of cascade-lattice: instead of tracing AI inference,
we trace CODE EXECUTION to expose bugs - known and unknown.

Core Insight:
- cascade-lattice traces causation chains (what caused what)
- Forensics module extracts artifacts (evidence of processing)
- System module ingests and analyzes repositories
- Monitor adapts to ANY signal format (symbiotic)

For DEBUGGING, we repurpose these:
- Events = Code execution points, function calls, variable states
- CausationLinks = Control flow, data dependencies
- Artifacts = Bug signatures, anomaly patterns
- GhostLog = Inferred sequence of execution failures
- Tracer = Backtrack from crash/bug to root cause

This creates a "debugger on steroids" that:
1. OBSERVES code execution at any granularity
2. TRACES causation chains to find root causes
3. EXPOSES hidden bugs through pattern recognition
4. PREDICTS cascading failures before they complete

Usage:
    from cascade.diagnostics import diagnose, CodeTracer, BugDetector
    
    # Quick analysis of a file
    report = diagnose("path/to/file.py")
    print(engine.to_markdown(report))
    
    # Trace function execution
    tracer = CodeTracer()
    
    @tracer.trace
    def my_function(x):
        return x * 2
    
    # After execution, find root causes
    tracer.find_root_causes(error_event_id)
    
    # Static bug detection
    detector = BugDetector()
    issues = detector.scan_directory("./my_project")
"""

from cascade.diagnostics.code_tracer import CodeTracer, CodeEvent, BugSignature
from cascade.diagnostics.bug_detector import BugDetector, BugPattern, DetectedIssue
from cascade.diagnostics.execution_monitor import ExecutionMonitor, ExecutionFrame, Anomaly, monitor
from cascade.diagnostics.report import DiagnosticReport, DiagnosticFinding, DiagnosticEngine, diagnose

__all__ = [
    # Main classes
    "CodeTracer",
    "BugDetector", 
    "ExecutionMonitor",
    "DiagnosticReport",
    "DiagnosticEngine",
    
    # Data classes
    "CodeEvent",
    "BugSignature",
    "BugPattern",
    "DetectedIssue",
    "ExecutionFrame",
    "Anomaly",
    "DiagnosticFinding",
    
    # Convenience
    "diagnose",
    "monitor",
]
