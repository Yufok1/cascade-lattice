"""
PROV-O Entities for Dataset Observation

W3C PROV Data Model:
- Entity: A physical, digital, or conceptual thing (the dataset)
- Activity: Something that occurs over time and acts upon entities
- Agent: Something that bears responsibility for an activity

Relationships:
- wasGeneratedBy: Entity → Activity
- wasDerivedFrom: Entity → Entity
- wasAttributedTo: Entity → Agent
- used: Activity → Entity
- wasAssociatedWith: Activity → Agent
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class RelationType(Enum):
    """W3C PROV-O relationship types."""
    # Entity relationships
    WAS_GENERATED_BY = "wasGeneratedBy"      # Entity → Activity
    WAS_DERIVED_FROM = "wasDerivedFrom"      # Entity → Entity
    WAS_ATTRIBUTED_TO = "wasAttributedTo"    # Entity → Agent
    WAS_REVISION_OF = "wasRevisionOf"        # Entity → Entity (versioning)
    HAD_PRIMARY_SOURCE = "hadPrimarySource"  # Entity → Entity
    
    # Activity relationships
    USED = "used"                            # Activity → Entity
    WAS_ASSOCIATED_WITH = "wasAssociatedWith"  # Activity → Agent
    WAS_INFORMED_BY = "wasInformedBy"        # Activity → Activity
    WAS_STARTED_BY = "wasStartedBy"          # Activity → Entity
    WAS_ENDED_BY = "wasEndedBy"              # Activity → Entity
    
    # Agent relationships
    ACTED_ON_BEHALF_OF = "actedOnBehalfOf"   # Agent → Agent


@dataclass
class Relationship:
    """A provenance relationship between two nodes."""
    relation_type: RelationType
    source_id: str
    target_id: str
    timestamp: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.relation_type.value,
            "source": self.source_id,
            "target": self.target_id,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
        }
    
    def to_prov_n(self) -> str:
        """Export as PROV-N notation."""
        return f"{self.relation_type.value}({self.source_id}, {self.target_id})"


@dataclass
class DatasetEntity:
    """
    A dataset entity in the provenance graph.
    
    Corresponds to prov:Entity - any physical, digital, or conceptual thing.
    In our case: a dataset, a version of a dataset, or a split.
    """
    id: str
    name: str
    
    # Content identification
    content_hash: Optional[str] = None  # SHA-256 of data content
    schema_hash: Optional[str] = None   # SHA-256 of schema/features
    
    # Versioning
    version: Optional[str] = None
    previous_version: Optional[str] = None
    
    # Source
    source_type: str = "unknown"  # hf_hub, local, s3, gcs, etc.
    source_uri: Optional[str] = None
    
    # License (SPDX identifier)
    license_id: Optional[str] = None    # e.g., "MIT", "CC-BY-4.0", "Apache-2.0"
    license_url: Optional[str] = None   # URL to license text
    
    # Statistics
    record_count: Optional[int] = None
    size_bytes: Optional[int] = None
    splits: Dict[str, int] = field(default_factory=dict)  # split_name → count
    
    # Metadata
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            self.id = f"entity:{self.name}:{int(self.created_at * 1000)}"
    
    def compute_hash(self) -> str:
        """Compute entity hash from content."""
        content = json.dumps({
            "id": self.id,
            "name": self.name,
            "content_hash": self.content_hash,
            "schema_hash": self.schema_hash,
            "version": self.version,
            "record_count": self.record_count,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "@type": "prov:Entity",
            "@id": self.id,
            "name": self.name,
            "content_hash": self.content_hash,
            "schema_hash": self.schema_hash,
            "version": self.version,
            "previous_version": self.previous_version,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "license_id": self.license_id,
            "license_url": self.license_url,
            "record_count": self.record_count,
            "size_bytes": self.size_bytes,
            "splits": self.splits,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }
    
    def to_prov_n(self) -> str:
        """Export as PROV-N notation."""
        attrs = ", ".join([
            f'prov:label="{self.name}"',
            f'cascade:contentHash="{self.content_hash or "unknown"}"',
            f'cascade:recordCount="{self.record_count or 0}"',
            f'cascade:license="{self.license_id or "unknown"}"',
        ])
        return f"entity({self.id}, [{attrs}])"


class ActivityType(Enum):
    """Types of dataset activities."""
    INGEST = "ingest"           # Load from source
    TRANSFORM = "transform"     # Filter, map, join, etc.
    SPLIT = "split"             # Train/test/val split
    AUGMENT = "augment"         # Data augmentation
    CLEAN = "clean"             # Cleaning/preprocessing
    MERGE = "merge"             # Combining datasets
    SAMPLE = "sample"           # Sampling/subsetting
    EXPORT = "export"           # Export to format
    TRAIN = "train"             # Model training (consumption)
    EVALUATE = "evaluate"       # Model evaluation
    INFERENCE = "inference"     # Model inference
    ENTITY_RESOLUTION = "entity_resolution"  # Data Unity matching


@dataclass
class Activity:
    """
    An activity in the provenance graph.
    
    Corresponds to prov:Activity - something that occurs over time
    and acts upon or with entities.
    """
    id: str
    activity_type: ActivityType
    name: str
    
    # Timing
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    
    # Input/Output tracking
    inputs: List[str] = field(default_factory=list)   # Entity IDs
    outputs: List[str] = field(default_factory=list)  # Entity IDs
    
    # Agent who performed this
    agent_id: Optional[str] = None
    
    # Parameters/configuration used
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = f"activity:{self.activity_type.value}:{int(time.time() * 1000)}"
        if self.started_at is None:
            self.started_at = time.time()
    
    def start(self):
        """Mark activity as started."""
        self.started_at = time.time()
    
    def end(self):
        """Mark activity as ended."""
        self.ended_at = time.time()
    
    @property
    def duration(self) -> Optional[float]:
        """Duration in seconds."""
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return None
    
    def add_input(self, entity_id: str):
        """Record an input entity."""
        if entity_id not in self.inputs:
            self.inputs.append(entity_id)
    
    def add_output(self, entity_id: str):
        """Record an output entity."""
        if entity_id not in self.outputs:
            self.outputs.append(entity_id)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "@type": "prov:Activity",
            "@id": self.id,
            "activity_type": self.activity_type.value,
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": self.duration,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "agent_id": self.agent_id,
            "parameters": self.parameters,
            "attributes": self.attributes,
        }
    
    def to_prov_n(self) -> str:
        """Export as PROV-N notation."""
        start = datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else "-"
        end = datetime.fromtimestamp(self.ended_at).isoformat() if self.ended_at else "-"
        attrs = f'prov:label="{self.name}", cascade:type="{self.activity_type.value}"'
        return f"activity({self.id}, {start}, {end}, [{attrs}])"


class AgentType(Enum):
    """Types of agents."""
    PERSON = "person"
    ORGANIZATION = "organization"
    SOFTWARE = "software"
    MODEL = "model"
    PIPELINE = "pipeline"
    SYSTEM = "system"


@dataclass
class Agent:
    """
    An agent in the provenance graph.
    
    Corresponds to prov:Agent - something that bears responsibility
    for an activity taking place.
    """
    id: str
    agent_type: AgentType
    name: str
    
    # For software/model agents
    version: Optional[str] = None
    
    # For organizational hierarchy
    parent_agent_id: Optional[str] = None
    
    # Contact/identification
    identifier: Optional[str] = None  # HF username, email, etc.
    
    # Metadata
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamp
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if not self.id:
            self.id = f"agent:{self.agent_type.value}:{self.name}".replace(" ", "_").lower()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "@type": "prov:Agent",
            "@id": self.id,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "version": self.version,
            "parent_agent_id": self.parent_agent_id,
            "identifier": self.identifier,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }
    
    def to_prov_n(self) -> str:
        """Export as PROV-N notation."""
        attrs = f'prov:label="{self.name}", cascade:type="{self.agent_type.value}"'
        if self.version:
            attrs += f', cascade:version="{self.version}"'
        return f"agent({self.id}, [{attrs}])"


# Convenience factory functions
def create_system_agent(name: str = "cascade", version: str = "1.0.0") -> Agent:
    """Create a system agent for automated operations."""
    return Agent(
        id=f"agent:system:{name}",
        agent_type=AgentType.SYSTEM,
        name=name,
        version=version,
    )


def create_model_agent(model_id: str, version: str = None) -> Agent:
    """Create an agent representing an ML model."""
    return Agent(
        id=f"agent:model:{model_id.replace('/', '_')}",
        agent_type=AgentType.MODEL,
        name=model_id,
        version=version,
        identifier=model_id,
    )


def create_user_agent(username: str, org: str = None) -> Agent:
    """Create an agent representing a user."""
    agent = Agent(
        id=f"agent:person:{username}",
        agent_type=AgentType.PERSON,
        name=username,
        identifier=username,
    )
    if org:
        agent.parent_agent_id = f"agent:organization:{org}"
    return agent
