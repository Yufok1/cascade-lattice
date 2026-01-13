"""
CASCADE Diagnostic Report - Generate comprehensive diagnostic reports.

Combines:
- CodeTracer execution traces
- BugDetector static analysis
- ExecutionMonitor runtime anomalies
- GhostLog forensic reconstruction

Into a unified diagnostic report.
"""

import time
import json
import hashlib
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from cascade.core.graph import CausationGraph
from cascade.forensics.analyzer import DataForensics, GhostLog


@dataclass
class DiagnosticFinding:
    """A single diagnostic finding."""
    finding_id: str
    category: str  # "static", "runtime", "forensic", "trace"
    severity: str  # "critical", "error", "warning", "info"
    title: str
    description: str
    location: Optional[Dict[str, Any]] = None  # file, line, function
    evidence: List[str] = field(default_factory=list)
    related_findings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass 
class DiagnosticReport:
    """
    A comprehensive diagnostic report.
    
    Aggregates findings from multiple sources:
    - Static analysis (BugDetector)
    - Runtime monitoring (ExecutionMonitor)
    - Execution tracing (CodeTracer)
    - Forensic analysis (GhostLog)
    """
    
    report_id: str
    title: str
    created_at: float
    target: str  # File, directory, or module analyzed
    
    findings: List[DiagnosticFinding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    # Source data
    static_analysis: Dict[str, Any] = field(default_factory=dict)
    runtime_analysis: Dict[str, Any] = field(default_factory=dict)
    trace_analysis: Dict[str, Any] = field(default_factory=dict)
    forensic_analysis: Dict[str, Any] = field(default_factory=dict)
    
    def add_finding(self, finding: DiagnosticFinding):
        """Add a finding to the report."""
        self.findings.append(finding)
    
    def get_findings_by_severity(self, severity: str) -> List[DiagnosticFinding]:
        """Get findings filtered by severity."""
        return [f for f in self.findings if f.severity == severity]
    
    def get_findings_by_category(self, category: str) -> List[DiagnosticFinding]:
        """Get findings filtered by category."""
        return [f for f in self.findings if f.category == category]
    
    def compute_summary(self):
        """Compute summary statistics."""
        self.summary = {
            "total_findings": len(self.findings),
            "by_severity": {},
            "by_category": {},
            "critical_count": 0,
            "has_critical": False,
        }
        
        for finding in self.findings:
            # Count by severity
            sev = finding.severity
            self.summary["by_severity"][sev] = self.summary["by_severity"].get(sev, 0) + 1
            
            # Count by category
            cat = finding.category
            self.summary["by_category"][cat] = self.summary["by_category"].get(cat, 0) + 1
        
        self.summary["critical_count"] = self.summary["by_severity"].get("critical", 0)
        self.summary["has_critical"] = self.summary["critical_count"] > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "title": self.title,
            "created_at": self.created_at,
            "target": self.target,
            "summary": self.summary,
            "findings": [
                {
                    "id": f.finding_id,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "location": f.location,
                    "evidence": f.evidence,
                    "suggestions": f.suggestions,
                    "confidence": f.confidence,
                }
                for f in self.findings
            ],
            "static_analysis": self.static_analysis,
            "runtime_analysis": self.runtime_analysis,
            "trace_analysis": self.trace_analysis,
            "forensic_analysis": self.forensic_analysis,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save(self, path: str):
        """Save report to file."""
        with open(path, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, path: str) -> "DiagnosticReport":
        """Load report from file."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        report = cls(
            report_id=data["report_id"],
            title=data["title"],
            created_at=data["created_at"],
            target=data["target"],
        )
        
        report.summary = data.get("summary", {})
        report.static_analysis = data.get("static_analysis", {})
        report.runtime_analysis = data.get("runtime_analysis", {})
        report.trace_analysis = data.get("trace_analysis", {})
        report.forensic_analysis = data.get("forensic_analysis", {})
        
        for f_data in data.get("findings", []):
            finding = DiagnosticFinding(
                finding_id=f_data["id"],
                category=f_data["category"],
                severity=f_data["severity"],
                title=f_data["title"],
                description=f_data["description"],
                location=f_data.get("location"),
                evidence=f_data.get("evidence", []),
                suggestions=f_data.get("suggestions", []),
                confidence=f_data.get("confidence", 1.0),
            )
            report.findings.append(finding)
        
        return report


class DiagnosticEngine:
    """
    Engine for running comprehensive diagnostics.
    
    Usage:
        engine = DiagnosticEngine()
        
        # Analyze a file
        report = engine.analyze_file("path/to/file.py")
        
        # Analyze a directory
        report = engine.analyze_directory("path/to/project")
        
        # Analyze with runtime monitoring
        report = engine.analyze_execution(my_function, args)
        
        # Print report
        print(report.to_markdown())
    """
    
    def __init__(self):
        from .code_tracer import CodeTracer
        from .bug_detector import BugDetector
        from .execution_monitor import ExecutionMonitor
        
        self.tracer = CodeTracer()
        self.detector = BugDetector()
        self.monitor_class = ExecutionMonitor
        
        self._report_counter = 0
    
    def analyze_file(self, file_path: str) -> DiagnosticReport:
        """Run static analysis on a single file."""
        self._report_counter += 1
        
        report = DiagnosticReport(
            report_id=self._generate_report_id(file_path),
            title=f"Diagnostic Report: {Path(file_path).name}",
            created_at=time.time(),
            target=file_path,
        )
        
        # Run static analysis
        issues = self.detector.scan_file(file_path)
        
        for issue in issues:
            finding = DiagnosticFinding(
                finding_id=issue.issue_id,
                category="static",
                severity=issue.severity,
                title=issue.pattern_name.replace("_", " ").title(),
                description=issue.message,
                location={
                    "file": issue.file_path,
                    "line": issue.line_number,
                    "column": issue.column,
                },
                evidence=[issue.code_snippet] if issue.code_snippet else [],
                suggestions=[issue.suggestion] if issue.suggestion else [],
                confidence=issue.confidence,
            )
            report.add_finding(finding)
        
        report.static_analysis = self.detector.get_summary()
        report.compute_summary()
        
        return report
    
    def analyze_directory(self, dir_path: str, recursive: bool = True) -> DiagnosticReport:
        """Run static analysis on a directory."""
        self._report_counter += 1
        
        report = DiagnosticReport(
            report_id=self._generate_report_id(dir_path),
            title=f"Diagnostic Report: {Path(dir_path).name}",
            created_at=time.time(),
            target=dir_path,
        )
        
        # Run static analysis
        issues = self.detector.scan_directory(dir_path, recursive)
        
        for issue in issues:
            finding = DiagnosticFinding(
                finding_id=issue.issue_id,
                category="static",
                severity=issue.severity,
                title=issue.pattern_name.replace("_", " ").title(),
                description=issue.message,
                location={
                    "file": issue.file_path,
                    "line": issue.line_number,
                    "column": issue.column,
                },
                evidence=[issue.code_snippet] if issue.code_snippet else [],
                suggestions=[issue.suggestion] if issue.suggestion else [],
                confidence=issue.confidence,
            )
            report.add_finding(finding)
        
        report.static_analysis = self.detector.get_summary()
        report.compute_summary()
        
        return report
    
    def analyze_execution(self, func, *args, **kwargs) -> DiagnosticReport:
        """Run diagnostics on function execution."""
        self._report_counter += 1
        
        func_name = getattr(func, '__name__', str(func))
        
        report = DiagnosticReport(
            report_id=self._generate_report_id(func_name),
            title=f"Execution Diagnostic: {func_name}",
            created_at=time.time(),
            target=func_name,
        )
        
        # Create a monitor for this execution
        monitor = self.monitor_class()
        
        result = None
        exception = None
        
        with monitor.monitoring():
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                exception = e
        
        # Convert anomalies to findings
        for anomaly in monitor.get_anomalies():
            finding = DiagnosticFinding(
                finding_id=f"anomaly_{anomaly.frame_id}_{anomaly.timestamp}",
                category="runtime",
                severity=anomaly.severity,
                title=anomaly.anomaly_type.replace("_", " ").title(),
                description=anomaly.description,
                location=anomaly.context,
                confidence=1.0,
            )
            report.add_finding(finding)
        
        # Add execution summary
        report.runtime_analysis = monitor.get_summary()
        report.runtime_analysis["hotspots"] = [
            {"function": f, "total_ms": t, "calls": c}
            for f, t, c in monitor.get_hotspots(10)
        ]
        
        if exception:
            report.runtime_analysis["exception"] = str(exception)
        
        report.compute_summary()
        
        return report
    
    def _generate_report_id(self, target: str) -> str:
        """Generate a unique report ID."""
        content = f"{target}:{time.time()}:{self._report_counter}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_markdown(self, report: DiagnosticReport) -> str:
        """Convert a report to Markdown format."""
        lines = [
            f"# {report.title}",
            "",
            f"**Report ID:** `{report.report_id}`",
            f"**Generated:** {datetime.fromtimestamp(report.created_at).isoformat()}",
            f"**Target:** `{report.target}`",
            "",
            "## Summary",
            "",
            f"- **Total Findings:** {report.summary.get('total_findings', 0)}",
        ]
        
        # Severity breakdown
        by_severity = report.summary.get("by_severity", {})
        if by_severity:
            lines.append("")
            lines.append("### By Severity")
            lines.append("")
            icons = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
            for sev in ["critical", "error", "warning", "info"]:
                count = by_severity.get(sev, 0)
                if count:
                    lines.append(f"- {icons.get(sev, '•')} **{sev.title()}:** {count}")
        
        # Findings
        if report.findings:
            lines.extend(["", "## Findings", ""])
            
            for finding in sorted(report.findings, 
                                  key=lambda f: ["critical", "error", "warning", "info"].index(f.severity)
                                  if f.severity in ["critical", "error", "warning", "info"] else 99):
                icon = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(finding.severity, "•")
                
                lines.append(f"### {icon} {finding.title}")
                lines.append("")
                lines.append(f"**Severity:** {finding.severity} | **Category:** {finding.category}")
                lines.append("")
                lines.append(finding.description)
                
                if finding.location:
                    loc = finding.location
                    if "file" in loc:
                        lines.append("")
                        lines.append(f"**Location:** `{loc.get('file', '')}:{loc.get('line', '')}`")
                
                if finding.evidence:
                    lines.append("")
                    lines.append("**Evidence:**")
                    for ev in finding.evidence:
                        lines.append(f"```")
                        lines.append(ev)
                        lines.append(f"```")
                
                if finding.suggestions:
                    lines.append("")
                    lines.append("**Suggestions:**")
                    for sug in finding.suggestions:
                        lines.append(f"- {sug}")
                
                lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def diagnose(target, **kwargs) -> DiagnosticReport:
    """
    Convenience function to run diagnostics.
    
    Usage:
        # Analyze a file
        report = diagnose("path/to/file.py")
        
        # Analyze a directory
        report = diagnose("path/to/project/")
        
        # Analyze a function
        report = diagnose(my_function, arg1, arg2)
    """
    engine = DiagnosticEngine()
    
    if callable(target):
        # It's a function
        return engine.analyze_execution(target, **kwargs)
    elif isinstance(target, str):
        path = Path(target)
        if path.is_file():
            return engine.analyze_file(target)
        elif path.is_dir():
            return engine.analyze_directory(target)
    
    raise ValueError(f"Cannot diagnose target: {target}")
