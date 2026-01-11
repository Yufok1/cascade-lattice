"""
CASCADE Forensics - Read the Ghost in the Data

Every dataset is a confession. It remembers what happened to it.
This module reads those memories.

GHOST LOG: Inferred processing history from data artifacts
SKELETON: Probable system architecture
DNA: Technology fingerprints
SOUL: Behavioral predictions

Usage:
    from cascade.forensics import DataForensics
    
    forensics = DataForensics()
    report = forensics.analyze(dataframe)
    
    print(report.ghost_log)      # Inferred operations
    print(report.skeleton)       # System architecture
    print(report.fingerprints)   # Technology hints
"""

from cascade.forensics.analyzer import (
    DataForensics,
    ForensicsReport,
    GhostLog,
    InferredOperation,
)

from cascade.forensics.artifacts import (
    ArtifactDetector,
    TimestampArtifacts,
    IDPatternArtifacts,
    TextArtifacts,
    NumericArtifacts,
    NullPatternArtifacts,
    SchemaArtifacts,
)

from cascade.forensics.fingerprints import (
    TechFingerprinter,
    Fingerprint,
)

__all__ = [
    "DataForensics",
    "ForensicsReport",
    "GhostLog",
    "InferredOperation",
    "ArtifactDetector",
    "TechFingerprinter",
    "Fingerprint",
]
