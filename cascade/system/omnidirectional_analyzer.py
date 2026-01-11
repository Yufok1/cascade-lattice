"""
CASCADE Omnidirectional Analyzer
The complete circuit: Repo ↔ Dataset ↔ Logs ↔ Architecture ↔ Verification
"""

import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import json

from .repo_ingester import ingest_repository
from .universal_extractor import extract_from_files
from cascade.forensics import DataForensics
from cascade.logging import get_log_manager, log


class OmnidirectionalAnalyzer:
    """
    Complete system for omni-directional engineering analysis
    Connects repositories to their operational evidence
    """
    
    def __init__(self):
        self.logger = get_log_manager()
        self.repo_data = None
        self.runtime_data = None
        self.analysis_results = {}
    
    def analyze_complete_system(self, 
                               repo_source: str,
                               runtime_logs: Optional[List[str]] = None,
                               runtime_datasets: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Complete omni-directional analysis
        
        Args:
            repo_source: Repository path/URL or uploaded files
            runtime_logs: Actual runtime logs
            runtime_datasets: Runtime datasets/files
            
        Returns:
            Complete analysis results
        """
        log("OmnidirectionalAnalyzer", "Starting complete system analysis",
            context=f"Repo: {repo_source}",
            impact="HIGH")
        
        # Step 1: Ingest repository
        self.repo_data, repo_summary = self._ingest_repository(repo_source)
        
        # Step 2: Process runtime evidence
        self.runtime_data, runtime_summary = self._process_runtime_evidence(
            runtime_logs, runtime_datasets
        )
        
        # Step 3: Generate expected patterns from repo
        expected_patterns = self._generate_expected_patterns()
        
        # Step 4: Extract actual patterns from runtime
        actual_patterns = self._extract_actual_patterns()
        
        # Step 5: Compare and find convergence/divergence
        comparison = self._compare_patterns(expected_patterns, actual_patterns)
        
        # Step 6: Generate insights
        insights = self._generate_insights(comparison)
        
        results = {
            "repository": {
                "data": self.repo_data,
                "summary": repo_summary
            },
            "runtime": {
                "data": self.runtime_data,
                "summary": runtime_summary
            },
            "expected_patterns": expected_patterns,
            "actual_patterns": actual_patterns,
            "comparison": comparison,
            "insights": insights,
            "timestamp": datetime.now().isoformat()
        }
        
        self.analysis_results = results
        return results
    
    def _ingest_repository(self, repo_source: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Ingest repository into analyzable format"""
        log("RepoIngest", "Ingesting repository",
            context=f"Source: {repo_source}",
            impact="MEDIUM")
        
        # Handle different input types
        if isinstance(repo_source, str) and repo_source.startswith(("http://", "https://", "git@")):
            # Remote repository
            df, summary = ingest_repository(repo_source, include_history=True)
        elif isinstance(repo_source, list):
            # Uploaded files
            df, summary = extract_from_files(repo_source)
            summary["source_type"] = "uploaded_files"
        else:
            # Local path
            df, summary = ingest_repository(repo_source, include_history=True)
        
        log("RepoIngest", "Repository ingested successfully",
            context=f"Files: {summary.get('total_files', 0)}, Lines: {summary.get('total_lines', 0)}",
            impact="LOW")
        
        return df, summary
    
    def _process_runtime_evidence(self, 
                                 logs: Optional[List[str]], 
                                 datasets: Optional[List[Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Process runtime logs and datasets"""
        log("RuntimeProcessor", "Processing runtime evidence",
            context=f"Logs: {len(logs or [])}, Datasets: {len(datasets or [])}",
            impact="MEDIUM")
        
        all_data = []
        summary = {"sources": []}
        
        # Process logs
        if logs:
            log_records = []
            for i, log_line in enumerate(logs):
                log_records.append({
                    "content": log_line,
                    "source_type": "runtime_log",
                    "source_file": f"log_{i}",
                    "line_number": i
                })
            all_data.extend(log_records)
            summary["sources"].append({"type": "logs", "count": len(logs)})
        
        # Process datasets
        if datasets:
            for dataset in datasets:
                # Use universal extractor
                df, ds_summary = extract_from_files(dataset)
                if df is not None:
                    df["source_type"] = "runtime_dataset"
                    all_data.append(df)
                    summary["sources"].append({"type": "dataset", "records": len(df)})
        
        # Combine all runtime data
        if all_data:
            runtime_df = pd.concat(all_data, ignore_index=True)
            summary["total_records"] = len(runtime_df)
        else:
            runtime_df = pd.DataFrame()
            summary["total_records"] = 0
        
        return runtime_df, summary
    
    def _generate_expected_patterns(self) -> Dict[str, Any]:
        """Generate expected operational patterns from repository"""
        log("PatternGenerator", "Generating expected patterns from repository",
            impact="MEDIUM")
        
        patterns = {
            "expected_functions": [],
            "expected_configs": [],
            "expected_dependencies": [],
            "expected_operations": [],
            "architecture_indicators": {}
        }
        
        if self.repo_data is not None:
            # Extract function names (expected operations)
            if 'functions' in self.repo_data.columns:
                all_functions = []
                for func_list in self.repo_data['functions'].dropna():
                    if isinstance(func_list, str):
                        try:
                            funcs = json.loads(func_list)
                            all_functions.extend([f['name'] for f in funcs])
                        except:
                            pass
                patterns["expected_functions"] = list(set(all_functions))
            
            # Find configuration files
            config_files = self.repo_data[self.repo_data['file_type'] == 'config']
            patterns["expected_configs"] = config_files['file_path'].tolist()
            
            # Extract dependencies
            if 'imports' in self.repo_data.columns:
                all_imports = []
                for import_list in self.repo_data['imports'].dropna():
                    if isinstance(import_list, str):
                        try:
                            imports = json.loads(import_list)
                            all_imports.extend(imports)
                        except:
                            pass
                patterns["expected_dependencies"] = list(set(all_imports))
            
            # Architecture indicators
            patterns["architecture_indicators"] = {
                "has_tests": "test" in self.repo_data['file_type'].values,
                "has_ci_cd": "cicd" in self.repo_data['file_type'].values,
                "main_language": self.repo_data['language'].mode().iloc[0] if not self.repo_data.empty else "unknown",
                "complexity_score": self.repo_data['complexity'].sum() if 'complexity' in self.repo_data.columns else 0
            }
        
        return patterns
    
    def _extract_actual_patterns(self) -> Dict[str, Any]:
        """Extract actual patterns from runtime evidence"""
        log("PatternExtractor", "Extracting actual patterns from runtime",
            impact="MEDIUM")
        
        patterns = {
            "actual_operations": [],
            "actual_errors": [],
            "actual_dependencies": [],
            "system_calls": [],
            "data_flows": []
        }
        
        if self.runtime_data is not None and not self.runtime_data.empty:
            # Run forensics on runtime data
            forensics = DataForensics()
            report = forensics.analyze(self.runtime_data)
            
            # Extract operations from ghost log
            patterns["actual_operations"] = [
                op.operation for op in report.ghost_log.operations
            ]
            
            # Extract security concerns as errors
            patterns["actual_errors"] = [
                concern['issue'] for concern in report.security_concerns
            ]
            
            # Extract tech fingerprints as dependencies
            patterns["actual_dependencies"] = [
                fp.technology for fp in report.fingerprints
            ]
        
        return patterns
    
    def _compare_patterns(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
        """Compare expected vs actual patterns"""
        log("PatternComparator", "Comparing expected vs actual patterns",
            impact="HIGH")
        
        comparison = {
            "convergence": {},
            "divergence": {},
            "coverage_metrics": {},
            "anomalies": []
        }
        
        # Function coverage
        expected_funcs = set(expected.get("expected_functions", []))
        actual_funcs = set(actual.get("actual_operations", []))
        
        comparison["convergence"]["functions"] = list(expected_funcs & actual_funcs)
        comparison["divergence"]["missing_functions"] = list(expected_funcs - actual_funcs)
        comparison["divergence"]["unexpected_functions"] = list(actual_funcs - expected_funcs)
        
        # Dependency analysis
        expected_deps = set(expected.get("expected_dependencies", []))
        actual_deps = set(actual.get("actual_dependencies", []))
        
        comparison["convergence"]["dependencies"] = list(expected_deps & actual_deps)
        comparison["divergence"]["missing_dependencies"] = list(expected_deps - actual_deps)
        comparison["divergence"]["unexpected_dependencies"] = list(actual_deps - expected_deps)
        
        # Coverage metrics
        comparison["coverage_metrics"] = {
            "function_coverage": len(comparison["convergence"]["functions"]) / max(len(expected_funcs), 1),
            "dependency_coverage": len(comparison["convergence"]["dependencies"]) / max(len(expected_deps), 1),
            "implementation_fidelity": self._calculate_fidelity(expected, actual)
        }
        
        # Detect anomalies
        comparison["anomalies"] = self._detect_anomalies(expected, actual)
        
        return comparison
    
    def _calculate_fidelity(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> float:
        """Calculate implementation fidelity score"""
        # Simple heuristic based on convergence
        total_expected = len(expected.get("expected_functions", [])) + len(expected.get("expected_dependencies", []))
        total_converged = len(self._compare_patterns(expected, actual)["convergence"].get("functions", [])) + \
                         len(self._compare_patterns(expected, actual)["convergence"].get("dependencies", []))
        
        return total_converged / max(total_expected, 1)
    
    def _detect_anomalies(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect system anomalies"""
        anomalies = []
        
        # Check for unexpected operations
        unexpected_ops = set(actual.get("actual_operations", [])) - set(expected.get("expected_functions", []))
        if unexpected_ops:
            anomalies.append({
                "type": "unexpected_operations",
                "description": f"Found {len(unexpected_ops)} operations not in repository",
                "items": list(unexpected_ops)[:5]
            })
        
        # Check for errors
        if actual.get("actual_errors"):
            anomalies.append({
                "type": "runtime_errors",
                "description": f"Found {len(actual['actual_errors'])} errors in runtime",
                "items": actual["actual_errors"][:3]
            })
        
        return anomalies
    
    def _generate_insights(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Generate actionable insights from comparison"""
        insights = {
            "overall_score": 0.0,
            "recommendations": [],
            "risk_assessment": {},
            "architecture_validation": {}
        }
        
        # Calculate overall score
        coverage = comparison["coverage_metrics"]
        insights["overall_score"] = (
            coverage.get("function_coverage", 0) * 0.4 +
            coverage.get("dependency_coverage", 0) * 0.3 +
            coverage.get("implementation_fidelity", 0) * 0.3
        )
        
        # Generate recommendations
        if coverage["function_coverage"] < 0.8:
            insights["recommendations"].append(
                "Consider implementing missing functions for better coverage"
            )
        
        if comparison["divergence"]["unexpected_dependencies"]:
            insights["recommendations"].append(
                "Review unexpected dependencies - may indicate hidden requirements"
            )
        
        # Risk assessment
        insights["risk_assessment"] = {
            "complexity_risk": "high" if coverage["implementation_fidelity"] < 0.5 else "low",
            "maintenance_risk": "medium" if len(comparison["divergence"]["missing_functions"]) > 5 else "low",
            "security_risk": "high" if any(a["type"] == "runtime_errors" for a in comparison["anomalies"]) else "low"
        }
        
        return insights
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        if not self.analysis_results:
            return "No analysis results available. Run analyze_complete_system() first."
        
        results = self.analysis_results
        
        report = f"""
# Omnidirectional Engineering Analysis Report
Generated: {results['timestamp']}

## Executive Summary
- Overall Implementation Fidelity: {results['insights']['overall_score']:.1%}
- Repository Files Analyzed: {results['repository']['summary'].get('total_files', 0)}
- Runtime Evidence Records: {results['runtime']['summary'].get('total_records', 0)}

## Convergence Analysis ✅
### Matching Elements
- Functions: {len(results['comparison']['convergence']['functions'])}
- Dependencies: {len(results['comparison']['convergence']['dependencies'])}

## Divergence Analysis ⚠️
### Missing from Runtime
- Functions: {len(results['comparison']['divergence']['missing_functions'])}
- Dependencies: {len(results['comparison']['divergence']['missing_dependencies'])}

### Unexpected in Runtime
- Operations: {len(results['comparison']['divergence']['unexpected_functions'])}
- Dependencies: {len(results['comparison']['divergence']['unexpected_dependencies'])}

## Risk Assessment
- Complexity Risk: {results['insights']['risk_assessment']['complexity_risk'].upper()}
- Maintenance Risk: {results['insights']['risk_assessment']['maintenance_risk'].upper()}
- Security Risk: {results['insights']['risk_assessment']['security_risk'].upper()}

## Recommendations
{chr(10).join(f"- {r}" for r in results['insights']['recommendations'])}

## Anomalies Detected
{chr(10).join(f"- {a['type']}: {a['description']}" for a in results['comparison']['anomalies'])}

---
*This analysis proves the connection between repository intent and runtime reality.*
"""
        
        return report


def analyze_omnidirectional(repo_source: str, 
                           runtime_logs: Optional[List[str]] = None,
                           runtime_datasets: Optional[List[Any]] = None) -> Dict[str, Any]:
    """
    Convenience function for complete omni-directional analysis
    """
    analyzer = OmnidirectionalAnalyzer()
    return analyzer.analyze_complete_system(repo_source, runtime_logs, runtime_datasets)
