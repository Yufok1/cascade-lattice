"""
CASCADE Data Observatory

Dataset observation with the same rigor as model observation.
Tracks provenance, schema, lineage using W3C PROV-O standard.
"""

from .entities import (
    DatasetEntity,
    Activity,
    Agent,
    Relationship,
    RelationType,
    ActivityType,
    AgentType,
    create_system_agent,
    create_model_agent,
    create_user_agent,
)
from .observer import DatasetObserver, ObservationContext
from .provenance import ProvenanceGraph
from .schema import SchemaObserver, DatasetSchema, FieldSchema, hash_content
from .croissant import CroissantExporter, export_to_croissant
from .hub import HubIntegration, AccountabilityBundle, push_to_hub, pull_from_hub
from .license import (
    SPDXLicense,
    LicenseCategory,
    LicenseRestriction,
    LicenseCompatibility,
    LicenseAnalyzer,
    SPDX_LICENSES,
    get_license,
    check_license_compatibility,
    get_derived_license,
)
from .pii import (
    PIIType,
    PIISeverity,
    PIIMatch,
    PIIScanResult,
    PIIScanner,
    scan_for_pii,
    quick_pii_check,
)
from .live import (
    LiveDocumentTracer,
    TraceEvent,
    TraceEventType,
    DocumentSpan,
    DocumentAssociation,
    ConsoleTraceRenderer,
    create_live_tracer,
)

__all__ = [
    # Entities (PROV-O)
    "DatasetEntity",
    "Activity",
    "Agent",
    "Relationship",
    "RelationType",
    "ActivityType",
    "AgentType",
    "create_system_agent",
    "create_model_agent",
    "create_user_agent",
    # Observer
    "DatasetObserver",
    "ObservationContext",
    # Provenance
    "ProvenanceGraph",
    # Schema
    "SchemaObserver",
    "DatasetSchema",
    "FieldSchema",
    "hash_content",
    # Export
    "CroissantExporter",
    "export_to_croissant",
    # Accountability
    "AccountabilityBundle",
    # Hub
    "HubIntegration",
    "push_to_hub",
    "pull_from_hub",
    # License
    "SPDXLicense",
    "LicenseCategory",
    "LicenseRestriction",
    "LicenseCompatibility",
    "LicenseAnalyzer",
    "SPDX_LICENSES",
    "get_license",
    "check_license_compatibility",
    "get_derived_license",
    # PII Detection
    "PIIType",
    "PIISeverity",
    "PIIMatch",
    "PIIScanResult",
    "PIIScanner",
    "scan_for_pii",
    "quick_pii_check",
    # Live Document Tracing
    "LiveDocumentTracer",
    "TraceEvent",
    "TraceEventType",
    "DocumentSpan",
    "DocumentAssociation",
    "ConsoleTraceRenderer",
    "create_live_tracer",
]
