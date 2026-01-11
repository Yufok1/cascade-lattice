"""
CASCADE Forensics - Technology Fingerprinting

Map detected artifacts to likely technologies and tools.
The artifacts are evidence. This module is the detective.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
from collections import defaultdict


@dataclass
class Fingerprint:
    """A technology fingerprint - evidence pointing to specific tools."""
    technology: str
    category: str  # database, framework, language, tool
    confidence: float
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "technology": self.technology,
            "category": self.category,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


class TechFingerprinter:
    """
    Map artifact patterns to likely technologies.
    
    This is pattern matching - certain artifact combinations
    are strong indicators of specific tools.
    """
    
    # Artifact patterns -> technology mappings
    PATTERNS = {
        # Databases
        "MONGODB_EXPORT": {
            "technology": "MongoDB",
            "category": "database",
            "weight": 0.9,
        },
        "ORM_GENERATED_SCHEMA": {
            "technology": "ORM (Django/Rails/SQLAlchemy)",
            "category": "framework",
            "weight": 0.7,
        },
        "PANDAS_CSV_EXPORT": {
            "technology": "Pandas",
            "category": "tool",
            "weight": 0.95,
        },
        
        # Processing tools
        "LOWERCASE_NORMALIZATION": {
            "technology": "Text Preprocessing",
            "category": "processing",
            "weight": 0.6,
        },
        "WHITESPACE_TRIM": {
            "technology": "String Cleaning",
            "category": "processing",
            "weight": 0.5,
        },
        
        # Batch processing
        "BATCH_HOURLY": {
            "technology": "Scheduled Batch Job (hourly)",
            "category": "infrastructure",
            "weight": 0.8,
        },
        "BATCH_15MIN": {
            "technology": "Scheduled Batch Job (15min)",
            "category": "infrastructure",
            "weight": 0.8,
        },
        "BATCH_BURST_PROCESSING": {
            "technology": "Event-Driven Batch Processing",
            "category": "infrastructure",
            "weight": 0.7,
        },
        "SCHEDULED_JOB": {
            "technology": "Cron/Scheduler",
            "category": "infrastructure",
            "weight": 0.75,
        },
        
        # ID generation
        "UUID_GENERATION_V4": {
            "technology": "Cryptographic UUID Generator",
            "category": "tool",
            "weight": 0.8,
        },
        "UUID_GENERATION_V1": {
            "technology": "Time-based UUID (leaks timestamp + MAC)",
            "category": "tool",
            "weight": 0.85,
        },
        "DETERMINISTIC_ID_GENERATION_SHA256": {
            "technology": "Content-Addressed Storage",
            "category": "architecture",
            "weight": 0.8,
        },
        "DETERMINISTIC_ID_GENERATION_MD5": {
            "technology": "MD5 Hash IDs (legacy system)",
            "category": "architecture",
            "weight": 0.8,
        },
        
        # Data quality
        "FILTERING_OR_DELETION": {
            "technology": "Record Filtering/Deletion Pipeline",
            "category": "processing",
            "weight": 0.7,
        },
        "CHARSET_CONVERSION_ERROR": {
            "technology": "Encoding Mismatch (Latin-1 vs UTF-8)",
            "category": "bug",
            "weight": 0.85,
        },
        
        # Languages/frameworks
        "PYTHON_OR_SQL_ORIGIN": {
            "technology": "Python or SQL",
            "category": "language",
            "weight": 0.6,
        },
        "JAVASCRIPT_OR_JAVA_ORIGIN": {
            "technology": "JavaScript or Java",
            "category": "language",
            "weight": 0.6,
        },
        
        # Source merging
        "MERGED_SOURCES": {
            "technology": "Multi-Source Data Integration",
            "category": "architecture",
            "weight": 0.8,
        },
        "MULTI_SOURCE_MERGE": {
            "technology": "Multi-Source Data Integration",
            "category": "architecture",
            "weight": 0.85,
        },
    }
    
    # Compound patterns - combinations that strengthen identification
    COMPOUND_PATTERNS = [
        {
            "requires": ["PANDAS_CSV_EXPORT", "PYTHON_OR_SQL_ORIGIN"],
            "suggests": Fingerprint("Pandas Data Pipeline", "tool", 0.95),
        },
        {
            "requires": ["MONGODB_EXPORT", "JAVASCRIPT_OR_JAVA_ORIGIN"],
            "suggests": Fingerprint("Node.js + MongoDB Stack", "stack", 0.85),
        },
        {
            "requires": ["ORM_GENERATED_SCHEMA", "BATCH_HOURLY"],
            "suggests": Fingerprint("Django/Rails Batch Worker", "stack", 0.80),
        },
        {
            "requires": ["CHARSET_CONVERSION_ERROR", "MERGED_SOURCES"],
            "suggests": Fingerprint("Legacy System Migration", "context", 0.85),
        },
        {
            "requires": ["UUID_GENERATION_V1", "BATCH_BURST_PROCESSING"],
            "suggests": Fingerprint("Distributed System (pre-2015 design)", "architecture", 0.75),
        },
    ]
    
    def __init__(self):
        self.fingerprints: List[Fingerprint] = []
    
    def analyze(self, artifacts: List['Artifact']) -> List[Fingerprint]:
        """
        Analyze artifacts and return technology fingerprints.
        
        Args:
            artifacts: List of detected artifacts
            
        Returns:
            List of technology fingerprints sorted by confidence
        """
        self.fingerprints = []
        
        # Get all inferred operations
        operations = set(a.inferred_operation for a in artifacts)
        
        # Match against patterns
        tech_evidence = defaultdict(list)
        tech_confidence = defaultdict(float)
        tech_category = {}
        
        for op in operations:
            # Direct pattern match
            if op in self.PATTERNS:
                pattern = self.PATTERNS[op]
                tech = pattern["technology"]
                tech_evidence[tech].append(op)
                tech_confidence[tech] = max(tech_confidence[tech], pattern["weight"])
                tech_category[tech] = pattern["category"]
            
            # Partial match (for patterns with suffixes like SCHEDULED_JOB_24HR)
            for pattern_name, pattern in self.PATTERNS.items():
                if op.startswith(pattern_name.split('_')[0] + '_'):
                    tech = pattern["technology"]
                    if tech not in tech_evidence or op not in tech_evidence[tech]:
                        tech_evidence[tech].append(op)
                        tech_confidence[tech] = max(tech_confidence[tech], pattern["weight"] * 0.9)
                        tech_category[tech] = pattern["category"]
        
        # Check compound patterns
        for compound in self.COMPOUND_PATTERNS:
            required = set(compound["requires"])
            if required.issubset(operations):
                fp = compound["suggests"]
                tech_evidence[fp.technology].extend(list(required))
                tech_confidence[fp.technology] = max(tech_confidence.get(fp.technology, 0), fp.confidence)
                tech_category[fp.technology] = fp.category
        
        # Build fingerprint objects
        for tech, evidence in tech_evidence.items():
            self.fingerprints.append(Fingerprint(
                technology=tech,
                category=tech_category.get(tech, "unknown"),
                confidence=tech_confidence[tech],
                evidence=list(set(evidence)),
            ))
        
        # Sort by confidence
        self.fingerprints.sort(key=lambda f: f.confidence, reverse=True)
        
        return self.fingerprints
    
    def get_likely_stack(self) -> Dict[str, Any]:
        """
        Synthesize fingerprints into a likely technology stack.
        
        Returns:
            Dict describing the probable system architecture
        """
        if not self.fingerprints:
            return {"stack": "Unknown", "components": []}
        
        # Group by category
        by_category = defaultdict(list)
        for fp in self.fingerprints:
            by_category[fp.category].append(fp)
        
        stack = {
            "database": None,
            "framework": None,
            "language": None,
            "processing": [],
            "infrastructure": [],
            "architecture_notes": [],
        }
        
        # Pick highest confidence for single-value categories
        for cat in ["database", "framework", "language"]:
            if cat in by_category:
                stack[cat] = by_category[cat][0].technology
        
        # Aggregate list categories
        for cat in ["processing", "infrastructure"]:
            if cat in by_category:
                stack[cat] = [fp.technology for fp in by_category[cat]]
        
        # Architecture notes from high-confidence findings
        if "architecture" in by_category:
            stack["architecture_notes"] = [fp.technology for fp in by_category["architecture"]]
        
        # Bugs/issues
        if "bug" in by_category:
            stack["issues"] = [fp.technology for fp in by_category["bug"]]
        
        return stack
    
    def get_security_concerns(self) -> List[Dict[str, Any]]:
        """
        Identify security-relevant findings.
        
        Returns:
            List of security concerns derived from fingerprints
        """
        concerns = []
        
        for fp in self.fingerprints:
            # UUID v1 leaks info
            if "UUID" in fp.technology and "V1" in fp.technology:
                concerns.append({
                    "severity": "medium",
                    "issue": "UUID v1 leaks timestamp and MAC address",
                    "evidence": fp.evidence,
                    "recommendation": "Use UUID v4 for privacy",
                })
            
            # MD5 for IDs
            if "MD5" in fp.technology:
                concerns.append({
                    "severity": "low",
                    "issue": "MD5 used for ID generation (collision risk)",
                    "evidence": fp.evidence,
                    "recommendation": "Consider SHA-256 for content addressing",
                })
            
            # Encoding errors = data loss
            if "Encoding" in fp.technology or "charset" in fp.technology.lower():
                concerns.append({
                    "severity": "medium",
                    "issue": "Character encoding errors indicate data corruption",
                    "evidence": fp.evidence,
                    "recommendation": "Audit data pipeline for charset handling",
                })
            
            # Legacy patterns
            if "legacy" in fp.technology.lower() or "pre-2015" in fp.technology.lower():
                concerns.append({
                    "severity": "info",
                    "issue": "Legacy system patterns detected",
                    "evidence": fp.evidence,
                    "recommendation": "Review for technical debt",
                })
        
        return concerns
