"""
Croissant Exporter

Exports provenance graph to MLCommons Croissant format.
Croissant is the emerging standard for ML dataset metadata.

Reference: https://github.com/mlcommons/croissant
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .entities import DatasetEntity, Activity, Agent
from .provenance import ProvenanceGraph


class CroissantExporter:
    """
    Export provenance to Croissant JSON-LD format.
    
    Croissant layers:
    1. Metadata - description, license, citation
    2. Resources - file descriptions
    3. Structure - record sets and fields
    4. ML Semantics - task types, splits
    
    We add provenance as an extension.
    """
    
    CROISSANT_VERSION = "1.0"
    CROISSANT_CONTEXT = "http://mlcommons.org/croissant/1.0"
    
    def __init__(self, graph: ProvenanceGraph):
        self.graph = graph
    
    def export(
        self,
        name: str = None,
        description: str = None,
        license_url: str = None,
        citation: str = None,
        url: str = None,
        include_provenance: bool = True,
    ) -> Dict[str, Any]:
        """
        Export to Croissant JSON-LD.
        
        Args:
            name: Dataset name (defaults to graph name)
            description: Dataset description
            license_url: License URL
            citation: Citation text
            url: Dataset URL
            include_provenance: Whether to include CASCADE provenance extension
        
        Returns:
            Croissant JSON-LD document
        """
        name = name or self.graph.name
        
        doc = {
            "@context": {
                "@vocab": "http://schema.org/",
                "sc": "http://schema.org/",
                "cr": "http://mlcommons.org/croissant/",
                "rai": "http://mlcommons.org/croissant/RAI/",
                "spdx": "http://spdx.org/rdf/terms#",
            },
            "@type": "sc:Dataset",
            "name": name,
            "conformsTo": self.CROISSANT_CONTEXT,
            "dateCreated": datetime.fromtimestamp(self.graph.created_at).isoformat(),
            "dateModified": datetime.now().isoformat(),
        }
        
        if description:
            doc["description"] = description
        if license_url:
            doc["license"] = license_url
        if citation:
            doc["citation"] = citation
        if url:
            doc["url"] = url
        
        # Add distributions (file objects)
        doc["distribution"] = self._build_distributions()
        
        # Add record sets
        doc["recordSet"] = self._build_record_sets()
        
        # Add provenance extension
        if include_provenance:
            doc["cr:provenance"] = self._build_provenance_extension()
        
        return doc
    
    def _build_distributions(self) -> List[Dict[str, Any]]:
        """Build distribution (FileObject) entries."""
        distributions = []
        
        for entity in self.graph.list_entities():
            dist = {
                "@type": "cr:FileObject",
                "@id": entity.id,
                "name": entity.name,
            }
            
            if entity.source_uri:
                dist["contentUrl"] = entity.source_uri
            
            if entity.content_hash:
                dist["sha256"] = entity.content_hash
            
            # License information (SPDX)
            if entity.license_id:
                dist["spdx:license"] = entity.license_id
                if entity.license_url:
                    dist["sc:license"] = entity.license_url
                else:
                    # Auto-generate SPDX license URL
                    dist["sc:license"] = f"https://spdx.org/licenses/{entity.license_id}.html"
            
            # Infer encoding format from source type
            format_map = {
                "hf_dataset": "application/x-arrow",
                "hf_hub": "application/x-arrow",
                "parquet": "application/x-parquet",
                "csv": "text/csv",
                "json": "application/json",
                "jsonl": "application/x-jsonlines",
            }
            if entity.source_type in format_map:
                dist["encodingFormat"] = format_map[entity.source_type]
            
            if entity.size_bytes:
                dist["contentSize"] = f"{entity.size_bytes} bytes"
            
            distributions.append(dist)
        
        return distributions
    
    def _build_record_sets(self) -> List[Dict[str, Any]]:
        """Build RecordSet entries from entity schemas."""
        record_sets = []
        
        for entity in self.graph.list_entities():
            schema = entity.attributes.get("schema")
            if not schema:
                continue
            
            fields = []
            for field_name, field_info in schema.get("fields", {}).items():
                field_entry = {
                    "@type": "cr:Field",
                    "name": field_name,
                    "dataType": self._map_dtype_to_croissant(field_info.get("dtype", "string")),
                }
                
                if field_info.get("description"):
                    field_entry["description"] = field_info["description"]
                
                # Source reference
                field_entry["source"] = {
                    "fileObject": {"@id": entity.id},
                    "extract": {"column": field_name},
                }
                
                fields.append(field_entry)
            
            if fields:
                record_set = {
                    "@type": "cr:RecordSet",
                    "@id": f"recordset_{entity.id}",
                    "name": f"{entity.name}_records",
                    "field": fields,
                }
                
                if entity.record_count:
                    record_set["cr:recordCount"] = entity.record_count
                
                record_sets.append(record_set)
        
        return record_sets
    
    def _map_dtype_to_croissant(self, dtype: str) -> str:
        """Map internal dtype to Croissant/schema.org type."""
        type_map = {
            "string": "sc:Text",
            "int8": "sc:Integer",
            "int16": "sc:Integer",
            "int32": "sc:Integer",
            "int64": "sc:Integer",
            "uint8": "sc:Integer",
            "uint16": "sc:Integer",
            "uint32": "sc:Integer",
            "uint64": "sc:Integer",
            "float16": "sc:Float",
            "float32": "sc:Float",
            "float64": "sc:Float",
            "bool": "sc:Boolean",
            "binary": "sc:Text",  # Base64 encoded
            "image": "sc:ImageObject",
            "audio": "sc:AudioObject",
            "categorical": "sc:Text",  # With enumeration
            "list": "sc:ItemList",
            "struct": "sc:StructuredValue",
        }
        return type_map.get(dtype, "sc:Text")
    
    def _build_provenance_extension(self) -> Dict[str, Any]:
        """Build CASCADE provenance extension."""
        return {
            "@type": "cascade:ProvenanceGraph",
            "cascade:rootHash": self.graph.root_hash,
            "cascade:createdAt": datetime.fromtimestamp(self.graph.created_at).isoformat(),
            
            # Entities with lineage
            "cascade:entities": [
                {
                    "@id": e.id,
                    "cascade:name": e.name,
                    "cascade:contentHash": e.content_hash,
                    "cascade:schemaHash": e.schema_hash,
                    "cascade:version": e.version,
                    "cascade:recordCount": e.record_count,
                    "cascade:derivedFrom": self.graph.get_lineage(e.id, "upstream"),
                }
                for e in self.graph.list_entities()
            ],
            
            # Activities
            "cascade:activities": [
                {
                    "@id": a.id,
                    "cascade:type": a.activity_type.value,
                    "cascade:name": a.name,
                    "cascade:startedAt": datetime.fromtimestamp(a.started_at).isoformat() if a.started_at else None,
                    "cascade:endedAt": datetime.fromtimestamp(a.ended_at).isoformat() if a.ended_at else None,
                    "cascade:inputs": a.inputs,
                    "cascade:outputs": a.outputs,
                    "cascade:parameters": a.parameters,
                }
                for a in self.graph.list_activities()
            ],
            
            # Agents
            "cascade:agents": [
                {
                    "@id": a.id,
                    "cascade:type": a.agent_type.value,
                    "cascade:name": a.name,
                    "cascade:version": a.version,
                }
                for a in self.graph.list_agents()
            ],
        }
    
    def to_json(self, **kwargs) -> str:
        """Export to JSON string."""
        return json.dumps(self.export(**kwargs), indent=2, default=str)
    
    def save(self, path: str, **kwargs):
        """Save to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json(**kwargs))


def export_to_croissant(
    graph: ProvenanceGraph,
    name: str = None,
    description: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Convenience function to export provenance to Croissant.
    
    Args:
        graph: The provenance graph to export
        name: Dataset name
        description: Dataset description
        **kwargs: Additional export options
    
    Returns:
        Croissant JSON-LD document
    """
    exporter = CroissantExporter(graph)
    return exporter.export(name=name, description=description, **kwargs)
