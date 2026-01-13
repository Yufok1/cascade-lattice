"""
CASCADE Diagnostics Demo - Exposing bugs with tracing.

This demonstrates how to use the cascade.diagnostics module
to trace through code and expose issues.
"""

import sys
sys.path.insert(0, "F:/End-Game/github-pypi-lattice")

from cascade.diagnostics import (
    diagnose,
    CodeTracer,
    BugDetector,
    ExecutionMonitor,
    DiagnosticEngine,
    monitor,
)


# =============================================================================
# DEMO 1: Trace function execution and find root causes
# =============================================================================

print("=" * 60)
print("DEMO 1: Function Execution Tracing")
print("=" * 60)

tracer = CodeTracer(name="demo_tracer")


@tracer.trace
def calculate_average(numbers):
    """Calculate average - but has a bug with empty lists!"""
    total = sum(numbers)
    return total / len(numbers)  # Bug: ZeroDivisionError if empty


@tracer.trace
def process_data(data):
    """Process data and return stats."""
    averages = []
    for dataset in data:
        avg = calculate_average(dataset)
        averages.append(avg)
    return averages


# Run with normal data
print("\n1a. Running with valid data...")
try:
    result = process_data([[1, 2, 3], [4, 5, 6]])
    print(f"    Result: {result}")
except Exception as e:
    print(f"    Error: {e}")

# Run with buggy data (empty list)
print("\n1b. Running with empty list (trigger bug)...")
try:
    result = process_data([[1, 2, 3], []])  # Empty list causes ZeroDivisionError
    print(f"    Result: {result}")
except Exception as e:
    print(f"    Error: {e}")

# Check detected bugs
print("\n1c. Detecting bugs from execution trace...")
bugs = tracer.detect_bugs()
for bug in bugs:
    print(f"    - {bug.bug_type}: {bug.evidence}")

# Print summary
print("\n1d. Tracer Summary:")
summary = tracer.get_summary()
for key, value in summary.items():
    print(f"    {key}: {value}")


# =============================================================================
# DEMO 2: Static code analysis with BugDetector
# =============================================================================

print("\n" + "=" * 60)
print("DEMO 2: Static Code Analysis")
print("=" * 60)

# Create a buggy file for demonstration
buggy_code = '''
def process_user(user_data):
    """Process user - has several bugs!"""
    # Bug 1: Bare except
    try:
        name = user_data["name"]
    except:
        pass
    
    # Bug 2: Mutable default argument
    def add_item(item, items=[]):
        items.append(item)
        return items
    
    # Bug 3: Hardcoded password
    password = "admin123"
    
    # Bug 4: SQL injection risk
    cursor.execute("SELECT * FROM users WHERE name = '%s'" % name)
    
    # Bug 5: Comparing to None with ==
    if user_data == None:
        return
    
    # Bug 6: File without context manager
    f = open("data.txt", "r")
    data = f.read()
    
    return name

def unreachable_example():
    """Has unreachable code."""
    return 42
    print("This never runs")  # Unreachable
'''

# Write buggy code to temp file
import tempfile
import os

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(buggy_code)
    buggy_file = f.name

print(f"\n2a. Scanning buggy code file...")
detector = BugDetector()
issues = detector.scan_file(buggy_file)

print(f"    Found {len(issues)} issues:\n")
for issue in sorted(issues, key=lambda i: ["critical", "error", "warning", "info"].index(i.severity)
                    if i.severity in ["critical", "error", "warning", "info"] else 99):
    severity_icon = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
    print(f"    {severity_icon} [{issue.severity}] Line {issue.line_number}: {issue.message}")
    if issue.suggestion:
        print(f"       💡 {issue.suggestion}")

# Clean up temp file
os.unlink(buggy_file)

print("\n2b. Bug Detection Summary:")
print(detector.get_report())


# =============================================================================
# DEMO 3: Real-time Execution Monitoring
# =============================================================================

print("\n" + "=" * 60)
print("DEMO 3: Real-time Execution Monitoring")
print("=" * 60)

print("\n3a. Monitoring execution with anomaly detection...")

monitor_instance = ExecutionMonitor()


def recursive_fib(n):
    """Intentionally slow recursive fibonacci."""
    if n <= 1:
        return n
    return recursive_fib(n - 1) + recursive_fib(n - 2)


def raise_error():
    """Function that raises an error."""
    raise ValueError("Intentional test error")


with monitor_instance.monitoring():
    # Normal computation
    result = recursive_fib(15)
    
    # Error (intentionally caught and ignored for demo)
    try:
        raise_error()
    except ValueError:
        pass  # Expected - demonstrating exception capture

print(f"    Frames captured: {len(monitor_instance.frames)}")
print(f"    Anomalies detected: {len(monitor_instance.anomalies)}")

print("\n3b. Execution Monitoring Report:")
print(monitor_instance.get_report())


# =============================================================================
# DEMO 4: Full Diagnostic Engine
# =============================================================================

print("\n" + "=" * 60)
print("DEMO 4: Full Diagnostic Engine")
print("=" * 60)

print("\n4a. Running full diagnostics on a function...")


def buggy_function(x, y):
    """Function with potential issues."""
    if x is None:
        raise ValueError("x cannot be None")
    result = x / y  # Potential ZeroDivisionError
    return result


engine = DiagnosticEngine()

# Analyze the function execution
try:
    report = engine.analyze_execution(buggy_function, 10, 2)
    print(f"    Report generated: {report.report_id}")
    print(f"    Total findings: {len(report.findings)}")
except Exception as e:
    print(f"    Analysis captured error: {e}")

# Analyze with error
print("\n4b. Analyzing execution that triggers error...")
try:
    report = engine.analyze_execution(buggy_function, 10, 0)
except ZeroDivisionError:
    # The error still propagates but we captured the trace
    print("    Error captured in execution trace")


# =============================================================================
# DEMO 5: The diagnose() convenience function
# =============================================================================

print("\n" + "=" * 60)
print("DEMO 5: diagnose() Convenience Function")
print("=" * 60)

# Create another temp file
simple_code = '''
def hello():
    try:
        pass  # Empty except coming
    except:
        pass
'''

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(simple_code)
    simple_file = f.name

print(f"\n5a. Quick diagnosis of a file...")
report = diagnose(simple_file)
print(f"    Issues found: {len(report.findings)}")

for finding in report.findings:
    print(f"    - {finding.title}: {finding.description}")

os.unlink(simple_file)


# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print("CASCADE DIAGNOSTICS - Summary")
print("=" * 60)

print("""
The cascade.diagnostics module repurposes cascade-lattice for debugging:

1. CodeTracer - Trace function execution with causation graph
   - @tracer.trace decorator captures every call
   - find_root_causes() traces backwards from errors
   - analyze_impact() predicts what a bug affects
   - detect_bugs() finds patterns in execution

2. BugDetector - Static analysis with AST pattern matching
   - Detects: null refs, bare excepts, SQL injection, etc.
   - scan_file() / scan_directory() for batch analysis
   - Custom patterns can be registered

3. ExecutionMonitor - Real-time sys.settrace monitoring
   - Captures every function call during execution
   - Detects anomalies: slow functions, deep recursion, repeated errors
   - get_hotspots() finds performance bottlenecks

4. DiagnosticEngine - Unified diagnostic reports
   - Combines all analyzers
   - Markdown/JSON output
   - Severity-ranked findings with suggestions

5. diagnose() - One-line convenience function
   - Works on files, directories, or functions

The core insight: Events = execution points, Links = causation.
Trace backwards from bugs to find root causes.
Trace forwards from changes to predict impact.
""")
