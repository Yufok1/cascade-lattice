"""
Provenance Graph

Tracks entities, activities, agents, and their relationships.
Supports Merkle tree hashing for tamper-evident lineage.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Iterator

from .entities import (
    DatasetEntity, Activity, Agent, Relationship, RelationType,
    ActivityType, AgentType, create_system_agent
)


@dataclass
class ProvenanceNode:
    """A node in the provenance graph with hash chain."""
    node_id: str
    node_type: str  # entity, activity, agent
    data: Dict[str, Any]
    
    # Hash chain
    node_hash: str = ""
    parent_hashes: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.node_hash:
            self.node_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute hash including parent hashes (Merkle-style)."""
        content = json.dumps({
            "id": self.node_id,
            "type": self.node_type,
            "data": self.data,
            "parents": sorted(self.parent_hashes),
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()


class ProvenanceGraph:
    """
    A graph of provenance relationships.
    
    Tracks:
    - Entities (datasets, versions, splits)
    - Activities (transforms, training, inference)
    - Agents (users, models, pipelines)
    - Relationships between them
    
    Provides:
    - Lineage queries (what produced this? what did this produce?)
    - Hash chain for integrity verification
    - Export to PROV-O and Croissant formats
    """
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.created_at = time.time()
        
        # Storage
        self._entities: Dict[str, DatasetEntity] = {}
        self._activities: Dict[str, Activity] = {}
        self._agents: Dict[str, Agent] = {}
        self._relationships: List[Relationship] = []
        
        # Hash chain
        self._nodes: Dict[str, ProvenanceNode] = {}
        self._root_hash: Optional[str] = None
        
        # Default system agent
        self._system_agent = create_system_agent("cascade-data-observatory")
        self.add_agent(self._system_agent)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ENTITY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_entity(self, entity: DatasetEntity) -> str:
        """Add a dataset entity to the graph."""
        self._entities[entity.id] = entity
        
        # Create provenance node
        node = ProvenanceNode(
            node_id=entity.id,
            node_type="entity",
            data=entity.to_dict(),
        )
        self._nodes[entity.id] = node
        self._update_root_hash()
        
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[DatasetEntity]:
        """Get entity by ID."""
        return self._entities.get(entity_id)
    
    def list_entities(self) -> List[DatasetEntity]:
        """List all entities."""
        return list(self._entities.values())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACTIVITY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_activity(self, activity: Activity) -> str:
        """Add an activity to the graph."""
        self._activities[activity.id] = activity
        
        # Link to agent
        if not activity.agent_id:
            activity.agent_id = self._system_agent.id
        
        # Create provenance node with parent hashes from inputs
        parent_hashes = []
        for input_id in activity.inputs:
            if input_id in self._nodes:
                parent_hashes.append(self._nodes[input_id].node_hash)
        
        node = ProvenanceNode(
            node_id=activity.id,
            node_type="activity",
            data=activity.to_dict(),
            parent_hashes=parent_hashes,
        )
        self._nodes[activity.id] = node
        self._update_root_hash()
        
        return activity.id
    
    def get_activity(self, activity_id: str) -> Optional[Activity]:
        """Get activity by ID."""
        return self._activities.get(activity_id)
    
    def list_activities(self) -> List[Activity]:
        """List all activities."""
        return list(self._activities.values())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AGENT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_agent(self, agent: Agent) -> str:
        """Add an agent to the graph."""
        self._agents[agent.id] = agent
        
        node = ProvenanceNode(
            node_id=agent.id,
            node_type="agent",
            data=agent.to_dict(),
        )
        self._nodes[agent.id] = node
        
        return agent.id
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> List[Agent]:
        """List all agents."""
        return list(self._agents.values())
    
    def list_relationships(self) -> List[Relationship]:
        """List all relationships."""
        return list(self._relationships)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RELATIONSHIP MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_relationship(
        self,
        relation_type: RelationType,
        source_id: str,
        target_id: str,
        attributes: Dict[str, Any] = None,
        timestamp: float = None,
    ) -> Relationship:
        """Add a relationship between nodes."""
        rel = Relationship(
            relation_type=relation_type,
            source_id=source_id,
            target_id=target_id,
            timestamp=timestamp if timestamp is not None else time.time(),
            attributes=attributes or {},
        )
        self._relationships.append(rel)
        return rel
    
    def link_derivation(self, derived_id: str, source_id: str) -> Relationship:
        """Record that derived entity came from source entity."""
        return self.add_relationship(
            RelationType.WAS_DERIVED_FROM,
            source_id=derived_id,
            target_id=source_id,
        )
    
    def link_generation(self, entity_id: str, activity_id: str) -> Relationship:
        """Record that entity was generated by activity."""
        return self.add_relationship(
            RelationType.WAS_GENERATED_BY,
            source_id=entity_id,
            target_id=activity_id,
        )
    
    def link_usage(self, activity_id: str, entity_id: str) -> Relationship:
        """Record that activity used entity as input."""
        return self.add_relationship(
            RelationType.USED,
            source_id=activity_id,
            target_id=entity_id,
        )
    
    def link_attribution(self, entity_id: str, agent_id: str) -> Relationship:
        """Record that entity was attributed to agent."""
        return self.add_relationship(
            RelationType.WAS_ATTRIBUTED_TO,
            source_id=entity_id,
            target_id=agent_id,
        )
    
    def link_association(self, activity_id: str, agent_id: str) -> Relationship:
        """Record that activity was associated with agent."""
        return self.add_relationship(
            RelationType.WAS_ASSOCIATED_WITH,
            source_id=activity_id,
            target_id=agent_id,
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LINEAGE QUERIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_lineage(self, entity_id: str, direction: str = "upstream") -> List[str]:
        """
        Get lineage for an entity.
        
        Args:
            entity_id: The entity to trace
            direction: "upstream" (what produced this) or "downstream" (what this produced)
        
        Returns:
            List of entity IDs in lineage order
        """
        visited: Set[str] = set()
        lineage: List[str] = []
        
        def trace(current_id: str):
            if current_id in visited:
                return
            visited.add(current_id)
            
            for rel in self._relationships:
                if direction == "upstream":
                    # Follow wasDerivedFrom backwards
                    if rel.relation_type == RelationType.WAS_DERIVED_FROM:
                        if rel.source_id == current_id:
                            lineage.append(rel.target_id)
                            trace(rel.target_id)
                else:
                    # Follow wasDerivedFrom forwards
                    if rel.relation_type == RelationType.WAS_DERIVED_FROM:
                        if rel.target_id == current_id:
                            lineage.append(rel.source_id)
                            trace(rel.source_id)
        
        trace(entity_id)
        return lineage
    
    def get_activities_for_entity(self, entity_id: str) -> List[Activity]:
        """Get activities that generated or used this entity."""
        activity_ids = set()
        
        for rel in self._relationships:
            if rel.relation_type == RelationType.WAS_GENERATED_BY:
                if rel.source_id == entity_id:
                    activity_ids.add(rel.target_id)
            elif rel.relation_type == RelationType.USED:
                if rel.target_id == entity_id:
                    activity_ids.add(rel.source_id)
        
        return [self._activities[aid] for aid in activity_ids if aid in self._activities]
    
    def get_inputs_for_activity(self, activity_id: str) -> List[DatasetEntity]:
        """Get entities that were inputs to an activity."""
        entity_ids = set()
        
        for rel in self._relationships:
            if rel.relation_type == RelationType.USED:
                if rel.source_id == activity_id:
                    entity_ids.add(rel.target_id)
        
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]
    
    def get_outputs_for_activity(self, activity_id: str) -> List[DatasetEntity]:
        """Get entities that were outputs of an activity."""
        entity_ids = set()
        
        for rel in self._relationships:
            if rel.relation_type == RelationType.WAS_GENERATED_BY:
                if rel.target_id == activity_id:
                    entity_ids.add(rel.source_id)
        
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HASH CHAIN
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _update_root_hash(self):
        """Update the Merkle root hash."""
        if not self._nodes:
            self._root_hash = None
            return
        
        # Compute root from all node hashes
        all_hashes = sorted([n.node_hash for n in self._nodes.values()])
        combined = "".join(all_hashes)
        self._root_hash = hashlib.sha256(combined.encode()).hexdigest()
    
    @property
    def root_hash(self) -> Optional[str]:
        """Get the current Merkle root hash."""
        return self._root_hash
    
    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """
        Verify integrity of the provenance graph.
        
        Returns:
            (is_valid, list of invalid node IDs)
        """
        invalid = []
        
        for node_id, node in self._nodes.items():
            expected_hash = node._compute_hash()
            if expected_hash != node.node_hash:
                invalid.append(node_id)
        
        return len(invalid) == 0, invalid
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary."""
        return {
            "name": self.name,
            "created_at": self.created_at,
            "root_hash": self._root_hash,
            "entities": {k: v.to_dict() for k, v in self._entities.items()},
            "activities": {k: v.to_dict() for k, v in self._activities.items()},
            "agents": {k: v.to_dict() for k, v in self._agents.items()},
            "relationships": [r.to_dict() for r in self._relationships],
        }
    
    def to_prov_n(self) -> str:
        """Export as PROV-N notation."""
        lines = [
            f"document",
            f"  prefix cascade <https://cascade.ai/ns/>",
            f"  prefix prov <http://www.w3.org/ns/prov#>",
            f"",
        ]
        
        # Entities
        for entity in self._entities.values():
            lines.append(f"  {entity.to_prov_n()}")
        
        lines.append("")
        
        # Activities
        for activity in self._activities.values():
            lines.append(f"  {activity.to_prov_n()}")
        
        lines.append("")
        
        # Agents
        for agent in self._agents.values():
            lines.append(f"  {agent.to_prov_n()}")
        
        lines.append("")
        
        # Relationships
        for rel in self._relationships:
            lines.append(f"  {rel.to_prov_n()}")
        
        lines.append("")
        lines.append("endDocument")
        
        return "\n".join(lines)
    
    def to_prov_jsonld(self) -> Dict[str, Any]:
        """Export as PROV-O JSON-LD."""
        return {
            "@context": {
                "prov": "http://www.w3.org/ns/prov#",
                "cascade": "https://cascade.ai/ns/",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
            },
            "@graph": [
                *[e.to_dict() for e in self._entities.values()],
                *[a.to_dict() for a in self._activities.values()],
                *[a.to_dict() for a in self._agents.values()],
            ],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceGraph":
        """Load graph from dictionary."""
        graph = cls(name=data.get("name", "default"))
        graph.created_at = data.get("created_at", time.time())
        
        # Load entities
        for entity_data in data.get("entities", {}).values():
            entity = DatasetEntity(
                id=entity_data["@id"],
                name=entity_data["name"],
                content_hash=entity_data.get("content_hash"),
                schema_hash=entity_data.get("schema_hash"),
                version=entity_data.get("version"),
                previous_version=entity_data.get("previous_version"),
                source_type=entity_data.get("source_type", "unknown"),
                source_uri=entity_data.get("source_uri"),
                record_count=entity_data.get("record_count"),
                size_bytes=entity_data.get("size_bytes"),
                splits=entity_data.get("splits", {}),
                attributes=entity_data.get("attributes", {}),
                created_at=entity_data.get("created_at", time.time()),
            )
            graph.add_entity(entity)
        
        # Load activities
        for activity_data in data.get("activities", {}).values():
            activity = Activity(
                id=activity_data["@id"],
                activity_type=ActivityType(activity_data["activity_type"]),
                name=activity_data["name"],
                started_at=activity_data.get("started_at"),
                ended_at=activity_data.get("ended_at"),
                inputs=activity_data.get("inputs", []),
                outputs=activity_data.get("outputs", []),
                agent_id=activity_data.get("agent_id"),
                parameters=activity_data.get("parameters", {}),
                attributes=activity_data.get("attributes", {}),
            )
            graph.add_activity(activity)
        
        # Load agents
        for agent_data in data.get("agents", {}).values():
            agent = Agent(
                id=agent_data["@id"],
                agent_type=AgentType(agent_data["agent_type"]),
                name=agent_data["name"],
                version=agent_data.get("version"),
                parent_agent_id=agent_data.get("parent_agent_id"),
                identifier=agent_data.get("identifier"),
                attributes=agent_data.get("attributes", {}),
                created_at=agent_data.get("created_at", time.time()),
            )
            graph.add_agent(agent)
        
        # Load relationships
        for rel_data in data.get("relationships", []):
            graph.add_relationship(
                relation_type=RelationType(rel_data["type"]),
                source_id=rel_data["source"],
                target_id=rel_data["target"],
                attributes=rel_data.get("attributes", {}),
                timestamp=rel_data.get("timestamp"),
            )
        
        return graph
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get graph statistics."""
        return {
            "entities": len(self._entities),
            "activities": len(self._activities),
            "agents": len(self._agents),
            "relationships": len(self._relationships),
        }
    
    def __repr__(self) -> str:
        stats = self.stats
        return (
            f"ProvenanceGraph(name='{self.name}', "
            f"entities={stats['entities']}, "
            f"activities={stats['activities']}, "
            f"relationships={stats['relationships']})"
        )
