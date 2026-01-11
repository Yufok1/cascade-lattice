"""
CASCADE Forensics - Main Analyzer

The data remembers. This module reads those memories.

Generates:
- GHOST LOG: Inferred sequence of operations
- SKELETON: Probable system architecture
- DNA: Technology fingerprints
- SOUL: Behavioral predictions
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import OrderedDict

from cascade.forensics.artifacts import (
    Artifact, ArtifactDetector,
    TimestampArtifacts, IDPatternArtifacts, TextArtifacts,
    NumericArtifacts, NullPatternArtifacts, SchemaArtifacts,
)
from cascade.forensics.fingerprints import TechFingerprinter, Fingerprint


@dataclass
class InferredOperation:
    """A single inferred operation from the ghost log."""
    sequence: int
    operation: str
    description: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.sequence,
            "op": self.operation,
            "desc": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class GhostLog:
    """
    Inferred processing history - the ghost of the system.
    
    This is a reconstruction of what PROBABLY happened
    based on artifacts left in the data.
    """
    operations: List[InferredOperation] = field(default_factory=list)
    
    # Provenance
    analysis_timestamp: float = field(default_factory=time.time)
    data_hash: str = ""
    ghost_hash: str = ""
    
    def add_operation(self, op: str, desc: str, confidence: float, evidence: List[str] = None):
        """Add an inferred operation to the ghost log."""
        self.operations.append(InferredOperation(
            sequence=len(self.operations) + 1,
            operation=op,
            description=desc,
            confidence=confidence,
            evidence=evidence or [],
        ))
    
    def finalize(self) -> str:
        """Compute hash of the ghost log for provenance."""
        content = json.dumps([op.to_dict() for op in self.operations], sort_keys=True)
        self.ghost_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return self.ghost_hash
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "operations": [op.to_dict() for op in self.operations],
            "analysis_timestamp": self.analysis_timestamp,
            "data_hash": self.data_hash,
            "ghost_hash": self.ghost_hash,
        }
    
    def to_narrative(self) -> str:
        """Generate human-readable narrative of inferred processing."""
        if not self.operations:
            return "No processing artifacts detected."
        
        lines = ["## Ghost Log - Inferred Processing History\n"]
        lines.append("*Based on artifacts left in the data, this is what probably happened:*\n")
        
        for op in self.operations:
            conf_str = "●" * int(op.confidence * 5) + "○" * (5 - int(op.confidence * 5))
            lines.append(f"**{op.sequence}. {op.operation}** [{conf_str}]")
            lines.append(f"   {op.description}")
            if op.evidence:
                lines.append(f"   *Evidence: {', '.join(op.evidence[:3])}*")
            lines.append("")
        
        return "\n".join(lines)


@dataclass
class ForensicsReport:
    """Complete forensics analysis report."""
    
    # Artifacts detected
    artifacts: List[Artifact] = field(default_factory=list)
    
    # Inferred processing
    ghost_log: GhostLog = field(default_factory=GhostLog)
    
    # Technology fingerprints
    fingerprints: List[Fingerprint] = field(default_factory=list)
    
    # Synthesized architecture
    likely_stack: Dict[str, Any] = field(default_factory=dict)
    
    # Security concerns
    security_concerns: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    analysis_timestamp: float = field(default_factory=time.time)
    row_count: int = 0
    column_count: int = 0
    data_hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifacts": [a.to_dict() for a in self.artifacts],
            "ghost_log": self.ghost_log.to_dict(),
            "fingerprints": [f.to_dict() for f in self.fingerprints],
            "likely_stack": self.likely_stack,
            "security_concerns": self.security_concerns,
            "metadata": {
                "timestamp": self.analysis_timestamp,
                "rows": self.row_count,
                "columns": self.column_count,
                "data_hash": self.data_hash,
            }
        }
    
    def summary(self) -> Dict[str, Any]:
        """Generate summary for display."""
        return {
            "artifacts_found": len(self.artifacts),
            "operations_inferred": len(self.ghost_log.operations),
            "technologies_identified": len(self.fingerprints),
            "security_concerns": len(self.security_concerns),
            "top_fingerprints": [f.technology for f in self.fingerprints[:5]],
            "data_hash": self.data_hash,
            "ghost_hash": self.ghost_log.ghost_hash,
        }


class DataForensics:
    """
    Main forensics analyzer.
    
    Usage:
        forensics = DataForensics()
        report = forensics.analyze(df)
        
        print(report.ghost_log.to_narrative())
        print(report.likely_stack)
    """
    
    def __init__(self):
        self.detectors = [
            TimestampArtifacts(),
            IDPatternArtifacts(),
            TextArtifacts(),
            NumericArtifacts(),
            NullPatternArtifacts(),
            SchemaArtifacts(),
        ]
        self.fingerprinter = TechFingerprinter()
    
    def analyze(self, df) -> ForensicsReport:
        """
        Analyze a dataframe for processing artifacts.
        
        Args:
            df: Pandas DataFrame to analyze
            
        Returns:
            ForensicsReport with all findings
        """
        report = ForensicsReport()
        report.row_count = len(df)
        report.column_count = len(df.columns)
        
        # Compute data hash
        try:
            # Sample hash for large datasets
            if len(df) > 10000:
                sample = df.sample(10000, random_state=42)
            else:
                sample = df
            content = sample.to_json()
            report.data_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        except:
            report.data_hash = "unknown"
        
        # Run all detectors
        all_artifacts = []
        
        for detector in self.detectors:
            try:
                # Some detectors analyze all columns at once
                if hasattr(detector, 'detect_all'):
                    artifacts = detector.detect_all(df)
                    all_artifacts.extend(artifacts)
                
                # Column-by-column analysis
                for col in df.columns:
                    artifacts = detector.detect(df, col)
                    all_artifacts.extend(artifacts)
            except Exception as e:
                # Don't let one detector crash the whole analysis
                pass
        
        report.artifacts = all_artifacts
        
        # Build ghost log from artifacts
        report.ghost_log = self._build_ghost_log(all_artifacts, df)
        report.ghost_log.data_hash = report.data_hash
        report.ghost_log.finalize()
        
        # Generate technology fingerprints
        report.fingerprints = self.fingerprinter.analyze(all_artifacts)
        report.likely_stack = self.fingerprinter.get_likely_stack()
        report.security_concerns = self.fingerprinter.get_security_concerns()
        
        return report
    
    def _build_ghost_log(self, artifacts: List[Artifact], df) -> GhostLog:
        """
        Build inferred processing history from artifacts.
        
        This is where we reconstruct the sequence of operations
        that probably created this data.
        """
        ghost = GhostLog()
        
        # Group artifacts by type for logical ordering
        by_type = {}
        for a in artifacts:
            if a.artifact_type not in by_type:
                by_type[a.artifact_type] = []
            by_type[a.artifact_type].append(a)
        
        # Infer operations in logical order
        
        # 1. Data sourcing (schema artifacts come first)
        if "framework_fingerprint" in by_type:
            for a in by_type["framework_fingerprint"]:
                ghost.add_operation(
                    "DATA_SOURCE",
                    f"Data originated from {a.details.get('framework', 'database')}: {a.evidence}",
                    a.confidence,
                    [a.evidence]
                )
        
        if "naming_convention" in by_type:
            for a in by_type["naming_convention"]:
                ghost.add_operation(
                    "SCHEMA_ORIGIN",
                    f"Schema follows {a.details.get('convention', 'unknown')} convention",
                    a.confidence,
                    [a.evidence]
                )
        
        # 2. Merging (if multiple sources detected)
        if "mixed_conventions" in by_type or "id_prefix" in by_type:
            ghost.add_operation(
                "DATA_MERGE",
                "Multiple data sources were merged together",
                0.75,
                [a.evidence for a in by_type.get("mixed_conventions", []) + by_type.get("id_prefix", [])]
            )
        
        # 3. ID generation
        if "uuid_version" in by_type:
            for a in by_type["uuid_version"]:
                ghost.add_operation(
                    "ID_GENERATION",
                    f"IDs generated using {a.details.get('meaning', 'UUID')}",
                    a.confidence,
                    [a.evidence]
                )
        
        if "hash_id" in by_type:
            for a in by_type["hash_id"]:
                ghost.add_operation(
                    "ID_GENERATION",
                    f"IDs are {a.details.get('probable_algorithm', 'hash')}-based (content-addressed)",
                    a.confidence,
                    [a.evidence]
                )
        
        # 4. Processing / Transformation
        if "case_normalization" in by_type:
            for a in by_type["case_normalization"]:
                ghost.add_operation(
                    "TEXT_NORMALIZATION",
                    f"Text converted to {a.details.get('case', 'normalized')} case",
                    a.confidence,
                    [a.evidence]
                )
        
        if "whitespace_trimming" in by_type:
            ghost.add_operation(
                "TEXT_CLEANING",
                "Whitespace trimmed from text fields",
                0.70,
                [a.evidence for a in by_type["whitespace_trimming"]]
            )
        
        if "truncation" in by_type:
            for a in by_type["truncation"]:
                ghost.add_operation(
                    "FIELD_TRUNCATION",
                    f"Text truncated at {a.details.get('max_length', '?')} characters",
                    a.confidence,
                    [a.evidence]
                )
        
        if "numeric_rounding" in by_type:
            for a in by_type["numeric_rounding"]:
                ghost.add_operation(
                    "NUMERIC_ROUNDING",
                    f"Numbers rounded: {a.evidence}",
                    a.confidence,
                    [a.evidence]
                )
        
        # 5. Filtering / Deletion
        if "sequential_id_gaps" in by_type:
            for a in by_type["sequential_id_gaps"]:
                gap_ratio = a.details.get('gap_ratio', 0)
                ghost.add_operation(
                    "RECORD_FILTERING",
                    f"~{gap_ratio*100:.0f}% of records were filtered or deleted",
                    a.confidence,
                    [a.evidence]
                )
        
        if "hard_cutoff" in by_type:
            for a in by_type["hard_cutoff"]:
                ghost.add_operation(
                    "VALUE_CAPPING",
                    f"Values capped at {a.details.get('cutoff', '?')}",
                    a.confidence,
                    [a.evidence]
                )
        
        # 6. Batch processing patterns
        if "timestamp_rounding" in by_type:
            for a in by_type["timestamp_rounding"]:
                ghost.add_operation(
                    "BATCH_PROCESSING",
                    f"Data processed in batches: {a.evidence}",
                    a.confidence,
                    [a.evidence]
                )
        
        if "regular_intervals" in by_type:
            for a in by_type["regular_intervals"]:
                ghost.add_operation(
                    "SCHEDULED_JOB",
                    f"Regular processing schedule detected: {a.details.get('interval_desc', 'unknown')}",
                    a.confidence,
                    [a.evidence]
                )
        
        if "temporal_clustering" in by_type:
            ghost.add_operation(
                "BURST_PROCESSING",
                "Event-driven or burst batch processing detected",
                0.75,
                [a.evidence for a in by_type["temporal_clustering"]]
            )
        
        # 7. Data quality issues
        if "encoding_artifact" in by_type:
            for a in by_type["encoding_artifact"]:
                ghost.add_operation(
                    "ENCODING_ERROR",
                    f"Character encoding conversion failed: {a.evidence}",
                    a.confidence,
                    [a.evidence]
                )
        
        if "sentinel_value" in by_type:
            for a in by_type["sentinel_value"]:
                ghost.add_operation(
                    "NULL_HANDLING",
                    f"NULLs represented as sentinel value {a.details.get('sentinel', '?')}",
                    a.confidence,
                    [a.evidence]
                )
        
        if "high_null_rate" in by_type:
            for a in by_type["high_null_rate"]:
                ghost.add_operation(
                    "OPTIONAL_FIELD",
                    f"Column {a.column} is optional or had ETL issues ({a.details.get('null_rate', 0)*100:.0f}% null)",
                    a.confidence,
                    [a.evidence]
                )
        
        # 8. Export (often the last step)
        if any("PANDAS" in a.inferred_operation for a in artifacts):
            ghost.add_operation(
                "DATA_EXPORT",
                "Data exported via Pandas to CSV",
                0.90,
                ["Unnamed column artifact"]
            )
        
        return ghost
    
    def analyze_file(self, filepath: str) -> ForensicsReport:
        """
        Analyze a data file.
        
        Supports: CSV, JSON, JSONL, Parquet, Excel
        """
        import pandas as pd
        from pathlib import Path
        
        path = Path(filepath)
        suffix = path.suffix.lower()
        
        if suffix == '.csv':
            df = pd.read_csv(filepath)
        elif suffix == '.json':
            df = pd.read_json(filepath)
        elif suffix == '.jsonl':
            df = pd.read_json(filepath, lines=True)
        elif suffix == '.parquet':
            df = pd.read_parquet(filepath)
        elif suffix in ['.xlsx', '.xls']:
            df = pd.read_excel(filepath)
        else:
            # Try CSV as default
            df = pd.read_csv(filepath)
        
        return self.analyze(df)


def analyze_dataframe(df) -> ForensicsReport:
    """Convenience function to analyze a dataframe."""
    forensics = DataForensics()
    return forensics.analyze(df)


def analyze_file(filepath: str) -> ForensicsReport:
    """Convenience function to analyze a file."""
    forensics = DataForensics()
    return forensics.analyze_file(filepath)
