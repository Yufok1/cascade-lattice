"""
CASCADE → Tableau Export Pipeline

Exports Cascade data in Tableau-friendly formats:
- CSV files (universal)
- Hyper files (native Tableau, optional)

Usage:
    from cascade.export import export_for_tableau
    
    # Export all data to a directory
    export_for_tableau("./tableau_data")
    
    # Then in Tableau: Connect → Text File → select CSVs
"""

import csv
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Try to import Hyper API (optional)
try:
    from tableauhyperapi import (
        HyperProcess, Telemetry, Connection, CreateMode,
        TableDefinition, SqlType, TableName, Inserter
    )
    HAS_HYPER = True
except ImportError:
    HAS_HYPER = False


@dataclass
class EventRow:
    """Flattened event for Tableau."""
    event_id: str
    timestamp: float
    timestamp_iso: str
    component: str
    event_type: str
    data_json: str
    # Extracted common fields
    loss: Optional[float] = None
    accuracy: Optional[float] = None
    learning_rate: Optional[float] = None
    epoch: Optional[int] = None
    step: Optional[int] = None
    tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class ChainRow:
    """Flattened provenance chain for Tableau."""
    session_id: str
    model_id: str
    model_hash: str
    input_hash: str
    output_hash: Optional[str]
    merkle_root: str
    created_at: float
    created_at_iso: str
    record_count: int
    external_links_count: int
    is_verified: bool


@dataclass
class HoldEventRow:
    """Flattened HOLD event for Tableau."""
    hold_id: str
    timestamp: float
    timestamp_iso: str
    brain_id: str
    state: str  # PENDING, ACCEPTED, OVERRIDDEN, TIMEOUT
    ai_choice: int
    ai_confidence: float
    final_action: int
    was_override: bool
    hold_duration_sec: float
    value_estimate: float
    action_count: int
    override_source: Optional[str] = None


@dataclass
class CausationEdgeRow:
    """Flattened causation link for Tableau."""
    link_id: str
    from_event_id: str
    to_event_id: str
    causation_type: str  # temporal, correlation, threshold, direct
    strength: float
    timestamp: float
    timestamp_iso: str


@dataclass
class MetricRow:
    """Time-series metric for Tableau."""
    timestamp: float
    timestamp_iso: str
    metric_name: str
    metric_value: float
    category: str  # TRAINING_DYNAMICS, GRADIENT_HEALTH, etc.
    component: str
    is_anomaly: bool
    anomaly_severity: Optional[str] = None


def _ts_to_iso(ts: float) -> str:
    """Convert Unix timestamp to ISO string."""
    try:
        return datetime.fromtimestamp(ts).isoformat()
    except:
        return ""


def _extract_metric_fields(data: Dict) -> Dict[str, Any]:
    """Extract common metric fields from event data."""
    return {
        "loss": data.get("loss"),
        "accuracy": data.get("accuracy") or data.get("acc"),
        "learning_rate": data.get("learning_rate") or data.get("lr"),
        "epoch": data.get("epoch"),
        "step": data.get("step") or data.get("iter"),
        "tokens": data.get("tokens") or data.get("total_tokens"),
        "latency_ms": data.get("latency_ms") or data.get("latency"),
        "error_message": data.get("error") or data.get("message"),
    }


class TableauExporter:
    """
    Export Cascade data for Tableau visualization.
    
    Creates a directory with CSV files ready for Tableau import:
    - events.csv: All observed events
    - chains.csv: Provenance chains
    - hold_events.csv: HOLD protocol events
    - causation_edges.csv: Graph edges for relationship diagrams
    - metrics_timeseries.csv: Metrics over time
    
    Example:
        exporter = TableauExporter()
        exporter.add_events(events)
        exporter.add_chains(chains)
        exporter.export("./tableau_data")
    """
    
    def __init__(self):
        self.events: List[EventRow] = []
        self.chains: List[ChainRow] = []
        self.hold_events: List[HoldEventRow] = []
        self.causation_edges: List[CausationEdgeRow] = []
        self.metrics: List[MetricRow] = []
    
    def add_event(self, event) -> None:
        """Add a Cascade Event."""
        data = event.data if hasattr(event, 'data') else {}
        extracted = _extract_metric_fields(data)
        
        row = EventRow(
            event_id=event.event_id,
            timestamp=event.timestamp,
            timestamp_iso=_ts_to_iso(event.timestamp),
            component=event.component,
            event_type=event.event_type,
            data_json=json.dumps(data),
            **extracted
        )
        self.events.append(row)
    
    def add_events(self, events) -> None:
        """Add multiple events."""
        for e in events:
            self.add_event(e)
    
    def add_chain(self, chain, is_verified: bool = True) -> None:
        """Add a ProvenanceChain."""
        row = ChainRow(
            session_id=chain.session_id,
            model_id=chain.model_id,
            model_hash=chain.model_hash,
            input_hash=chain.input_hash,
            output_hash=chain.output_hash,
            merkle_root=chain.merkle_root or "",
            created_at=chain.created_at,
            created_at_iso=_ts_to_iso(chain.created_at),
            record_count=len(chain.records),
            external_links_count=len(chain.external_roots),
            is_verified=is_verified,
        )
        self.chains.append(row)
    
    def add_chains(self, chains) -> None:
        """Add multiple chains."""
        for c in chains:
            self.add_chain(c)
    
    def add_hold_event(self, hold_point, resolution) -> None:
        """Add a HOLD event with its resolution."""
        import numpy as np
        
        probs = hold_point.action_probs
        if isinstance(probs, np.ndarray):
            ai_choice = int(np.argmax(probs))
            ai_confidence = float(np.max(probs))
            action_count = len(probs)
        else:
            ai_choice = 0
            ai_confidence = 0.0
            action_count = 0
        
        row = HoldEventRow(
            hold_id=getattr(hold_point, 'hold_id', f"hold_{hold_point.timestamp}"),
            timestamp=hold_point.timestamp if hasattr(hold_point, 'timestamp') else 0,
            timestamp_iso=_ts_to_iso(hold_point.timestamp) if hasattr(hold_point, 'timestamp') else "",
            brain_id=hold_point.brain_id,
            state=resolution.state.value if hasattr(resolution.state, 'value') else str(resolution.state),
            ai_choice=ai_choice,
            ai_confidence=ai_confidence,
            final_action=resolution.action,
            was_override=resolution.was_override,
            hold_duration_sec=resolution.hold_duration if hasattr(resolution, 'hold_duration') else 0,
            value_estimate=hold_point.value,
            action_count=action_count,
            override_source=resolution.override_source if hasattr(resolution, 'override_source') else None,
        )
        self.hold_events.append(row)
    
    def add_causation_link(self, link) -> None:
        """Add a causation graph edge."""
        row = CausationEdgeRow(
            link_id=link.link_id if hasattr(link, 'link_id') else f"{link.from_event}_{link.to_event}",
            from_event_id=link.from_event,
            to_event_id=link.to_event,
            causation_type=link.causation_type,
            strength=link.strength,
            timestamp=link.timestamp if hasattr(link, 'timestamp') else 0,
            timestamp_iso=_ts_to_iso(link.timestamp) if hasattr(link, 'timestamp') else "",
        )
        self.causation_edges.append(row)
    
    def add_causation_links(self, links) -> None:
        """Add multiple causation links."""
        for link in links:
            self.add_causation_link(link)
    
    def add_metric(self, name: str, value: float, timestamp: float,
                   category: str = "OTHER", component: str = "default",
                   is_anomaly: bool = False, anomaly_severity: str = None) -> None:
        """Add a time-series metric point."""
        row = MetricRow(
            timestamp=timestamp,
            timestamp_iso=_ts_to_iso(timestamp),
            metric_name=name,
            metric_value=value,
            category=category,
            component=component,
            is_anomaly=is_anomaly,
            anomaly_severity=anomaly_severity,
        )
        self.metrics.append(row)
    
    def add_metrics_from_event(self, event, category_map: Dict[str, str] = None) -> None:
        """Extract and add all metrics from an event."""
        if category_map is None:
            category_map = {
                "loss": "TRAINING_DYNAMICS",
                "accuracy": "TRAINING_DYNAMICS",
                "lr": "TRAINING_DYNAMICS",
                "learning_rate": "TRAINING_DYNAMICS",
                "grad_norm": "GRADIENT_HEALTH",
                "weight_norm": "WEIGHT_DYNAMICS",
                "tokens": "MEMORY_COMPUTE",
                "latency": "MEMORY_COMPUTE",
            }
        
        data = event.data if hasattr(event, 'data') else {}
        for key, value in data.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self.add_metric(
                    name=key,
                    value=float(value),
                    timestamp=event.timestamp,
                    category=category_map.get(key, "OTHER"),
                    component=event.component,
                )
    
    def _write_csv(self, path: Path, rows: List, fieldnames: List[str]) -> None:
        """Write rows to CSV."""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row) if hasattr(row, '__dataclass_fields__') else row)
    
    def export(self, output_dir: str) -> Dict[str, str]:
        """
        Export all data to CSV files.
        
        Args:
            output_dir: Directory to write CSV files
            
        Returns:
            Dict mapping data type to file path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        files = {}
        
        # Events
        if self.events:
            events_path = output_path / "events.csv"
            self._write_csv(events_path, self.events, list(EventRow.__dataclass_fields__.keys()))
            files["events"] = str(events_path)
            print(f"✓ Exported {len(self.events)} events to {events_path}")
        
        # Chains
        if self.chains:
            chains_path = output_path / "chains.csv"
            self._write_csv(chains_path, self.chains, list(ChainRow.__dataclass_fields__.keys()))
            files["chains"] = str(chains_path)
            print(f"✓ Exported {len(self.chains)} chains to {chains_path}")
        
        # HOLD events
        if self.hold_events:
            hold_path = output_path / "hold_events.csv"
            self._write_csv(hold_path, self.hold_events, list(HoldEventRow.__dataclass_fields__.keys()))
            files["hold_events"] = str(hold_path)
            print(f"✓ Exported {len(self.hold_events)} HOLD events to {hold_path}")
        
        # Causation edges
        if self.causation_edges:
            edges_path = output_path / "causation_edges.csv"
            self._write_csv(edges_path, self.causation_edges, list(CausationEdgeRow.__dataclass_fields__.keys()))
            files["causation_edges"] = str(edges_path)
            print(f"✓ Exported {len(self.causation_edges)} causation edges to {edges_path}")
        
        # Metrics time series
        if self.metrics:
            metrics_path = output_path / "metrics_timeseries.csv"
            self._write_csv(metrics_path, self.metrics, list(MetricRow.__dataclass_fields__.keys()))
            files["metrics"] = str(metrics_path)
            print(f"✓ Exported {len(self.metrics)} metric points to {metrics_path}")
        
        # Write a manifest
        manifest_path = output_path / "manifest.json"
        manifest = {
            "exported_at": datetime.now().isoformat(),
            "files": files,
            "counts": {
                "events": len(self.events),
                "chains": len(self.chains),
                "hold_events": len(self.hold_events),
                "causation_edges": len(self.causation_edges),
                "metrics": len(self.metrics),
            }
        }
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"\n📊 Tableau export complete: {output_path}")
        print(f"   Open Tableau → Connect → Text File → Select CSVs")
        
        return files
    
    def export_hyper(self, output_path: str) -> Optional[str]:
        """
        Export to Tableau Hyper format (native, fastest).
        
        Requires: pip install tableauhyperapi
        """
        if not HAS_HYPER:
            print("⚠️ Hyper API not installed. Run: pip install tableauhyperapi")
            return None
        
        hyper_path = Path(output_path)
        
        with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
            with Connection(hyper.endpoint, str(hyper_path), CreateMode.CREATE_AND_REPLACE) as conn:
                
                # Create events table
                if self.events:
                    events_table = TableDefinition(
                        TableName("events"),
                        [
                            ("event_id", SqlType.text()),
                            ("timestamp", SqlType.double()),
                            ("timestamp_iso", SqlType.text()),
                            ("component", SqlType.text()),
                            ("event_type", SqlType.text()),
                            ("loss", SqlType.double()),
                            ("accuracy", SqlType.double()),
                            ("tokens", SqlType.int()),
                        ]
                    )
                    conn.catalog.create_table(events_table)
                    
                    with Inserter(conn, events_table) as inserter:
                        for e in self.events:
                            inserter.add_row([
                                e.event_id, e.timestamp, e.timestamp_iso,
                                e.component, e.event_type,
                                e.loss, e.accuracy, e.tokens
                            ])
                        inserter.execute()
        
        print(f"✓ Exported Hyper file: {hyper_path}")
        return str(hyper_path)


# =============================================================================
# Convenience Functions
# =============================================================================

def export_for_tableau(output_dir: str = "./tableau_export",
                       include_sample_data: bool = True) -> Dict[str, str]:
    """
    One-line export of all Cascade data for Tableau.
    
    Args:
        output_dir: Where to write CSV files
        include_sample_data: Generate sample data if no real data
        
    Returns:
        Dict of exported file paths
    """
    exporter = TableauExporter()
    
    # Try to load real data from Cascade store
    try:
        from cascade.store import query, stats
        from cascade.observation import ObservationManager
        
        # Get observations
        manager = ObservationManager()
        observations = manager.get_recent(limit=1000)
        
        for obs in observations:
            # Create mock event from observation
            class MockEvent:
                def __init__(self, o):
                    self.event_id = o.get('cid', '')
                    self.timestamp = o.get('timestamp', 0)
                    self.component = o.get('model_id', 'unknown')
                    self.event_type = 'inference'
                    self.data = o.get('data', {})
            
            exporter.add_event(MockEvent(obs))
            exporter.add_metrics_from_event(MockEvent(obs))
        
        print(f"Loaded {len(observations)} observations from Cascade store")
        
    except Exception as e:
        print(f"Note: Could not load Cascade store ({e})")
        if include_sample_data:
            print("Generating sample data for demo...")
            _add_sample_data(exporter)
    
    return exporter.export(output_dir)


def _add_sample_data(exporter: TableauExporter) -> None:
    """Add sample data for demonstration."""
    import time
    import random
    
    base_time = time.time() - 3600  # 1 hour ago
    
    # Sample events
    models = ["gpt-4", "claude-3-opus", "llama-3-8b", "mistral-7b"]
    event_types = ["inference", "training_step", "error", "checkpoint"]
    
    for i in range(200):
        class SampleEvent:
            def __init__(self, idx):
                self.event_id = f"evt_{idx:06d}"
                self.timestamp = base_time + (idx * 18)  # 18 sec apart
                self.component = random.choice(models)
                self.event_type = random.choice(event_types)
                self.data = {
                    "loss": 2.5 - (idx * 0.01) + random.uniform(-0.1, 0.1),
                    "accuracy": min(0.95, 0.5 + (idx * 0.002) + random.uniform(-0.02, 0.02)),
                    "tokens": random.randint(100, 2000),
                    "latency_ms": random.uniform(50, 500),
                    "step": idx,
                }
        
        event = SampleEvent(i)
        exporter.add_event(event)
        exporter.add_metrics_from_event(event)
    
    # Sample HOLD events
    for i in range(20):
        class SampleHoldPoint:
            def __init__(self, idx):
                import numpy as np
                self.hold_id = f"hold_{idx:04d}"
                self.timestamp = base_time + (idx * 180)
                self.brain_id = random.choice(models)
                self.action_probs = np.random.dirichlet([1, 1, 1, 1])
                self.value = random.uniform(0.3, 0.9)
        
        class SampleResolution:
            def __init__(self, override=False):
                self.state = type('State', (), {'value': 'OVERRIDDEN' if override else 'ACCEPTED'})()
                self.action = random.randint(0, 3)
                self.was_override = override
                self.hold_duration = random.uniform(0.5, 10.0)
                self.override_source = "human" if override else None
        
        hold = SampleHoldPoint(i)
        resolution = SampleResolution(override=random.random() < 0.25)
        exporter.add_hold_event(hold, resolution)
    
    # Sample causation edges
    for i in range(50):
        class SampleLink:
            def __init__(self, idx):
                self.link_id = f"link_{idx:04d}"
                self.from_event = f"evt_{idx:06d}"
                self.to_event = f"evt_{idx+1:06d}"
                self.causation_type = random.choice(["temporal", "correlation", "threshold", "direct"])
                self.strength = random.uniform(0.5, 1.0)
                self.timestamp = base_time + (idx * 18)
        
        exporter.add_causation_link(SampleLink(i))
    
    # Sample chains
    for i in range(10):
        class SampleChain:
            def __init__(self, idx):
                self.session_id = f"session_{idx:04d}"
                self.model_id = random.choice(models)
                self.model_hash = f"{random.randint(0, 0xFFFFFFFF):08x}"
                self.input_hash = f"{random.randint(0, 0xFFFFFFFF):08x}"
                self.output_hash = f"{random.randint(0, 0xFFFFFFFF):08x}"
                self.merkle_root = f"{random.randint(0, 0xFFFFFFFFFFFFFFFF):016x}"
                self.created_at = base_time + (idx * 360)
                self.records = [None] * random.randint(5, 50)
                self.external_roots = [f"root_{j}" for j in range(random.randint(0, 3))]
        
        exporter.add_chain(SampleChain(i))


def export_events_csv(events, output_path: str) -> str:
    """Export events to CSV."""
    exporter = TableauExporter()
    exporter.add_events(events)
    files = exporter.export(str(Path(output_path).parent))
    return files.get("events", "")


def export_chains_csv(chains, output_path: str) -> str:
    """Export chains to CSV."""
    exporter = TableauExporter()
    exporter.add_chains(chains)
    files = exporter.export(str(Path(output_path).parent))
    return files.get("chains", "")


def export_metrics_csv(events, output_path: str) -> str:
    """Export metrics time series to CSV."""
    exporter = TableauExporter()
    for e in events:
        exporter.add_metrics_from_event(e)
    files = exporter.export(str(Path(output_path).parent))
    return files.get("metrics", "")


def export_hold_events_csv(hold_pairs, output_path: str) -> str:
    """Export HOLD events to CSV. hold_pairs = [(hold_point, resolution), ...]"""
    exporter = TableauExporter()
    for hold, res in hold_pairs:
        exporter.add_hold_event(hold, res)
    files = exporter.export(str(Path(output_path).parent))
    return files.get("hold_events", "")


def export_causation_graph_csv(links, output_path: str) -> str:
    """Export causation edges to CSV."""
    exporter = TableauExporter()
    exporter.add_causation_links(links)
    files = exporter.export(str(Path(output_path).parent))
    return files.get("causation_edges", "")


if __name__ == "__main__":
    # Quick test
    print("Exporting sample data for Tableau...")
    export_for_tableau("./tableau_export", include_sample_data=True)
