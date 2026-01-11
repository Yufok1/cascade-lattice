"""
Dataset Observer

The main interface for observing datasets.
Provides context managers for tracking ingest, transform, and consume operations.
"""

import hashlib
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional, Union

from .entities import (
    DatasetEntity, Activity, Agent, Relationship, RelationType,
    ActivityType, AgentType, create_system_agent, create_model_agent, create_user_agent
)
from .provenance import ProvenanceGraph
from .schema import SchemaObserver, DatasetSchema, hash_content


@dataclass
class ObservationContext:
    """
    Context for an ongoing observation.
    
    Used within context managers to track inputs/outputs.
    """
    activity: Activity
    observer: "DatasetObserver"
    
    _inputs: List[DatasetEntity] = field(default_factory=list)
    _outputs: List[DatasetEntity] = field(default_factory=list)
    
    def input(self, dataset, name: str = None, **kwargs) -> DatasetEntity:
        """
        Register an input dataset.
        
        Args:
            dataset: HuggingFace Dataset, DatasetDict, or entity ID
            name: Optional name override
            **kwargs: Additional entity attributes
        
        Returns:
            The created or retrieved DatasetEntity
        """
        # If string, assume it's an existing entity ID
        if isinstance(dataset, str):
            entity = self.observer.graph.get_entity(dataset)
            if entity:
                self._inputs.append(entity)
                self.activity.add_input(entity.id)
                self.observer.graph.link_usage(self.activity.id, entity.id)
                return entity
            else:
                raise ValueError(f"Entity not found: {dataset}")
        
        # Otherwise, observe the dataset
        entity = self.observer.observe_dataset(dataset, name=name, **kwargs)
        self._inputs.append(entity)
        self.activity.add_input(entity.id)
        self.observer.graph.link_usage(self.activity.id, entity.id)
        
        return entity
    
    def output(self, dataset, name: str = None, **kwargs) -> DatasetEntity:
        """
        Register an output dataset.
        
        Args:
            dataset: HuggingFace Dataset, DatasetDict, or dict
            name: Optional name override
            **kwargs: Additional entity attributes
        
        Returns:
            The created DatasetEntity
        """
        entity = self.observer.observe_dataset(dataset, name=name, **kwargs)
        self._outputs.append(entity)
        self.activity.add_output(entity.id)
        
        # Link generation
        self.observer.graph.link_generation(entity.id, self.activity.id)
        
        # Link derivation from all inputs
        for input_entity in self._inputs:
            self.observer.graph.link_derivation(entity.id, input_entity.id)
        
        return entity
    
    @property
    def inputs(self) -> List[DatasetEntity]:
        return self._inputs
    
    @property
    def outputs(self) -> List[DatasetEntity]:
        return self._outputs


class DatasetObserver:
    """
    Observer for dataset operations.
    
    Tracks:
    - Dataset loading (ingest)
    - Transformations (filter, map, join, etc.)
    - Consumption (training, inference)
    
    Example:
        observer = DatasetObserver()
        
        with observer.observe_ingest("squad") as ctx:
            ds = load_dataset("squad")
            ctx.output(ds)
        
        with observer.observe_transform("filter_english") as ctx:
            ctx.input(ds)
            filtered = ds.filter(lambda x: x["lang"] == "en")
            ctx.output(filtered)
        
        chain = observer.export_provenance()
    """
    
    def __init__(
        self,
        name: str = "default",
        agent: Agent = None,
    ):
        """
        Initialize observer.
        
        Args:
            name: Name for the provenance graph
            agent: Default agent for activities (defaults to graph's system agent)
        """
        self.graph = ProvenanceGraph(name=name)
        self.schema_observer = SchemaObserver()
        
        # Use provided agent or the graph's default system agent
        if agent:
            self._default_agent = agent
            self.graph.add_agent(agent)
        else:
            # Use the graph's already-created system agent
            self._default_agent = self.graph._system_agent
        
        # Entity counter for unique IDs
        self._counter = 0
    
    def _next_id(self, prefix: str) -> str:
        """Generate unique ID."""
        self._counter += 1
        return f"{prefix}:{int(time.time() * 1000)}:{self._counter:04d}"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATASET OBSERVATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def observe_dataset(
        self,
        dataset,
        name: str = None,
        source_type: str = None,
        source_uri: str = None,
        version: str = None,
        license_id: str = None,
        license_url: str = None,
        **kwargs,
    ) -> DatasetEntity:
        """
        Observe a dataset and create an entity.
        
        Args:
            dataset: HuggingFace Dataset, DatasetDict, DataFrame, or dict
            name: Name for the entity
            source_type: Type of source (hf_hub, local, etc.)
            source_uri: URI of the source
            version: Version string
            license_id: SPDX license identifier (e.g., "MIT", "CC-BY-4.0")
            license_url: URL to the license text
            **kwargs: Additional attributes
        
        Returns:
            DatasetEntity representing the dataset
        """
        # Infer name if not provided
        if name is None:
            if hasattr(dataset, 'info') and hasattr(dataset.info, 'dataset_name'):
                name = dataset.info.dataset_name
            elif hasattr(dataset, 'config_name'):
                name = dataset.config_name
            else:
                name = f"dataset_{self._counter + 1}"
        
        # Try to extract license from HuggingFace dataset info
        if license_id is None and hasattr(dataset, 'info'):
            info = dataset.info
            if hasattr(info, 'license') and info.license:
                license_id = info.license
        
        # Observe schema
        schema = self._observe_schema(dataset)
        
        # Compute content hash
        content_hash = self._compute_content_hash(dataset)
        
        # Get record count and splits
        record_count, splits = self._get_counts(dataset)
        
        # Infer source
        if source_type is None:
            source_type = self._infer_source_type(dataset)
        
        # Create entity
        entity = DatasetEntity(
            id=self._next_id("entity"),
            name=name,
            content_hash=content_hash,
            schema_hash=schema.hash() if schema else None,
            version=version,
            source_type=source_type,
            source_uri=source_uri,
            license_id=license_id,
            license_url=license_url,
            record_count=record_count,
            splits=splits,
            attributes={
                "schema": schema.to_dict() if schema else None,
                **kwargs,
            },
        )
        
        # Add to graph
        self.graph.add_entity(entity)
        
        return entity
    
    def register_agent(self, name: str, agent_type: str = "software", version: str = None) -> Agent:
        """
        Register a new agent in the provenance graph.
        
        Args:
            name: Name of the agent
            agent_type: Type of agent (software, model, person, etc.)
            version: Optional version string
            
        Returns:
            The created Agent
        """
        if agent_type == "model":
            agent = create_model_agent(name, version=version)
        elif agent_type == "system":
            agent = create_system_agent(name, version=version)
        elif agent_type == "person":
            agent = create_user_agent(name)
        else:
            # Default to software agent or generic
            try:
                type_enum = AgentType(agent_type)
            except ValueError:
                type_enum = AgentType.SOFTWARE
            
            agent = Agent(
                id=f"agent:{type_enum.value}:{name.replace(' ', '_').lower()}",
                agent_type=type_enum,
                name=name,
                version=version
            )
            
        self.graph.add_agent(agent)
        return agent
    
    def _observe_schema(self, dataset) -> Optional[DatasetSchema]:
        """Extract schema from dataset."""
        try:
            # HuggingFace Dataset
            if hasattr(dataset, 'features'):
                return self.schema_observer.observe_hf_dataset(dataset)
            
            # Pandas DataFrame
            if hasattr(dataset, 'dtypes') and hasattr(dataset, 'columns'):
                return self.schema_observer.observe_pandas(dataset)
            
            # Dict
            if isinstance(dataset, dict):
                # Check if it's columnar (dict of lists)
                if all(isinstance(v, list) for v in dataset.values()):
                    return self.schema_observer.observe_dict(dataset)
            
            return None
        except Exception as e:
            # Don't fail observation if schema extraction fails
            print(f"Warning: Could not extract schema: {e}")
            return None
    
    def _compute_content_hash(self, dataset) -> str:
        """Compute content hash of dataset."""
        try:
            return hash_content(dataset)
        except Exception:
            # Fallback to timestamp-based hash
            return hashlib.sha256(str(time.time()).encode()).hexdigest()
    
    def _get_counts(self, dataset) -> tuple:
        """Get record count and split counts."""
        record_count = None
        splits = {}
        
        try:
            # HuggingFace DatasetDict
            if hasattr(dataset, 'keys') and hasattr(dataset, '__getitem__'):
                for split_name in dataset.keys():
                    split_ds = dataset[split_name]
                    if hasattr(split_ds, '__len__'):
                        splits[split_name] = len(split_ds)
                record_count = sum(splits.values()) if splits else None
            
            # Single dataset
            elif hasattr(dataset, '__len__'):
                record_count = len(dataset)
            
        except Exception:
            pass
        
        return record_count, splits
    
    def _infer_source_type(self, dataset) -> str:
        """Infer source type from dataset."""
        # HuggingFace Dataset
        if hasattr(dataset, '_info'):
            return "hf_dataset"
        
        # Pandas
        if hasattr(dataset, 'dtypes'):
            return "pandas"
        
        # Dict
        if isinstance(dataset, dict):
            return "dict"
        
        return "unknown"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT MANAGERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @contextmanager
    def observe_ingest(
        self,
        name: str,
        source_uri: str = None,
        agent: Agent = None,
        **kwargs,
    ) -> Generator[ObservationContext, None, None]:
        """
        Observe a dataset ingest operation.
        
        Args:
            name: Name of the ingest operation
            source_uri: URI of the data source
            agent: Agent performing the ingest
            **kwargs: Additional activity parameters
        
        Yields:
            ObservationContext for registering inputs/outputs
        
        Example:
            with observer.observe_ingest("load_squad", source_uri="hf://squad") as ctx:
                ds = load_dataset("squad")
                ctx.output(ds, name="squad")
        """
        activity = Activity(
            id=self._next_id("activity"),
            activity_type=ActivityType.INGEST,
            name=name,
            agent_id=(agent or self._default_agent).id,
            parameters={"source_uri": source_uri, **kwargs},
        )
        activity.start()
        
        ctx = ObservationContext(activity=activity, observer=self)
        
        try:
            yield ctx
        finally:
            activity.end()
            self.graph.add_activity(activity)
            self.graph.link_association(activity.id, activity.agent_id)
    
    @contextmanager
    def observe_transform(
        self,
        name: str,
        transform_type: str = None,
        agent: Agent = None,
        **kwargs,
    ) -> Generator[ObservationContext, None, None]:
        """
        Observe a dataset transformation.
        
        Args:
            name: Name of the transform
            transform_type: Type of transform (filter, map, join, etc.)
            agent: Agent performing the transform
            **kwargs: Additional activity parameters
        
        Yields:
            ObservationContext for registering inputs/outputs
        
        Example:
            with observer.observe_transform("filter_english") as ctx:
                ctx.input(ds)
                filtered = ds.filter(lambda x: x["lang"] == "en")
                ctx.output(filtered)
        """
        activity = Activity(
            id=self._next_id("activity"),
            activity_type=ActivityType.TRANSFORM,
            name=name,
            agent_id=(agent or self._default_agent).id,
            parameters={"transform_type": transform_type, **kwargs},
        )
        activity.start()
        
        ctx = ObservationContext(activity=activity, observer=self)
        
        try:
            yield ctx
        finally:
            activity.end()
            self.graph.add_activity(activity)
            self.graph.link_association(activity.id, activity.agent_id)
    
    @contextmanager
    def observe_consume(
        self,
        name: str,
        model_id: str = None,
        consume_type: str = "train",
        agent: Agent = None,
        **kwargs,
    ) -> Generator[ObservationContext, None, None]:
        """
        Observe dataset consumption (training, inference).
        
        Args:
            name: Name of the consumption operation
            model_id: ID of the model consuming the data
            consume_type: Type of consumption (train, evaluate, inference)
            agent: Agent performing the consumption
            **kwargs: Additional activity parameters
        
        Yields:
            ObservationContext for registering inputs/outputs
        
        Example:
            with observer.observe_consume("train_qa_model", model_id="bert-base") as ctx:
                ctx.input(train_ds)
                model = train(train_ds)
                # Model provenance now links to data provenance!
        """
        # Create model agent if model_id provided
        if model_id and agent is None:
            agent = create_model_agent(model_id)
            self.graph.add_agent(agent)
        
        activity_type = {
            "train": ActivityType.TRAIN,
            "evaluate": ActivityType.EVALUATE,
            "inference": ActivityType.INFERENCE,
        }.get(consume_type, ActivityType.TRAIN)
        
        activity = Activity(
            id=self._next_id("activity"),
            activity_type=activity_type,
            name=name,
            agent_id=(agent or self._default_agent).id,
            parameters={"model_id": model_id, "consume_type": consume_type, **kwargs},
        )
        activity.start()
        
        ctx = ObservationContext(activity=activity, observer=self)
        
        try:
            yield ctx
        finally:
            activity.end()
            self.graph.add_activity(activity)
            self.graph.link_association(activity.id, activity.agent_id)
    
    @contextmanager
    def observe_entity_resolution(
        self,
        name: str,
        model_id: str = None,
        threshold: float = None,
        agent: Agent = None,
        **kwargs,
    ) -> Generator[ObservationContext, None, None]:
        """
        Observe entity resolution / data unity operation.
        
        Args:
            name: Name of the operation
            model_id: Embedding model used
            threshold: Similarity threshold
            agent: Agent performing the operation
            **kwargs: Additional parameters
        
        Example:
            with observer.observe_entity_resolution("match_patients_claims") as ctx:
                ctx.input(patients_ds)
                ctx.input(claims_ds)
                unified = run_unity(patients_ds, claims_ds)
                ctx.output(unified)
        """
        if model_id and agent is None:
            agent = create_model_agent(model_id)
            self.graph.add_agent(agent)
        
        activity = Activity(
            id=self._next_id("activity"),
            activity_type=ActivityType.ENTITY_RESOLUTION,
            name=name,
            agent_id=(agent or self._default_agent).id,
            parameters={
                "model_id": model_id,
                "threshold": threshold,
                **kwargs,
            },
        )
        activity.start()
        
        ctx = ObservationContext(activity=activity, observer=self)
        
        try:
            yield ctx
        finally:
            activity.end()
            self.graph.add_activity(activity)
            self.graph.link_association(activity.id, activity.agent_id)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def export_provenance(self) -> ProvenanceGraph:
        """Export the provenance graph."""
        return self.graph
    
    def to_dict(self) -> Dict[str, Any]:
        """Export observation state to dictionary."""
        return {
            "graph": self.graph.to_dict(),
            "counter": self._counter,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetObserver":
        """Load observer from dictionary."""
        observer = cls()
        observer.graph = ProvenanceGraph.from_dict(data["graph"])
        observer._counter = data.get("counter", 0)
        return observer
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get observer statistics."""
        return {
            "graph": self.graph.stats,
            "root_hash": self.graph.root_hash,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LICENSE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def check_license_compatibility(
        self,
        entity_ids: List[str],
        target_license: str = None,
    ):
        """
        Check license compatibility for deriving from entities.
        
        Args:
            entity_ids: List of source entity IDs
            target_license: Intended SPDX license for derived work
        
        Returns:
            LicenseCompatibility result
        
        Example:
            result = observer.check_license_compatibility(
                ["entity:123", "entity:456"],
                target_license="MIT"
            )
            if not result.compatible:
                print(f"Issues: {result.issues}")
        """
        from .license import check_license_compatibility
        
        sources = []
        for entity_id in entity_ids:
            entity = self.graph.get_entity(entity_id)
            if entity:
                license_id = entity.license_id or "unknown"
                sources.append((entity_id, license_id))
        
        return check_license_compatibility(sources, target_license)
    
    def get_derived_license(self, entity_ids: List[str]):
        """
        Get the appropriate license for a work derived from entities.
        
        Args:
            entity_ids: List of source entity IDs
        
        Returns:
            SPDXLicense for the derived work
        """
        from .license import get_derived_license
        
        licenses = []
        for entity_id in entity_ids:
            entity = self.graph.get_entity(entity_id)
            if entity and entity.license_id:
                licenses.append(entity.license_id)
        
        return get_derived_license(licenses) if licenses else None
    
    def generate_attribution(self, entity_ids: List[str] = None) -> str:
        """
        Generate attribution text for entities.
        
        Args:
            entity_ids: List of entity IDs (defaults to all entities)
        
        Returns:
            Markdown attribution text
        """
        from .license import LicenseAnalyzer
        
        analyzer = LicenseAnalyzer()
        
        if entity_ids is None:
            entities = self.graph.list_entities()
        else:
            entities = [
                self.graph.get_entity(eid) for eid in entity_ids
                if self.graph.get_entity(eid)
            ]
        
        sources = [
            (e.id, e.license_id or "unknown", e.name)
            for e in entities
        ]
        
        return analyzer.generate_attribution(sources)
    
    def __repr__(self) -> str:
        return f"DatasetObserver({self.graph})"
