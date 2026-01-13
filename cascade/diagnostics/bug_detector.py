"""
CASCADE Bug Detector - Automatic bug detection using pattern matching.

Uses cascade-lattice's forensic capabilities:
- GhostLog for inferring missing execution (what *should* have run)
- Artifact patterns for detecting anomalies
- SymbioticAdapter for interpreting signals
"""

import time
import hashlib
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import ast
import re

from cascade.core.adapter import SymbioticAdapter
from cascade.forensics.artifacts import ArtifactDetector, TimestampArtifacts


@dataclass
class BugPattern:
    """A detectable bug pattern."""
    name: str
    description: str
    severity: str  # "critical", "error", "warning", "info"
    detector: Callable[[str, ast.AST], List[Dict[str, Any]]]
    category: str = "general"
    
    
@dataclass 
class DetectedIssue:
    """A detected code issue."""
    issue_id: str
    pattern_name: str
    severity: str
    file_path: str
    line_number: int
    column: int
    code_snippet: str
    message: str
    suggestion: Optional[str] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.issue_id,
            "pattern": self.pattern_name,
            "severity": self.severity,
            "location": {
                "file": self.file_path,
                "line": self.line_number,
                "column": self.column,
            },
            "snippet": self.code_snippet,
            "message": self.message,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }


class BugDetector:
    """
    Static analysis bug detector using AST patterns.
    
    Usage:
        detector = BugDetector()
        issues = detector.scan_file("path/to/file.py")
        issues = detector.scan_directory("path/to/project")
    """
    
    def __init__(self):
        self.patterns: List[BugPattern] = []
        self._detected_issues: List[DetectedIssue] = []
        self._scanned_files: Set[str] = set()
        
        # For signal interpretation
        self.adapter = SymbioticAdapter()
        
        # Register built-in patterns
        self._register_builtin_patterns()
    
    def _register_builtin_patterns(self):
        """Register built-in bug detection patterns."""
        patterns = [
            # Null checks
            BugPattern(
                name="potential_none_access",
                description="Accessing attribute on potentially None value",
                severity="warning",
                detector=self._detect_none_access,
                category="null_safety",
            ),
            
            # Exception handling
            BugPattern(
                name="bare_except",
                description="Bare except clause catches all exceptions",
                severity="warning",
                detector=self._detect_bare_except,
                category="exception_handling",
            ),
            BugPattern(
                name="empty_except",
                description="Empty except block silently swallows exceptions",
                severity="error",
                detector=self._detect_empty_except,
                category="exception_handling",
            ),
            
            # Resource management
            BugPattern(
                name="unclosed_resource",
                description="File/resource opened but not closed",
                severity="warning",
                detector=self._detect_unclosed_resource,
                category="resource_management",
            ),
            
            # Common mistakes
            BugPattern(
                name="mutable_default_arg",
                description="Mutable default argument in function",
                severity="warning",
                detector=self._detect_mutable_default,
                category="common_mistakes",
            ),
            BugPattern(
                name="comparison_to_none",
                description="Using == instead of 'is' for None comparison",
                severity="info",
                detector=self._detect_none_comparison,
                category="common_mistakes",
            ),
            BugPattern(
                name="unreachable_code",
                description="Code that can never be executed",
                severity="warning",
                detector=self._detect_unreachable_code,
                category="common_mistakes",
            ),
            
            # Security
            BugPattern(
                name="hardcoded_secret",
                description="Potential hardcoded secret or password",
                severity="error",
                detector=self._detect_hardcoded_secret,
                category="security",
            ),
            BugPattern(
                name="sql_injection_risk",
                description="Potential SQL injection vulnerability",
                severity="critical",
                detector=self._detect_sql_injection,
                category="security",
            ),
            
            # Performance
            BugPattern(
                name="loop_invariant",
                description="Computation inside loop that could be moved outside",
                severity="info",
                detector=self._detect_loop_invariant,
                category="performance",
            ),
        ]
        
        self.patterns.extend(patterns)
    
    def register_pattern(self, pattern: BugPattern):
        """Register a custom bug pattern."""
        self.patterns.append(pattern)
    
    def scan_file(self, file_path: str) -> List[DetectedIssue]:
        """Scan a Python file for bugs."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
        except Exception as e:
            return [DetectedIssue(
                issue_id=self._generate_id(file_path, 0, "read_error"),
                pattern_name="file_read_error",
                severity="error",
                file_path=file_path,
                line_number=0,
                column=0,
                code_snippet="",
                message=f"Could not read file: {e}",
            )]
        
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return [DetectedIssue(
                issue_id=self._generate_id(file_path, e.lineno or 0, "syntax_error"),
                pattern_name="syntax_error",
                severity="critical",
                file_path=file_path,
                line_number=e.lineno or 0,
                column=e.offset or 0,
                code_snippet=e.text or "",
                message=f"Syntax error: {e.msg}",
            )]
        
        # Run all patterns
        lines = source.splitlines()
        for pattern in self.patterns:
            try:
                matches = pattern.detector(source, tree)
                for match in matches:
                    line_num = match.get("line", 0)
                    snippet = lines[line_num - 1] if 0 < line_num <= len(lines) else ""
                    
                    issues.append(DetectedIssue(
                        issue_id=self._generate_id(file_path, line_num, pattern.name),
                        pattern_name=pattern.name,
                        severity=pattern.severity,
                        file_path=file_path,
                        line_number=line_num,
                        column=match.get("column", 0),
                        code_snippet=snippet.strip(),
                        message=match.get("message", pattern.description),
                        suggestion=match.get("suggestion"),
                        confidence=match.get("confidence", 1.0),
                    ))
            except Exception as e:
                print(f"[DIAG] Pattern {pattern.name} failed on {file_path}: {e}")
        
        self._scanned_files.add(file_path)
        self._detected_issues.extend(issues)
        
        return issues
    
    def scan_directory(self, dir_path: str, recursive: bool = True) -> List[DetectedIssue]:
        """Scan a directory for Python files and detect bugs."""
        path = Path(dir_path)
        issues = []
        
        pattern = "**/*.py" if recursive else "*.py"
        for py_file in path.glob(pattern):
            # Skip __pycache__
            if "__pycache__" in str(py_file):
                continue
            issues.extend(self.scan_file(str(py_file)))
        
        return issues
    
    def _generate_id(self, file_path: str, line: int, pattern: str) -> str:
        """Generate a unique issue ID."""
        content = f"{file_path}:{line}:{pattern}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    # =========================================================================
    # PATTERN DETECTORS
    # =========================================================================
    
    def _detect_none_access(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect potential None access."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def visit_Attribute(self, node):
                # Look for patterns like: x.y where x might be None
                # This is heuristic - check if there's no None check before
                if isinstance(node.value, ast.Name):
                    # Simple heuristic: flag if variable name suggests nullable
                    name = node.value.id
                    if any(word in name.lower() for word in ["result", "maybe", "optional", "response"]):
                        matches.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "message": f"'{name}' may be None - consider adding a null check",
                            "confidence": 0.6,
                        })
                self.generic_visit(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_bare_except(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect bare except clauses."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def visit_ExceptHandler(self, node):
                if node.type is None:
                    matches.append({
                        "line": node.lineno,
                        "column": node.col_offset,
                        "message": "Bare 'except:' catches all exceptions including KeyboardInterrupt",
                        "suggestion": "Use 'except Exception:' instead",
                    })
                self.generic_visit(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_empty_except(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect empty except blocks."""
        matches = []
        lines = source.splitlines()
        
        class Visitor(ast.NodeVisitor):
            def visit_ExceptHandler(self, node):
                # Check if body is just 'pass' or empty
                if len(node.body) == 1:
                    stmt = node.body[0]
                    if isinstance(stmt, ast.Pass):
                        # Check if there's a comment explaining the pass
                        line_idx = stmt.lineno - 1
                        if line_idx < len(lines):
                            line = lines[line_idx]
                            if '#' in line:
                                # Has a comment - don't flag as issue
                                self.generic_visit(node)
                                return
                        matches.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "message": "Empty except block silently ignores exception",
                            "suggestion": "At minimum, log the exception",
                        })
                self.generic_visit(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_unclosed_resource(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect files opened without context manager."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.in_with = False
            
            def visit_With(self, node):
                old = self.in_with
                self.in_with = True
                self.generic_visit(node)
                self.in_with = old
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    if not self.in_with:
                        matches.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "message": "File opened without 'with' context manager",
                            "suggestion": "Use 'with open(...) as f:' to ensure file is closed",
                        })
                self.generic_visit(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_mutable_default(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect mutable default arguments."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        matches.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "message": f"Mutable default argument in function '{node.name}'",
                            "suggestion": "Use None as default and create mutable object inside function",
                        })
                        break
                self.generic_visit(node)
            
            def visit_AsyncFunctionDef(self, node):
                self.visit_FunctionDef(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_none_comparison(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect == None instead of 'is None'."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def visit_Compare(self, node):
                for i, (op, comparator) in enumerate(zip(node.ops, node.comparators)):
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        if isinstance(comparator, ast.Constant) and comparator.value is None:
                            matches.append({
                                "line": node.lineno,
                                "column": node.col_offset,
                                "message": "Use 'is None' instead of '== None'",
                                "suggestion": "Replace with 'is None' or 'is not None'",
                            })
                self.generic_visit(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_unreachable_code(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect code after return/raise/break/continue."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def check_body(self, body):
                for i, stmt in enumerate(body):
                    if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                        # Check if there's code after this
                        if i + 1 < len(body):
                            next_stmt = body[i + 1]
                            matches.append({
                                "line": next_stmt.lineno,
                                "column": next_stmt.col_offset,
                                "message": "Unreachable code after return/raise/break/continue",
                            })
                    self.visit(stmt)
            
            def visit_FunctionDef(self, node):
                self.check_body(node.body)
            
            def visit_AsyncFunctionDef(self, node):
                self.check_body(node.body)
            
            def visit_If(self, node):
                self.check_body(node.body)
                self.check_body(node.orelse)
            
            def visit_For(self, node):
                self.check_body(node.body)
            
            def visit_While(self, node):
                self.check_body(node.body)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_hardcoded_secret(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect potential hardcoded secrets."""
        matches = []
        
        # Pattern for secret-like variable names
        secret_patterns = re.compile(
            r'\b(password|passwd|pwd|secret|api_key|apikey|token|auth|credential)\s*=\s*["\'][^"\']+["\']',
            re.IGNORECASE
        )
        
        for i, line in enumerate(source.splitlines(), 1):
            if secret_patterns.search(line):
                matches.append({
                    "line": i,
                    "column": 0,
                    "message": "Potential hardcoded secret detected",
                    "suggestion": "Use environment variables or a secrets manager",
                })
        
        return matches
    
    def _detect_sql_injection(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect potential SQL injection vulnerabilities."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def visit_Call(self, node):
                # Look for .execute() calls with string formatting
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
                    for arg in node.args:
                        if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
                            matches.append({
                                "line": node.lineno,
                                "column": node.col_offset,
                                "message": "Potential SQL injection - using string formatting in query",
                                "suggestion": "Use parameterized queries instead",
                            })
                        elif isinstance(arg, ast.JoinedStr):  # f-string
                            matches.append({
                                "line": node.lineno,
                                "column": node.col_offset,
                                "message": "Potential SQL injection - using f-string in query",
                                "suggestion": "Use parameterized queries instead",
                            })
                self.generic_visit(node)
        
        Visitor().visit(tree)
        return matches
    
    def _detect_loop_invariant(self, source: str, tree: ast.AST) -> List[Dict]:
        """Detect computations that could be moved outside loops."""
        matches = []
        
        class Visitor(ast.NodeVisitor):
            def visit_For(self, node):
                # Get loop variable name
                if isinstance(node.target, ast.Name):
                    loop_var = node.target.id
                    
                    # Look for calls that don't use the loop variable
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    # Check if value doesn't depend on loop var
                                    value_vars = self._get_names(stmt.value)
                                    if loop_var not in value_vars and self._is_expensive(stmt.value):
                                        matches.append({
                                            "line": stmt.lineno,
                                            "column": stmt.col_offset,
                                            "message": "Computation inside loop may be loop-invariant",
                                            "suggestion": "Consider moving this outside the loop",
                                            "confidence": 0.5,
                                        })
                self.generic_visit(node)
            
            def _get_names(self, node) -> Set[str]:
                names = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Name):
                        names.add(child.id)
                return names
            
            def _is_expensive(self, node) -> bool:
                # Heuristic: calls are potentially expensive
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        return True
                return False
        
        Visitor().visit(tree)
        return matches
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get detection summary."""
        by_severity = {}
        by_category = {}
        
        for issue in self._detected_issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
            
            pattern = next((p for p in self.patterns if p.name == issue.pattern_name), None)
            if pattern:
                by_category[pattern.category] = by_category.get(pattern.category, 0) + 1
        
        return {
            "files_scanned": len(self._scanned_files),
            "total_issues": len(self._detected_issues),
            "by_severity": by_severity,
            "by_category": by_category,
        }
    
    def get_report(self) -> str:
        """Generate a human-readable report."""
        lines = [
            "BUG DETECTION REPORT",
            "=" * 60,
            f"Files scanned: {len(self._scanned_files)}",
            f"Issues found: {len(self._detected_issues)}",
            "",
        ]
        
        # Group by severity
        by_severity: Dict[str, List[DetectedIssue]] = {}
        for issue in self._detected_issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)
        
        severity_order = ["critical", "error", "warning", "info"]
        severity_icons = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
        
        for severity in severity_order:
            if severity in by_severity:
                issues = by_severity[severity]
                icon = severity_icons.get(severity, "•")
                lines.append(f"\n{icon} {severity.upper()} ({len(issues)})")
                lines.append("-" * 40)
                
                for issue in issues:
                    lines.append(f"  {issue.file_path}:{issue.line_number}")
                    lines.append(f"    {issue.message}")
                    if issue.suggestion:
                        lines.append(f"    💡 {issue.suggestion}")
                    lines.append("")
        
        return "\n".join(lines)
