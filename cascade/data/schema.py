"""
Schema Observer

Observes and hashes dataset schemas/features.
Works with HuggingFace datasets Features, Pandas DataFrames, and raw dicts.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class FieldSchema:
    """Schema for a single field/column."""
    name: str
    dtype: str  # Normalized type name
    
    # Type details
    nullable: bool = True
    is_list: bool = False
    list_inner_type: Optional[str] = None
    
    # For ClassLabel
    is_categorical: bool = False
    categories: Optional[List[str]] = None
    num_categories: Optional[int] = None
    
    # For nested structures
    nested_fields: Optional[Dict[str, "FieldSchema"]] = None
    
    # For arrays/tensors
    shape: Optional[tuple] = None
    
    # Constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None  # Regex for strings
    
    # Metadata
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "dtype": self.dtype,
            "nullable": self.nullable,
        }
        if self.is_list:
            result["is_list"] = True
            result["list_inner_type"] = self.list_inner_type
        if self.is_categorical:
            result["is_categorical"] = True
            result["categories"] = self.categories
            result["num_categories"] = self.num_categories
        if self.nested_fields:
            result["nested_fields"] = {
                k: v.to_dict() for k, v in self.nested_fields.items()
            }
        if self.shape:
            result["shape"] = self.shape
        if self.description:
            result["description"] = self.description
        return result
    
    def hash(self) -> str:
        """Hash this field's structure."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class DatasetSchema:
    """Complete schema for a dataset."""
    fields: Dict[str, FieldSchema] = field(default_factory=dict)
    
    # Dataset-level metadata
    primary_key: Optional[List[str]] = None
    foreign_keys: Dict[str, str] = field(default_factory=dict)  # field → target
    
    # Source info
    source_format: Optional[str] = None  # arrow, parquet, csv, etc.
    
    def add_field(self, field_schema: FieldSchema):
        """Add a field to the schema."""
        self.fields[field_schema.name] = field_schema
    
    @property
    def field_names(self) -> List[str]:
        return list(self.fields.keys())
    
    @property
    def num_fields(self) -> int:
        return len(self.fields)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "primary_key": self.primary_key,
            "foreign_keys": self.foreign_keys,
            "source_format": self.source_format,
        }
    
    def hash(self) -> str:
        """Compute schema hash - identifies structure regardless of content."""
        # Sort fields for deterministic hashing
        ordered_fields = sorted(self.fields.keys())
        content = json.dumps({
            "fields": [self.fields[k].to_dict() for k in ordered_fields],
            "primary_key": self.primary_key,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def diff(self, other: "DatasetSchema") -> Dict[str, Any]:
        """Compare two schemas and return differences."""
        added = set(other.field_names) - set(self.field_names)
        removed = set(self.field_names) - set(other.field_names)
        
        modified = {}
        for name in set(self.field_names) & set(other.field_names):
            if self.fields[name].hash() != other.fields[name].hash():
                modified[name] = {
                    "old": self.fields[name].to_dict(),
                    "new": other.fields[name].to_dict(),
                }
        
        return {
            "added": list(added),
            "removed": list(removed),
            "modified": modified,
            "compatible": len(removed) == 0 and len(modified) == 0,
        }


class SchemaObserver:
    """
    Observes and extracts schemas from various data sources.
    """
    
    # Type mapping from various sources to normalized types
    TYPE_MAP = {
        # Python types
        "str": "string",
        "int": "int64",
        "float": "float64",
        "bool": "bool",
        "bytes": "binary",
        
        # NumPy types
        "int8": "int8",
        "int16": "int16",
        "int32": "int32",
        "int64": "int64",
        "uint8": "uint8",
        "uint16": "uint16",
        "uint32": "uint32",
        "uint64": "uint64",
        "float16": "float16",
        "float32": "float32",
        "float64": "float64",
        
        # Arrow types
        "string": "string",
        "large_string": "string",
        "binary": "binary",
        "large_binary": "binary",
        
        # HuggingFace special types
        "Image": "image",
        "Audio": "audio",
        "ClassLabel": "categorical",
    }
    
    def observe_hf_dataset(self, dataset) -> DatasetSchema:
        """
        Extract schema from HuggingFace Dataset.
        
        Args:
            dataset: A HuggingFace datasets.Dataset or DatasetDict
        
        Returns:
            DatasetSchema with all fields
        """
        schema = DatasetSchema(source_format="arrow")
        
        # Get features (works for both Dataset and DatasetDict)
        if hasattr(dataset, 'features'):
            features = dataset.features
        elif hasattr(dataset, '__iter__'):
            # DatasetDict - get features from first split
            first_split = next(iter(dataset.values()))
            features = first_split.features
        else:
            raise ValueError(f"Cannot extract features from {type(dataset)}")
        
        # Parse each feature
        for name, feature in features.items():
            field_schema = self._parse_hf_feature(name, feature)
            schema.add_field(field_schema)
        
        return schema
    
    def _parse_hf_feature(self, name: str, feature) -> FieldSchema:
        """Parse a HuggingFace Feature into FieldSchema."""
        # Import here to avoid hard dependency
        try:
            from datasets import (
                Value, ClassLabel, Sequence, 
                Array2D, Array3D, Array4D, Array5D,
                Image, Audio
            )
        except ImportError:
            # Fallback for when datasets not installed
            return FieldSchema(name=name, dtype="unknown")
        
        # Value type (primitives)
        if isinstance(feature, Value):
            return FieldSchema(
                name=name,
                dtype=self.TYPE_MAP.get(feature.dtype, feature.dtype),
            )
        
        # ClassLabel (categorical)
        if isinstance(feature, ClassLabel):
            return FieldSchema(
                name=name,
                dtype="categorical",
                is_categorical=True,
                categories=feature.names,
                num_categories=feature.num_classes,
            )
        
        # Sequence (list)
        if isinstance(feature, Sequence):
            inner = self._parse_hf_feature(f"{name}_inner", feature.feature)
            return FieldSchema(
                name=name,
                dtype="list",
                is_list=True,
                list_inner_type=inner.dtype,
            )
        
        # Arrays
        if isinstance(feature, (Array2D, Array3D, Array4D, Array5D)):
            return FieldSchema(
                name=name,
                dtype=self.TYPE_MAP.get(feature.dtype, feature.dtype),
                shape=feature.shape,
            )
        
        # Image
        if isinstance(feature, Image):
            return FieldSchema(
                name=name,
                dtype="image",
            )
        
        # Audio
        if isinstance(feature, Audio):
            return FieldSchema(
                name=name,
                dtype="audio",
            )
        
        # Dict/nested structure
        if isinstance(feature, dict):
            nested = {}
            for k, v in feature.items():
                nested[k] = self._parse_hf_feature(k, v)
            return FieldSchema(
                name=name,
                dtype="struct",
                nested_fields=nested,
            )
        
        # Fallback
        return FieldSchema(
            name=name,
            dtype=str(type(feature).__name__),
        )
    
    def observe_pandas(self, df) -> DatasetSchema:
        """
        Extract schema from Pandas DataFrame.
        
        Args:
            df: A pandas DataFrame
        
        Returns:
            DatasetSchema with all fields
        """
        schema = DatasetSchema(source_format="pandas")
        
        for col in df.columns:
            dtype = str(df[col].dtype)
            normalized = self.TYPE_MAP.get(dtype, dtype)
            
            # Check for categorical
            if dtype == "category":
                schema.add_field(FieldSchema(
                    name=col,
                    dtype="categorical",
                    is_categorical=True,
                    categories=list(df[col].cat.categories),
                    num_categories=len(df[col].cat.categories),
                ))
            else:
                schema.add_field(FieldSchema(
                    name=col,
                    dtype=normalized,
                    nullable=df[col].isna().any(),
                ))
        
        return schema
    
    def observe_dict(self, data: Dict[str, Any], sample_size: int = 100) -> DatasetSchema:
        """
        Extract schema from a dict of lists (columnar format).
        
        Args:
            data: Dict mapping column names to lists of values
            sample_size: Number of values to sample for type inference
        
        Returns:
            DatasetSchema with all fields
        """
        schema = DatasetSchema(source_format="dict")
        
        for col, values in data.items():
            if not values:
                schema.add_field(FieldSchema(name=col, dtype="unknown"))
                continue
            
            # Sample values for type inference
            sample = values[:sample_size]
            types = set(type(v).__name__ for v in sample if v is not None)
            
            # Determine type
            if len(types) == 0:
                dtype = "null"
            elif len(types) == 1:
                dtype = self.TYPE_MAP.get(types.pop(), "unknown")
            else:
                dtype = "mixed"
            
            # Check for nulls
            nullable = any(v is None for v in sample)
            
            schema.add_field(FieldSchema(
                name=col,
                dtype=dtype,
                nullable=nullable,
            ))
        
        return schema
    
    def observe_arrow(self, table) -> DatasetSchema:
        """
        Extract schema from PyArrow Table.
        
        Args:
            table: A pyarrow.Table
        
        Returns:
            DatasetSchema with all fields
        """
        schema = DatasetSchema(source_format="arrow")
        
        for field in table.schema:
            dtype = str(field.type)
            normalized = self.TYPE_MAP.get(dtype, dtype)
            
            schema.add_field(FieldSchema(
                name=field.name,
                dtype=normalized,
                nullable=field.nullable,
            ))
        
        return schema


def hash_content(data, sample_size: int = 10000) -> str:
    """
    Compute content hash of dataset.
    
    For large datasets, samples rows for efficiency.
    """
    hasher = hashlib.sha256()
    
    # Handle dict first (dict also has __iter__ and __len__)
    if isinstance(data, dict):
        content = json.dumps(data, sort_keys=True, default=str)
        hasher.update(content.encode())
    
    # Handle list
    elif isinstance(data, list):
        for item in data[:sample_size]:
            item_str = json.dumps(item, sort_keys=True, default=str)
            hasher.update(item_str.encode())
    
    # Handle HuggingFace Dataset or other iterables with __len__
    elif hasattr(data, '__iter__') and hasattr(data, '__len__'):
        # Sample if large
        n = len(data)
        if n > sample_size:
            import random
            indices = sorted(random.sample(range(n), sample_size))
            sample = [data[i] for i in indices]
        else:
            sample = list(data)
        
        for row in sample:
            row_str = json.dumps(row, sort_keys=True, default=str)
            hasher.update(row_str.encode())
    
    return hasher.hexdigest()
