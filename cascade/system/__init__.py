"""
CASCADE System Observatory - Universal Log Visualization

Parse logs from ANY system and visualize them in CASCADE's state-space topology.
Systems produce logs. CASCADE reveals their soul.

Causation is derived from explicit parent_hash chains in the data - 
no inference or ML models needed. Your forensics pipeline builds the chains,
System Observatory just reads and visualizes them.

Supported formats (all handled by UniversalAdapter):
- JSON/JSONL at any nesting depth
- Apache/Nginx access logs
- Kubernetes events
- Syslog format
- Generic timestamped logs
- Custom regex patterns
- ANY format with timestamps and messages

Supported file types (via file_extractors):
- Text: .log, .txt, .json, .jsonl, .xml, .yaml
- Tabular: .csv, .tsv, .parquet, .xlsx
- Compressed: .gz, .zip, .tar, .tar.gz, .bz2
- Documents: .pdf
- Databases: .sqlite, .db
- Binary: .evtx (Windows Event Log)
"""

from cascade.system.adapter import (
    LogAdapter,
    UniversalAdapter,  # The one adapter to rule them all
    JSONLAdapter,
    ApacheLogAdapter,
    NginxLogAdapter,
    KubernetesLogAdapter,
    GenericLogAdapter,
    RegexAdapter,
    auto_detect_adapter,
    detect_data_type,  # Detect logs vs dataset
)

from cascade.system.observer import (
    SystemObserver,
    observe_log_file,
    observe_log_stream,
)

from cascade.system.file_extractors import (
    extract_from_file,
    extract_from_bytes,
    get_extractor_for_file,
    get_supported_extensions,
    get_supported_formats,
    ExtractionResult,
    # Individual extractors
    TextExtractor,
    JSONExtractor,
    CSVExtractor,
    ParquetExtractor,
    ExcelExtractor,
    PDFExtractor,
    XMLExtractor,
    YAMLExtractor,
    GzipExtractor,
    ZipExtractor,
    TarExtractor,
    SQLiteExtractor,
)

# ═══════════════════════════════════════════════════════════════════════════════
# MoE Analyzer - DEPRECATED
# Kept for backwards compatibility but not used by System Observatory.
# Causation is now derived directly from parent_hash chains in the data.
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from cascade.system.moe_analyzer import (
        MoEAnalyzer,
        MoEAnalysisResult,
        SystemClassifier,
        TopologyClassification,
        SystemTopology,
        BaseSpecialist,
        MLTrainingSpecialist,
        WebServiceSpecialist,
        MicroservicesSpecialist,
        GenericSpecialist,
        AnalysisInsight,
        SpecialistAnalysis,
    )
    _MOE_AVAILABLE = True
except ImportError:
    _MOE_AVAILABLE = False

__all__ = [
    # Adapters
    "LogAdapter",
    "UniversalAdapter",  # Future-proof default
    "JSONLAdapter", 
    "ApacheLogAdapter",
    "NginxLogAdapter",
    "KubernetesLogAdapter",
    "GenericLogAdapter",
    "RegexAdapter",
    "auto_detect_adapter",
    "detect_data_type",  # Logs vs dataset detection
    # Observer
    "SystemObserver",
    "observe_log_file",
    "observe_log_stream",
    # File Extractors
    "extract_from_file",
    "extract_from_bytes",
    "get_extractor_for_file",
    "get_supported_extensions",
    "get_supported_formats",
    "ExtractionResult",
    "TextExtractor",
    "JSONExtractor",
    "CSVExtractor",
    "ParquetExtractor",
    "ExcelExtractor",
    "PDFExtractor",
    "XMLExtractor",
    "YAMLExtractor",
    "GzipExtractor",
    "ZipExtractor",
    "TarExtractor",
    "SQLiteExtractor",
]

# Add MoE exports only if available (deprecated but kept for compatibility)
if _MOE_AVAILABLE:
    __all__.extend([
        "MoEAnalyzer",
        "MoEAnalysisResult",
        "SystemClassifier",
        "TopologyClassification",
        "SystemTopology",
        "BaseSpecialist",
        "MLTrainingSpecialist",
        "WebServiceSpecialist",
        "MicroservicesSpecialist",
        "GenericSpecialist",
        "AnalysisInsight",
        "SpecialistAnalysis",
    ])
