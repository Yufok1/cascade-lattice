"""
CASCADE Forensics - Artifact Detectors

Each detector looks for specific patterns in data that reveal
how it was processed. The data remembers. We read.
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from collections import Counter
import statistics


@dataclass
class Artifact:
    """A single detected artifact - evidence of processing."""
    artifact_type: str
    column: str
    evidence: str
    confidence: float  # 0.0 to 1.0
    inferred_operation: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.artifact_type,
            "column": self.column,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "inferred_op": self.inferred_operation,
            "details": self.details,
        }


class ArtifactDetector:
    """Base class for artifact detection."""
    
    name: str = "base"
    
    def detect(self, df, column: str) -> List[Artifact]:
        """Detect artifacts in a column. Override in subclasses."""
        return []
    
    def detect_all(self, df) -> List[Artifact]:
        """Detect artifacts across all applicable columns."""
        artifacts = []
        for col in df.columns:
            artifacts.extend(self.detect(df, col))
        return artifacts


class TimestampArtifacts(ArtifactDetector):
    """
    Detect timestamp patterns that reveal processing behavior.
    
    Artifacts detected:
    - Rounding to minute/hour/day (batch processing intervals)
    - Regular intervals (scheduled jobs)
    - Temporal clustering (burst processing)
    - Timezone artifacts
    - Future/past anomalies
    """
    
    name = "timestamp"
    
    def detect(self, df, column: str) -> List[Artifact]:
        artifacts = []
        
        # Check if column looks like timestamps
        if not self._is_timestamp_column(df, column):
            return artifacts
        
        try:
            timestamps = self._parse_timestamps(df, column)
            if len(timestamps) < 2:
                return artifacts
            
            # Check for rounding patterns
            rounding = self._detect_rounding(timestamps)
            if rounding:
                artifacts.append(rounding)
            
            # Check for regular intervals
            intervals = self._detect_intervals(timestamps)
            if intervals:
                artifacts.append(intervals)
            
            # Check for clustering
            clustering = self._detect_clustering(timestamps)
            if clustering:
                artifacts.append(clustering)
            
            # Check for timezone issues
            tz_artifacts = self._detect_timezone_artifacts(timestamps)
            artifacts.extend(tz_artifacts)
            
        except Exception:
            pass
        
        return artifacts
    
    def _is_timestamp_column(self, df, column: str) -> bool:
        """Heuristic to detect timestamp columns."""
        col_lower = column.lower()
        timestamp_hints = ['time', 'date', 'created', 'updated', 'modified', 'timestamp', '_at', '_on']
        if any(hint in col_lower for hint in timestamp_hints):
            return True
        
        # Check data type
        dtype = str(df[column].dtype)
        if 'datetime' in dtype or 'time' in dtype:
            return True
        
        # Sample and check format
        sample = df[column].dropna().head(5).astype(str).tolist()
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{10,13}',  # Unix timestamp
        ]
        for val in sample:
            for pattern in date_patterns:
                if re.search(pattern, val):
                    return True
        
        return False
    
    def _parse_timestamps(self, df, column: str) -> List[datetime]:
        """Parse column to datetime objects."""
        import pandas as pd
        
        try:
            # Try pandas datetime conversion
            parsed = pd.to_datetime(df[column], errors='coerce')
            return [ts.to_pydatetime() for ts in parsed.dropna()]
        except:
            return []
    
    def _detect_rounding(self, timestamps: List[datetime]) -> Optional[Artifact]:
        """Detect if timestamps are rounded to specific intervals."""
        if len(timestamps) < 10:
            return None
        
        # Check seconds
        seconds = [ts.second for ts in timestamps]
        unique_seconds = set(seconds)
        
        # All zeros = minute rounding
        if unique_seconds == {0}:
            # Check minutes
            minutes = [ts.minute for ts in timestamps]
            unique_minutes = set(minutes)
            
            if unique_minutes == {0}:
                return Artifact(
                    artifact_type="timestamp_rounding",
                    column="timestamps",
                    evidence=f"All timestamps rounded to hour (0 minutes, 0 seconds)",
                    confidence=0.95,
                    inferred_operation="BATCH_HOURLY",
                    details={"interval": "hour", "sample_size": len(timestamps)}
                )
            elif all(m % 15 == 0 for m in minutes):
                return Artifact(
                    artifact_type="timestamp_rounding",
                    column="timestamps",
                    evidence=f"Timestamps rounded to 15-minute intervals",
                    confidence=0.90,
                    inferred_operation="BATCH_15MIN",
                    details={"interval": "15min", "unique_minutes": list(unique_minutes)}
                )
            elif all(m % 5 == 0 for m in minutes):
                return Artifact(
                    artifact_type="timestamp_rounding",
                    column="timestamps",
                    evidence=f"Timestamps rounded to 5-minute intervals",
                    confidence=0.85,
                    inferred_operation="BATCH_5MIN",
                    details={"interval": "5min"}
                )
            else:
                return Artifact(
                    artifact_type="timestamp_rounding",
                    column="timestamps",
                    evidence=f"Timestamps rounded to minute (0 seconds)",
                    confidence=0.85,
                    inferred_operation="BATCH_MINUTE",
                    details={"interval": "minute"}
                )
        
        # Check if seconds cluster on specific values
        second_counts = Counter(seconds)
        most_common = second_counts.most_common(1)[0]
        if most_common[1] > len(timestamps) * 0.8:
            return Artifact(
                artifact_type="timestamp_rounding",
                column="timestamps",
                evidence=f"{most_common[1]/len(timestamps)*100:.0f}% of timestamps have second={most_common[0]}",
                confidence=0.70,
                inferred_operation="SYSTEMATIC_TIMESTAMP_ASSIGNMENT",
                details={"dominant_second": most_common[0], "percentage": most_common[1]/len(timestamps)}
            )
        
        return None
    
    def _detect_intervals(self, timestamps: List[datetime]) -> Optional[Artifact]:
        """Detect regular time intervals suggesting scheduled jobs."""
        if len(timestamps) < 10:
            return None
        
        sorted_ts = sorted(timestamps)
        deltas = [(sorted_ts[i+1] - sorted_ts[i]).total_seconds() for i in range(len(sorted_ts)-1)]
        
        if not deltas:
            return None
        
        # Check for consistent intervals
        median_delta = statistics.median(deltas)
        if median_delta == 0:
            return None
        
        # Count how many deltas are close to median
        tolerance = median_delta * 0.1  # 10% tolerance
        consistent = sum(1 for d in deltas if abs(d - median_delta) < tolerance)
        consistency_ratio = consistent / len(deltas)
        
        if consistency_ratio > 0.7:
            # Describe the interval
            interval_desc = self._describe_interval(median_delta)
            return Artifact(
                artifact_type="regular_intervals",
                column="timestamps",
                evidence=f"{consistency_ratio*100:.0f}% of records have ~{interval_desc} intervals",
                confidence=min(0.95, consistency_ratio),
                inferred_operation=f"SCHEDULED_JOB_{interval_desc.upper().replace(' ', '_')}",
                details={
                    "median_seconds": median_delta,
                    "interval_desc": interval_desc,
                    "consistency": consistency_ratio
                }
            )
        
        return None
    
    def _describe_interval(self, seconds: float) -> str:
        """Human-readable interval description."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}min"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}hr"
        else:
            return f"{seconds/86400:.1f}day"
    
    def _detect_clustering(self, timestamps: List[datetime]) -> Optional[Artifact]:
        """Detect temporal clustering (burst processing)."""
        if len(timestamps) < 20:
            return None
        
        sorted_ts = sorted(timestamps)
        
        # Look for bursts: many records in short time, then gaps
        deltas = [(sorted_ts[i+1] - sorted_ts[i]).total_seconds() for i in range(len(sorted_ts)-1)]
        
        if not deltas:
            return None
        
        median_delta = statistics.median(deltas)
        if median_delta == 0:
            return None
        
        # Count "burst" deltas (much smaller than median) vs "gap" deltas (much larger)
        bursts = sum(1 for d in deltas if d < median_delta * 0.1)
        gaps = sum(1 for d in deltas if d > median_delta * 5)
        
        if bursts > len(deltas) * 0.3 and gaps > len(deltas) * 0.05:
            return Artifact(
                artifact_type="temporal_clustering",
                column="timestamps",
                evidence=f"Burst pattern: {bursts} rapid records, {gaps} long gaps",
                confidence=0.75,
                inferred_operation="BATCH_BURST_PROCESSING",
                details={
                    "burst_count": bursts,
                    "gap_count": gaps,
                    "median_delta_seconds": median_delta
                }
            )
        
        return None
    
    def _detect_timezone_artifacts(self, timestamps: List[datetime]) -> List[Artifact]:
        """Detect timezone-related artifacts."""
        artifacts = []
        
        # Check for hour distribution anomalies (e.g., no records 0-7 UTC = US business hours)
        hours = [ts.hour for ts in timestamps]
        hour_counts = Counter(hours)
        
        # Check for gaps suggesting business hours in a specific timezone
        zero_hours = [h for h in range(24) if hour_counts.get(h, 0) == 0]
        
        if len(zero_hours) >= 6 and len(zero_hours) <= 12:
            # Contiguous gap?
            zero_hours_sorted = sorted(zero_hours)
            if zero_hours_sorted[-1] - zero_hours_sorted[0] == len(zero_hours) - 1:
                artifacts.append(Artifact(
                    artifact_type="business_hours",
                    column="timestamps",
                    evidence=f"No records during hours {min(zero_hours)}-{max(zero_hours)} UTC",
                    confidence=0.70,
                    inferred_operation="BUSINESS_HOURS_ONLY",
                    details={"quiet_hours": zero_hours}
                ))
        
        return artifacts


class IDPatternArtifacts(ArtifactDetector):
    """
    Detect ID patterns that reveal data lineage.
    
    Artifacts detected:
    - Sequential IDs with gaps (deletions/filtering)
    - UUID versions (generation method)
    - Prefixes (source identification)
    - Hash patterns (deterministic generation)
    """
    
    name = "id_patterns"
    
    def detect(self, df, column: str) -> List[Artifact]:
        artifacts = []
        
        if not self._is_id_column(df, column):
            return artifacts
        
        try:
            values = df[column].dropna().astype(str).tolist()
            if len(values) < 5:
                return artifacts
            
            # Check for sequential integers with gaps
            gaps = self._detect_sequential_gaps(values)
            if gaps:
                artifacts.append(gaps)
            
            # Check for UUID patterns
            uuid_artifact = self._detect_uuid_patterns(values)
            if uuid_artifact:
                artifacts.append(uuid_artifact)
            
            # Check for prefixes
            prefix = self._detect_prefixes(values)
            if prefix:
                artifacts.append(prefix)
            
            # Check for hash patterns
            hash_artifact = self._detect_hash_patterns(values)
            if hash_artifact:
                artifacts.append(hash_artifact)
            
        except Exception:
            pass
        
        return artifacts
    
    def _is_id_column(self, df, column: str) -> bool:
        """Heuristic to detect ID columns."""
        col_lower = column.lower()
        id_hints = ['id', 'key', 'uuid', 'guid', 'pk', '_id', 'identifier']
        return any(hint in col_lower for hint in id_hints)
    
    def _detect_sequential_gaps(self, values: List[str]) -> Optional[Artifact]:
        """Detect sequential IDs with gaps indicating deletions."""
        # Try to parse as integers
        try:
            ints = sorted([int(v) for v in values if v.isdigit()])
            if len(ints) < 10:
                return None
            
            # Check for gaps
            expected_count = ints[-1] - ints[0] + 1
            actual_count = len(set(ints))
            gap_count = expected_count - actual_count
            gap_ratio = gap_count / expected_count if expected_count > 0 else 0
            
            if gap_ratio > 0.05:  # More than 5% missing
                return Artifact(
                    artifact_type="sequential_id_gaps",
                    column=values[0] if values else "id",
                    evidence=f"Sequential IDs with {gap_ratio*100:.1f}% gaps ({gap_count} missing)",
                    confidence=0.85,
                    inferred_operation="FILTERING_OR_DELETION",
                    details={
                        "min_id": ints[0],
                        "max_id": ints[-1],
                        "expected": expected_count,
                        "actual": actual_count,
                        "gap_ratio": gap_ratio
                    }
                )
        except:
            pass
        
        return None
    
    def _detect_uuid_patterns(self, values: List[str]) -> Optional[Artifact]:
        """Detect UUID version from patterns."""
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-([0-9a-f])[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        
        versions = []
        for v in values[:100]:  # Sample
            match = uuid_pattern.match(v)
            if match:
                versions.append(match.group(1))
        
        if len(versions) < len(values[:100]) * 0.5:
            return None
        
        version_counts = Counter(versions)
        dominant = version_counts.most_common(1)[0]
        
        version_meanings = {
            '1': 'TIME_BASED_MAC',      # Reveals generation time + machine
            '2': 'DCE_SECURITY',
            '3': 'MD5_HASH',            # Deterministic from input
            '4': 'RANDOM',              # Crypto random
            '5': 'SHA1_HASH',           # Deterministic from input
            '6': 'SORTABLE_TIME',       # Modern time-sortable
            '7': 'UNIX_TIME_RANDOM',    # Time-ordered with randomness
        }
        
        return Artifact(
            artifact_type="uuid_version",
            column="id",
            evidence=f"UUIDs are version {dominant[0]} ({version_meanings.get(dominant[0], 'UNKNOWN')})",
            confidence=0.90,
            inferred_operation=f"UUID_GENERATION_V{dominant[0]}",
            details={
                "version": dominant[0],
                "meaning": version_meanings.get(dominant[0], 'unknown'),
                "sample_count": len(versions)
            }
        )
    
    def _detect_prefixes(self, values: List[str]) -> Optional[Artifact]:
        """Detect common prefixes indicating source systems."""
        if len(values) < 10:
            return None
        
        # Find common prefix
        prefix_len = 0
        for i in range(1, min(20, min(len(v) for v in values[:100]))):
            prefixes = set(v[:i] for v in values[:100])
            if len(prefixes) <= 3:  # Allow up to 3 different prefixes
                prefix_len = i
            else:
                break
        
        if prefix_len >= 2:
            prefixes = Counter(v[:prefix_len] for v in values)
            top_prefixes = prefixes.most_common(3)
            
            return Artifact(
                artifact_type="id_prefix",
                column="id",
                evidence=f"IDs have systematic prefix: {top_prefixes}",
                confidence=0.80,
                inferred_operation="MULTI_SOURCE_MERGE" if len(top_prefixes) > 1 else "SOURCE_IDENTIFICATION",
                details={
                    "prefixes": dict(top_prefixes),
                    "prefix_length": prefix_len
                }
            )
        
        return None
    
    def _detect_hash_patterns(self, values: List[str]) -> Optional[Artifact]:
        """Detect if IDs look like hashes."""
        hex_pattern = re.compile(r'^[0-9a-f]+$', re.I)
        
        hex_lengths = []
        for v in values[:100]:
            if hex_pattern.match(v):
                hex_lengths.append(len(v))
        
        if len(hex_lengths) < len(values[:100]) * 0.8:
            return None
        
        # Check for consistent hash lengths
        length_counts = Counter(hex_lengths)
        dominant = length_counts.most_common(1)[0]
        
        hash_types = {
            32: 'MD5',
            40: 'SHA1',
            64: 'SHA256',
            128: 'SHA512',
            16: 'SHORT_HASH',
        }
        
        if dominant[1] > len(hex_lengths) * 0.9:
            hash_type = hash_types.get(dominant[0], f'{dominant[0]}-char hash')
            return Artifact(
                artifact_type="hash_id",
                column="id",
                evidence=f"IDs are {hash_type} hashes ({dominant[0]} hex chars)",
                confidence=0.85,
                inferred_operation=f"DETERMINISTIC_ID_GENERATION_{hash_type}",
                details={
                    "hash_length": dominant[0],
                    "probable_algorithm": hash_type
                }
            )
        
        return None


class TextArtifacts(ArtifactDetector):
    """
    Detect text processing artifacts.
    
    Artifacts detected:
    - Truncation (field length limits)
    - Encoding issues (charset conversion)
    - Case normalization
    - Whitespace patterns
    - Sanitization patterns
    """
    
    name = "text"
    
    def detect(self, df, column: str) -> List[Artifact]:
        artifacts = []
        
        dtype = str(df[column].dtype)
        if 'object' not in dtype and 'str' not in dtype:
            return artifacts
        
        try:
            values = df[column].dropna().astype(str).tolist()
            if len(values) < 5:
                return artifacts
            
            # Truncation
            trunc = self._detect_truncation(values)
            if trunc:
                artifacts.append(trunc)
            
            # Encoding issues
            encoding = self._detect_encoding_artifacts(values)
            if encoding:
                artifacts.append(encoding)
            
            # Case patterns
            case = self._detect_case_patterns(values, column)
            if case:
                artifacts.append(case)
            
            # Whitespace
            ws = self._detect_whitespace_patterns(values)
            if ws:
                artifacts.append(ws)
            
        except Exception:
            pass
        
        return artifacts
    
    def _detect_truncation(self, values: List[str]) -> Optional[Artifact]:
        """Detect truncation at specific lengths."""
        lengths = [len(v) for v in values]
        max_len = max(lengths)
        
        # Count values at max length
        at_max = sum(1 for l in lengths if l == max_len)
        
        # If many values hit the max, likely truncation
        if at_max > len(values) * 0.1 and max_len > 10:
            # Check if values at max look truncated (end mid-word, etc.)
            max_values = [v for v in values if len(v) == max_len]
            truncated_looking = sum(1 for v in max_values if not v.endswith(('.', '!', '?', ' ')))
            
            if truncated_looking > len(max_values) * 0.5:
                return Artifact(
                    artifact_type="truncation",
                    column=str(values[0])[:20] if values else "text",
                    evidence=f"{at_max} values ({at_max/len(values)*100:.1f}%) truncated at {max_len} chars",
                    confidence=0.80,
                    inferred_operation=f"FIELD_LENGTH_LIMIT_{max_len}",
                    details={
                        "max_length": max_len,
                        "truncated_count": at_max,
                        "truncated_ratio": at_max / len(values)
                    }
                )
        
        return None
    
    def _detect_encoding_artifacts(self, values: List[str]) -> Optional[Artifact]:
        """Detect encoding/charset conversion issues."""
        # Common mojibake patterns
        mojibake_patterns = [
            r'Ã©',  # é misencoded
            r'Ã¨',  # è
            r'Ã ',  # à
            r'â€™',  # ' smart quote
            r'â€"',  # — em dash
            r'Ã¶',  # ö
            r'Ã¼',  # ü
            r'ï»¿',  # BOM
            r'\\x[0-9a-f]{2}',  # Raw hex escapes
            r'&amp;|&lt;|&gt;',  # HTML entities
        ]
        
        issue_count = 0
        patterns_found = set()
        
        for v in values[:500]:  # Sample
            for pattern in mojibake_patterns:
                if re.search(pattern, v):
                    issue_count += 1
                    patterns_found.add(pattern)
                    break
        
        if issue_count > 5:
            return Artifact(
                artifact_type="encoding_artifact",
                column="text",
                evidence=f"{issue_count} values have encoding issues (patterns: {patterns_found})",
                confidence=0.85,
                inferred_operation="CHARSET_CONVERSION_ERROR",
                details={
                    "issue_count": issue_count,
                    "patterns": list(patterns_found)
                }
            )
        
        return None
    
    def _detect_case_patterns(self, values: List[str], column: str) -> Optional[Artifact]:
        """Detect case normalization."""
        # Skip obviously non-text columns
        sample = values[:100]
        
        all_lower = all(v == v.lower() for v in sample if v.strip())
        all_upper = all(v == v.upper() for v in sample if v.strip())
        
        if all_lower:
            return Artifact(
                artifact_type="case_normalization",
                column=column,
                evidence="All values are lowercase",
                confidence=0.90,
                inferred_operation="LOWERCASE_NORMALIZATION",
                details={"case": "lower"}
            )
        elif all_upper:
            return Artifact(
                artifact_type="case_normalization",
                column=column,
                evidence="All values are UPPERCASE",
                confidence=0.90,
                inferred_operation="UPPERCASE_NORMALIZATION",
                details={"case": "upper"}
            )
        
        return None
    
    def _detect_whitespace_patterns(self, values: List[str]) -> Optional[Artifact]:
        """Detect whitespace handling patterns."""
        # Check for leading/trailing whitespace
        has_leading = sum(1 for v in values if v and v[0] == ' ')
        has_trailing = sum(1 for v in values if v and v[-1] == ' ')
        
        # No whitespace at all = trimmed
        if has_leading == 0 and has_trailing == 0:
            # Verify there's text that COULD have whitespace
            has_spaces = sum(1 for v in values if ' ' in v.strip())
            if has_spaces > len(values) * 0.3:
                return Artifact(
                    artifact_type="whitespace_trimming",
                    column="text",
                    evidence="No leading/trailing whitespace (data was trimmed)",
                    confidence=0.70,
                    inferred_operation="WHITESPACE_TRIM",
                    details={"trimmed": True}
                )
        
        return None


class NumericArtifacts(ArtifactDetector):
    """
    Detect numeric processing artifacts.
    
    Artifacts detected:
    - Rounding patterns (precision limits)
    - Outlier presence/absence (filtering)
    - Distribution anomalies (sampling)
    - Sentinel values (nulls represented as -1, 0, 9999)
    """
    
    name = "numeric"
    
    def detect(self, df, column: str) -> List[Artifact]:
        artifacts = []
        
        # Check if numeric
        try:
            values = df[column].dropna()
            if len(values) < 10:
                return artifacts
            
            # Try to get numeric values
            numeric_values = values.astype(float).tolist()
            
            # Rounding
            rounding = self._detect_rounding(numeric_values, column)
            if rounding:
                artifacts.append(rounding)
            
            # Sentinel values
            sentinel = self._detect_sentinel_values(numeric_values, column)
            if sentinel:
                artifacts.append(sentinel)
            
            # Distribution
            dist = self._detect_distribution_artifacts(numeric_values, column)
            if dist:
                artifacts.append(dist)
            
        except (ValueError, TypeError):
            pass
        
        return artifacts
    
    def _detect_rounding(self, values: List[float], column: str) -> Optional[Artifact]:
        """Detect systematic rounding."""
        # Check decimal places
        decimal_places = []
        for v in values[:500]:
            if v != int(v):
                str_v = f"{v:.10f}".rstrip('0')
                if '.' in str_v:
                    decimal_places.append(len(str_v.split('.')[1]))
        
        if not decimal_places:
            # All integers - check for rounding to 10, 100, etc.
            int_values = [int(v) for v in values]
            
            divisible_by_100 = sum(1 for v in int_values if v % 100 == 0)
            divisible_by_10 = sum(1 for v in int_values if v % 10 == 0)
            
            if divisible_by_100 > len(int_values) * 0.9:
                return Artifact(
                    artifact_type="numeric_rounding",
                    column=column,
                    evidence="Values rounded to nearest 100",
                    confidence=0.85,
                    inferred_operation="ROUND_TO_100",
                    details={"rounding": 100}
                )
            elif divisible_by_10 > len(int_values) * 0.9:
                return Artifact(
                    artifact_type="numeric_rounding",
                    column=column,
                    evidence="Values rounded to nearest 10",
                    confidence=0.80,
                    inferred_operation="ROUND_TO_10",
                    details={"rounding": 10}
                )
        else:
            # Check for consistent decimal places
            max_decimals = max(decimal_places)
            at_max = sum(1 for d in decimal_places if d == max_decimals)
            
            if at_max < len(decimal_places) * 0.3 and max_decimals <= 2:
                return Artifact(
                    artifact_type="numeric_rounding",
                    column=column,
                    evidence=f"Values appear rounded to {max_decimals} decimal places",
                    confidence=0.75,
                    inferred_operation=f"ROUND_TO_{max_decimals}_DECIMALS",
                    details={"decimal_places": max_decimals}
                )
        
        return None
    
    def _detect_sentinel_values(self, values: List[float], column: str) -> Optional[Artifact]:
        """Detect sentinel values representing nulls."""
        sentinels = [-1, -999, -9999, 0, 9999, 99999]
        
        value_counts = Counter(values)
        
        for sentinel in sentinels:
            if sentinel in value_counts:
                count = value_counts[sentinel]
                if count > len(values) * 0.01:  # More than 1%
                    return Artifact(
                        artifact_type="sentinel_value",
                        column=column,
                        evidence=f"{count} occurrences of {sentinel} (likely NULL sentinel)",
                        confidence=0.70,
                        inferred_operation=f"NULL_AS_{int(sentinel)}",
                        details={
                            "sentinel": sentinel,
                            "count": count,
                            "percentage": count / len(values) * 100
                        }
                    )
        
        return None
    
    def _detect_distribution_artifacts(self, values: List[float], column: str) -> Optional[Artifact]:
        """Detect distribution anomalies suggesting filtering/sampling."""
        if len(values) < 100:
            return None
        
        # Check for hard cutoffs
        sorted_vals = sorted(values)
        min_val, max_val = sorted_vals[0], sorted_vals[-1]
        
        # Round number cutoffs suggest filtering
        if max_val == int(max_val) and max_val % 10 == 0:
            # Check if there's a cluster at the max
            at_max = sum(1 for v in values if v == max_val)
            if at_max > len(values) * 0.05:
                return Artifact(
                    artifact_type="hard_cutoff",
                    column=column,
                    evidence=f"Hard cutoff at {max_val} ({at_max} values at limit)",
                    confidence=0.75,
                    inferred_operation=f"CAP_AT_{int(max_val)}",
                    details={
                        "cutoff": max_val,
                        "count_at_cutoff": at_max
                    }
                )
        
        return None


class NullPatternArtifacts(ArtifactDetector):
    """
    Detect null/missing value patterns.
    
    Artifacts detected:
    - Systematic nulls (default handling)
    - Null correlations (conditional logic)
    - Null rates anomalies (ETL errors)
    """
    
    name = "null_patterns"
    
    def detect_all(self, df) -> List[Artifact]:
        """Analyze null patterns across all columns."""
        artifacts = []
        
        # Overall null rates per column
        null_rates = {}
        for col in df.columns:
            null_rate = df[col].isna().mean()
            null_rates[col] = null_rate
        
        # Detect anomalous null rates
        rates = list(null_rates.values())
        if len(rates) > 3:
            mean_rate = statistics.mean(rates)
            
            for col, rate in null_rates.items():
                if rate > 0.5 and rate > mean_rate * 3:
                    artifacts.append(Artifact(
                        artifact_type="high_null_rate",
                        column=col,
                        evidence=f"{rate*100:.1f}% null (vs {mean_rate*100:.1f}% average)",
                        confidence=0.70,
                        inferred_operation="OPTIONAL_FIELD_OR_ETL_ERROR",
                        details={
                            "null_rate": rate,
                            "avg_null_rate": mean_rate
                        }
                    ))
        
        # Detect columns that are null together (conditional logic)
        # This is expensive so we sample
        if len(df) > 100:
            sample = df.sample(min(1000, len(df)))
        else:
            sample = df
        
        correlated_nulls = []
        cols = list(df.columns)
        for i, col1 in enumerate(cols):
            for col2 in cols[i+1:]:
                both_null = (sample[col1].isna() & sample[col2].isna()).mean()
                either_null = (sample[col1].isna() | sample[col2].isna()).mean()
                
                if either_null > 0.1 and both_null / either_null > 0.8:
                    correlated_nulls.append((col1, col2, both_null))
        
        if correlated_nulls:
            artifacts.append(Artifact(
                artifact_type="correlated_nulls",
                column="multiple",
                evidence=f"{len(correlated_nulls)} column pairs have correlated nulls",
                confidence=0.75,
                inferred_operation="CONDITIONAL_FIELD_POPULATION",
                details={
                    "pairs": [(c1, c2) for c1, c2, _ in correlated_nulls[:5]]
                }
            ))
        
        return artifacts
    
    def detect(self, df, column: str) -> List[Artifact]:
        """Null patterns are analyzed globally, not per-column."""
        return []


class SchemaArtifacts(ArtifactDetector):
    """
    Detect schema-level artifacts.
    
    Artifacts detected:
    - Column naming conventions (framework hints)
    - Data type patterns (database origin)
    - Schema inconsistencies (merged sources)
    """
    
    name = "schema"
    
    def detect_all(self, df) -> List[Artifact]:
        """Analyze schema patterns."""
        artifacts = []
        
        columns = list(df.columns)
        
        # Naming convention detection
        conventions = self._detect_naming_conventions(columns)
        if conventions:
            artifacts.append(conventions)
        
        # Framework fingerprints
        framework = self._detect_framework_fingerprints(columns)
        if framework:
            artifacts.append(framework)
        
        # Mixed conventions (merged sources)
        mixed = self._detect_mixed_conventions(columns)
        if mixed:
            artifacts.append(mixed)
        
        return artifacts
    
    def detect(self, df, column: str) -> List[Artifact]:
        """Schema patterns are analyzed globally."""
        return []
    
    def _detect_naming_conventions(self, columns: List[str]) -> Optional[Artifact]:
        """Detect column naming convention."""
        snake_case = sum(1 for c in columns if '_' in c and c == c.lower())
        camel_case = sum(1 for c in columns if re.match(r'^[a-z]+([A-Z][a-z]+)+$', c))
        pascal_case = sum(1 for c in columns if re.match(r'^([A-Z][a-z]+)+$', c))
        
        total = len(columns)
        
        if snake_case > total * 0.7:
            return Artifact(
                artifact_type="naming_convention",
                column="schema",
                evidence=f"snake_case naming ({snake_case}/{total} columns)",
                confidence=0.80,
                inferred_operation="PYTHON_OR_SQL_ORIGIN",
                details={"convention": "snake_case", "ratio": snake_case/total}
            )
        elif camel_case > total * 0.5:
            return Artifact(
                artifact_type="naming_convention",
                column="schema",
                evidence=f"camelCase naming ({camel_case}/{total} columns)",
                confidence=0.80,
                inferred_operation="JAVASCRIPT_OR_JAVA_ORIGIN",
                details={"convention": "camelCase", "ratio": camel_case/total}
            )
        elif pascal_case > total * 0.5:
            return Artifact(
                artifact_type="naming_convention",
                column="schema",
                evidence=f"PascalCase naming ({pascal_case}/{total} columns)",
                confidence=0.80,
                inferred_operation="DOTNET_OR_JAVA_ORIGIN",
                details={"convention": "PascalCase", "ratio": pascal_case/total}
            )
        
        return None
    
    def _detect_framework_fingerprints(self, columns: List[str]) -> Optional[Artifact]:
        """Detect framework-specific column patterns."""
        col_lower = [c.lower() for c in columns]
        
        # Django fingerprints
        if 'id' in col_lower and 'created_at' in col_lower:
            return Artifact(
                artifact_type="framework_fingerprint",
                column="schema",
                evidence="Django/Rails-style auto columns (id, created_at)",
                confidence=0.65,
                inferred_operation="ORM_GENERATED_SCHEMA",
                details={"framework_hints": ["django", "rails", "sqlalchemy"]}
            )
        
        # Pandas export fingerprints
        if 'unnamed: 0' in col_lower or any('unnamed:' in c for c in col_lower):
            return Artifact(
                artifact_type="framework_fingerprint",
                column="schema",
                evidence="Pandas index column artifact (Unnamed: 0)",
                confidence=0.90,
                inferred_operation="PANDAS_CSV_EXPORT",
                details={"framework": "pandas"}
            )
        
        # MongoDB fingerprints
        if '_id' in col_lower:
            return Artifact(
                artifact_type="framework_fingerprint",
                column="schema",
                evidence="MongoDB _id column present",
                confidence=0.85,
                inferred_operation="MONGODB_EXPORT",
                details={"framework": "mongodb"}
            )
        
        return None
    
    def _detect_mixed_conventions(self, columns: List[str]) -> Optional[Artifact]:
        """Detect mixed naming conventions suggesting merged sources."""
        snake_case = sum(1 for c in columns if '_' in c and c == c.lower())
        camel_case = sum(1 for c in columns if re.match(r'^[a-z]+([A-Z][a-z]+)+$', c))
        
        total = len(columns)
        
        # Both conventions present significantly
        if snake_case > total * 0.2 and camel_case > total * 0.2:
            return Artifact(
                artifact_type="mixed_conventions",
                column="schema",
                evidence=f"Mixed naming: {snake_case} snake_case, {camel_case} camelCase",
                confidence=0.75,
                inferred_operation="MERGED_SOURCES",
                details={
                    "snake_case_count": snake_case,
                    "camel_case_count": camel_case
                }
            )
        
        return None
