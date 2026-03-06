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
    analysis_mode: str = "dataset"
    
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
                "analysis_mode": self.analysis_mode,
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
            "analysis_mode": self.analysis_mode,
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
    
    def analyze(self, df, mode: str = "auto") -> ForensicsReport:
        """
        Analyze a dataframe for processing artifacts.
        
        Args:
            df: Pandas DataFrame to analyze
            mode: "dataset", "anomaly", or "auto"
             
        Returns:
            ForensicsReport with all findings
        """
        report = ForensicsReport()
        report.row_count = len(df)
        report.column_count = len(df.columns)
        report.data_hash = self._compute_data_hash(df)
        report.analysis_mode = self._resolve_mode(df, mode)

        if report.analysis_mode == "anomaly":
            return self._analyze_anomaly_frame(df, report)

        return self._analyze_dataset_frame(df, report)

    def _compute_data_hash(self, df) -> str:
        try:
            if len(df) > 10000:
                sample = df.sample(10000, random_state=42)
            else:
                sample = df
            content = sample.to_json()
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        except Exception:
            return "unknown"

    def _resolve_mode(self, df, mode: str) -> str:
        requested = str(mode or "auto").strip().lower()
        if requested not in ("auto", "dataset", "anomaly"):
            raise ValueError("mode must be one of: auto, dataset, anomaly")
        if requested != "auto":
            return requested
        row_count = len(df)
        if row_count <= 1:
            return "anomaly"
        if row_count <= 3:
            for record in df.to_dict(orient="records"):
                if self._record_looks_anomalous(record):
                    return "anomaly"
        return "dataset"

    def _record_looks_anomalous(self, record: Dict[str, Any]) -> bool:
        for key, value in (record or {}).items():
            key_lower = str(key).lower()
            if isinstance(value, (dict, list)):
                return True
            if any(hint in key_lower for hint in (
                "error", "exception", "trace", "session", "request",
                "receipt", "status", "retry", "timeout", "route", "tool",
                "component", "context"
            )):
                return True
            if isinstance(value, str):
                text = value.strip()
                if not text:
                    continue
                if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
                    return True
                lowered = text.lower()
                if any(tok in lowered for tok in ("error", "exception", "timeout", "traceback", "failed")):
                    return True
        return False

    def _analyze_dataset_frame(self, df, report: ForensicsReport) -> ForensicsReport:
        all_artifacts = []

        for detector in self.detectors:
            try:
                if hasattr(detector, 'detect_all'):
                    artifacts = detector.detect_all(df)
                    all_artifacts.extend(artifacts)

                for col in df.columns:
                    artifacts = detector.detect(df, col)
                    all_artifacts.extend(artifacts)
            except Exception:
                pass

        report.artifacts = all_artifacts
        report.ghost_log = self._build_ghost_log(all_artifacts, df)
        report.ghost_log.data_hash = report.data_hash
        report.ghost_log.finalize()
        report.fingerprints = self.fingerprinter.analyze(all_artifacts)
        report.likely_stack = self.fingerprinter.get_likely_stack()
        report.security_concerns = self.fingerprinter.get_security_concerns()
        return report

    def _analyze_anomaly_frame(self, df, report: ForensicsReport) -> ForensicsReport:
        records = self._normalize_anomaly_records(df)
        all_artifacts: List[Artifact] = []

        for record in records:
            all_artifacts.extend(self._build_anomaly_artifacts(record))

        report.artifacts = self._dedupe_artifacts(all_artifacts)
        report.ghost_log = self._build_anomaly_ghost_log(report.artifacts, records)
        report.ghost_log.data_hash = report.data_hash
        report.ghost_log.finalize()
        report.fingerprints = self.fingerprinter.analyze(report.artifacts)
        report.likely_stack = self.fingerprinter.get_likely_stack()
        report.security_concerns = self.fingerprinter.get_security_concerns()
        return report

    def _normalize_anomaly_records(self, df) -> List[Dict[str, Any]]:
        records = []
        for idx, record in enumerate(df.to_dict(orient="records")):
            flat: Dict[str, Any] = OrderedDict()
            self._flatten_record_fields("", record, flat)
            if not flat:
                flat[f"row_{idx}"] = record
            records.append(flat)
        return records

    def _flatten_record_fields(self, prefix: str, value: Any, out: Dict[str, Any]) -> None:
        key = prefix or "value"
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                next_key = f"{key}.{sub_key}" if prefix else str(sub_key)
                self._flatten_record_fields(next_key, sub_value, out)
            return
        if isinstance(value, list):
            if value and all(not isinstance(item, (dict, list)) for item in value):
                out[key] = value
                return
            for idx, item in enumerate(value[:5]):
                next_key = f"{key}[{idx}]"
                self._flatten_record_fields(next_key, item, out)
            return
        if isinstance(value, str):
            text = value.strip()
            if text:
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
                if isinstance(parsed, (dict, list)):
                    self._flatten_record_fields(key, parsed, out)
                    return
        out[key] = value

    def _build_anomaly_artifacts(self, record: Dict[str, Any]) -> List[Artifact]:
        artifacts: List[Artifact] = []
        component_hits = self._collect_record_hits(record, (
            "component", "service", "module", "subsystem", "scope"
        ))
        route_hits = self._collect_record_hits(record, (
            "route", "tool", "endpoint", "operation", "method"
        ))
        trace_hits = self._collect_record_hits(record, (
            "trace", "request_id", "session_id", "receipt", "cid", "event_id", "correlation"
        ))
        temporal_hits = self._collect_record_hits(record, (
            "timestamp", "created_at", "updated_at", "time", "date", "ts"
        ))
        retry_hits = self._collect_record_hits(record, (
            "retry", "attempt", "backoff", "timeout"
        ))
        status_hits = self._collect_record_hits(record, (
            "status", "status_code", "http_status", "code"
        ))
        error_hits = self._collect_record_hits(record, (
            "error", "exception", "message", "reason", "failure", "stack", "traceback"
        ), include_value_tokens=("error", "exception", "timeout", "failed", "traceback"))
        nested_hits = [entry for entry in record.items() if "." in str(entry[0]) or "[" in str(entry[0])]

        if component_hits:
            field_name, field_value = component_hits[0]
            artifacts.append(Artifact(
                artifact_type="component_scope",
                column=field_name,
                evidence=f"Observed component scope {field_name}={field_value}",
                confidence=0.92,
                inferred_operation="COMPONENT_ATTRIBUTION",
                details={"field": field_name, "value": field_value},
            ))
        if route_hits:
            field_name, field_value = route_hits[0]
            artifacts.append(Artifact(
                artifact_type="observability_route",
                column=field_name,
                evidence=f"Observed route/tool marker {field_name}={field_value}",
                confidence=0.90,
                inferred_operation="OBSERVABILITY_ROUTE",
                details={"field": field_name, "value": field_value},
            ))
        if trace_hits:
            field_name, field_value = trace_hits[0]
            artifacts.append(Artifact(
                artifact_type="trace_identifier",
                column=field_name,
                evidence=f"Trace-correlation identifier present via {field_name}",
                confidence=0.95,
                inferred_operation="TRACE_CORRELATION",
                details={"field": field_name, "value": field_value},
            ))
        if temporal_hits:
            field_name, field_value = temporal_hits[0]
            artifacts.append(Artifact(
                artifact_type="temporal_marker",
                column=field_name,
                evidence=f"Temporal evidence captured in {field_name}={field_value}",
                confidence=0.88,
                inferred_operation="TEMPORAL_EVIDENCE",
                details={"field": field_name, "value": field_value},
            ))
        if retry_hits:
            field_name, field_value = retry_hits[0]
            artifacts.append(Artifact(
                artifact_type="retry_marker",
                column=field_name,
                evidence=f"Retry/timeout diagnostic present via {field_name}={field_value}",
                confidence=0.84,
                inferred_operation="RETRY_DIAGNOSTIC",
                details={"field": field_name, "value": field_value},
            ))
        if status_hits:
            field_name, field_value = status_hits[0]
            artifacts.append(Artifact(
                artifact_type="failure_status",
                column=field_name,
                evidence=f"Failure status surfaced via {field_name}={field_value}",
                confidence=0.87,
                inferred_operation="TRANSPORT_FAILURE_STATUS",
                details={"field": field_name, "value": field_value},
            ))
        if error_hits:
            field_name, field_value = error_hits[0]
            artifacts.append(Artifact(
                artifact_type="error_signal",
                column=field_name,
                evidence=f"Structured error signal present in {field_name}",
                confidence=0.93,
                inferred_operation="DEBUG_ERROR_SIGNAL",
                details={"field": field_name, "value": field_value},
            ))
        if nested_hits:
            sample_fields = [str(name) for name, _ in nested_hits[:4]]
            artifacts.append(Artifact(
                artifact_type="nested_failure_context",
                column=sample_fields[0],
                evidence=f"Nested failure context retained across {len(nested_hits)} fields",
                confidence=0.82,
                inferred_operation="NESTED_FAILURE_CONTEXT",
                details={"fields": sample_fields, "field_count": len(nested_hits)},
            ))

        return artifacts

    def _collect_record_hits(
        self,
        record: Dict[str, Any],
        key_tokens: tuple,
        include_value_tokens: tuple = (),
    ) -> List[Any]:
        hits = []
        for field_name, field_value in record.items():
            key_lower = str(field_name).lower()
            value_text = self._stringify_field(field_value)
            value_lower = value_text.lower()
            if any(token in key_lower for token in key_tokens) or (
                include_value_tokens and any(token in value_lower for token in include_value_tokens)
            ):
                if value_text:
                    hits.append((str(field_name), value_text))
        return hits

    def _stringify_field(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, dict)):
            try:
                return json.dumps(value, sort_keys=True)
            except Exception:
                return str(value)
        return str(value).strip()

    def _dedupe_artifacts(self, artifacts: List[Artifact]) -> List[Artifact]:
        deduped: List[Artifact] = []
        seen = set()
        for artifact in artifacts:
            sig = (
                artifact.artifact_type,
                artifact.column,
                artifact.evidence,
                artifact.inferred_operation,
            )
            if sig in seen:
                continue
            seen.add(sig)
            deduped.append(artifact)
        return deduped

    def _build_anomaly_ghost_log(self, artifacts: List[Artifact], records: List[Dict[str, Any]]) -> GhostLog:
        ghost = GhostLog()
        by_operation = OrderedDict()
        for artifact in artifacts:
            by_operation.setdefault(artifact.inferred_operation, []).append(artifact)

        if "COMPONENT_ATTRIBUTION" in by_operation:
            ghost.add_operation(
                "COMPONENT_ATTRIBUTION",
                "Failure payload preserved component/service ownership for the observed anomaly.",
                max(a.confidence for a in by_operation["COMPONENT_ATTRIBUTION"]),
                [a.evidence for a in by_operation["COMPONENT_ATTRIBUTION"][:3]],
            )
        if "OBSERVABILITY_ROUTE" in by_operation:
            ghost.add_operation(
                "OBSERVABILITY_ROUTE",
                "Instrumentation retained the route/tool surface where the anomaly was emitted.",
                max(a.confidence for a in by_operation["OBSERVABILITY_ROUTE"]),
                [a.evidence for a in by_operation["OBSERVABILITY_ROUTE"][:3]],
            )
        if "TRACE_CORRELATION" in by_operation:
            ghost.add_operation(
                "TRACE_CORRELATION",
                "The payload contains correlation identifiers suitable for cross-system debugging.",
                max(a.confidence for a in by_operation["TRACE_CORRELATION"]),
                [a.evidence for a in by_operation["TRACE_CORRELATION"][:3]],
            )
        if "TEMPORAL_EVIDENCE" in by_operation:
            ghost.add_operation(
                "TEMPORAL_CAPTURE",
                "Temporal markers were preserved, allowing the anomaly to be placed on a timeline.",
                max(a.confidence for a in by_operation["TEMPORAL_EVIDENCE"]),
                [a.evidence for a in by_operation["TEMPORAL_EVIDENCE"][:3]],
            )
        if "RETRY_DIAGNOSTIC" in by_operation:
            ghost.add_operation(
                "RETRY_HANDLING",
                "Retry/backoff or timeout behavior was captured in the failure payload.",
                max(a.confidence for a in by_operation["RETRY_DIAGNOSTIC"]),
                [a.evidence for a in by_operation["RETRY_DIAGNOSTIC"][:3]],
            )
        if "TRANSPORT_FAILURE_STATUS" in by_operation or "DEBUG_ERROR_SIGNAL" in by_operation:
            relevant = by_operation.get("TRANSPORT_FAILURE_STATUS", []) + by_operation.get("DEBUG_ERROR_SIGNAL", [])
            ghost.add_operation(
                "FAILURE_CLASSIFICATION",
                "The anomaly payload includes explicit failure/status evidence instead of only raw text.",
                max(a.confidence for a in relevant),
                [a.evidence for a in relevant[:4]],
            )
        if "NESTED_FAILURE_CONTEXT" in by_operation:
            ghost.add_operation(
                "CONTEXT_ATTACHMENT",
                "Nested context survived transport, preserving debug-relevant structured details.",
                max(a.confidence for a in by_operation["NESTED_FAILURE_CONTEXT"]),
                [a.evidence for a in by_operation["NESTED_FAILURE_CONTEXT"][:3]],
            )
        if not ghost.operations and records:
            ghost.add_operation(
                "SINGLE_EVENT_CAPTURE",
                "A small-sample anomaly payload was analyzed, but only limited structured evidence was available.",
                0.35,
                [f"{len(records)} record(s) analyzed in anomaly mode"],
            )
        return ghost
    
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
    
    def analyze_file(self, filepath: str, mode: str = "auto") -> ForensicsReport:
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
        
        return self.analyze(df, mode=mode)


def analyze_dataframe(df, mode: str = "auto") -> ForensicsReport:
    """Convenience function to analyze a dataframe."""
    forensics = DataForensics()
    return forensics.analyze(df, mode=mode)


def analyze_file(filepath: str, mode: str = "auto") -> ForensicsReport:
    """Convenience function to analyze a file."""
    forensics = DataForensics()
    return forensics.analyze_file(filepath, mode=mode)
