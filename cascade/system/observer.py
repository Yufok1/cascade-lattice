"""
CASCADE System Observer - Process logs into CASCADE events.

Observes log files or streams and emits CASCADE-compatible events
with full hash chain provenance.
"""

import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator, Union
from dataclasses import dataclass, field

from cascade.system.adapter import (
    LogAdapter, ParsedEvent, auto_detect_adapter,
    JSONLAdapter, ApacheLogAdapter, GenericLogAdapter,
)
from cascade.core.event import Event
from cascade.analysis.metrics import MetricsEngine


@dataclass
class SystemObservation:
    """Result of observing a log source."""
    
    source: str  # File path or stream name
    adapter_name: str
    events: List[ParsedEvent] = field(default_factory=list)
    
    # Hash chain
    merkle_root: str = ""
    chain_length: int = 0
    
    # Statistics
    event_counts: Dict[str, int] = field(default_factory=dict)  # type -> count
    component_counts: Dict[str, int] = field(default_factory=dict)  # component -> count
    time_range: tuple = (0.0, 0.0)  # (min_ts, max_ts)
    
    # Errors
    parse_errors: int = 0
    
    def compute_merkle_root(self) -> str:
        """Compute Merkle root of all event hashes."""
        if not self.events:
            return ""
        
        hashes = [e.event_hash for e in self.events]
        
        # Build Merkle tree
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Duplicate last if odd
            
            new_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
                new_level.append(new_hash)
            hashes = new_level
        
        self.merkle_root = hashes[0] if hashes else ""
        self.chain_length = len(self.events)
        return self.merkle_root
    
    def to_summary(self) -> Dict[str, Any]:
        """Generate summary for display."""
        return {
            "source": self.source,
            "adapter": self.adapter_name,
            "total_events": len(self.events),
            "merkle_root": self.merkle_root,
            "chain_length": self.chain_length,
            "event_types": self.event_counts,
            "components": self.component_counts,
            "time_range": {
                "start": self.time_range[0],
                "end": self.time_range[1],
                "duration_sec": self.time_range[1] - self.time_range[0] if self.time_range[1] > 0 else 0,
            },
            "parse_errors": self.parse_errors,
        }


class SystemObserver:
    """
    Observe system logs and emit CASCADE events.
    
    This is the bridge between external system logs and CASCADE visualization.
    """
    
    def __init__(self, adapter: LogAdapter = None):
        """
        Args:
            adapter: Log adapter to use. If None, will auto-detect.
        """
        self.adapter = adapter
        self.observations: List[SystemObservation] = []
        self.metrics_engine = MetricsEngine()
    
    def observe_file(self, filepath: str, adapter: LogAdapter = None) -> Generator[Event, None, SystemObservation]:
        """
        Observe a log file and emit CASCADE events.
        
        Args:
            filepath: Path to log file
            adapter: Override adapter (auto-detect if None)
            
        Yields:
            CASCADE Event objects
            
        Returns:
            SystemObservation with summary and provenance
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {filepath}")
        
        # Auto-detect adapter if needed
        if adapter is None:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                sample = [f.readline() for _ in range(20)]
            adapter = auto_detect_adapter(sample)
        
        observation = SystemObservation(
            source=str(filepath),
            adapter_name=adapter.name,
        )
        
        min_ts = float("inf")
        max_ts = 0.0
        
        # Parse file
        for parsed in adapter.parse_file(filepath):
            observation.events.append(parsed)
            
            # Update stats
            observation.event_counts[parsed.event_type] = observation.event_counts.get(parsed.event_type, 0) + 1
            observation.component_counts[parsed.component] = observation.component_counts.get(parsed.component, 0) + 1
            
            min_ts = min(min_ts, parsed.timestamp)
            max_ts = max(max_ts, parsed.timestamp)
            
            # Convert to CASCADE Event and yield
            cascade_event = Event(
                timestamp=parsed.timestamp,
                event_type=parsed.event_type,
                component=parsed.component,
                data={
                    **parsed.data,
                    "hash": parsed.event_hash,
                    "parent_hash": parsed.parent_hash,
                    "source": "system_log",
                    "adapter": adapter.name,
                },
            )
            
            self.metrics_engine.ingest(cascade_event)
            yield cascade_event
        
        # Finalize observation
        observation.time_range = (min_ts if min_ts != float("inf") else 0, max_ts)
        observation.compute_merkle_root()
        self.observations.append(observation)
        
        return observation
    
    def observe_lines(self, lines: List[str], source_name: str = "input", adapter: LogAdapter = None) -> Generator[Event, None, SystemObservation]:
        """
        Observe log lines (e.g., from text input or upload).
        
        Args:
            lines: List of log lines
            source_name: Name for this source
            adapter: Override adapter (auto-detect if None)
            
        Yields:
            CASCADE Event objects
        """
        if adapter is None:
            adapter = auto_detect_adapter(lines[:20])
        
        observation = SystemObservation(
            source=source_name,
            adapter_name=adapter.name,
        )
        
        min_ts = float("inf")
        max_ts = 0.0
        
        for parsed in adapter.parse_lines(lines):
            observation.events.append(parsed)
            
            observation.event_counts[parsed.event_type] = observation.event_counts.get(parsed.event_type, 0) + 1
            observation.component_counts[parsed.component] = observation.component_counts.get(parsed.component, 0) + 1
            
            min_ts = min(min_ts, parsed.timestamp)
            max_ts = max(max_ts, parsed.timestamp)
            
            cascade_event = Event(
                timestamp=parsed.timestamp,
                event_type=parsed.event_type,
                component=parsed.component,
                data={
                    **parsed.data,
                    "hash": parsed.event_hash,
                    "parent_hash": parsed.parent_hash,
                    "source": "system_log",
                    "adapter": adapter.name,
                },
            )
            
            self.metrics_engine.ingest(cascade_event)
            yield cascade_event
        
        observation.time_range = (min_ts if min_ts != float("inf") else 0, max_ts)
        observation.compute_merkle_root()
        self.observations.append(observation)
        
        return observation
    
    def get_all_events_for_viz(self) -> List[Dict[str, Any]]:
        """Get all events formatted for CASCADE visualization."""
        all_events = []
        for obs in self.observations:
            for parsed in obs.events:
                all_events.append({
                    "event": parsed.to_cascade_event(),
                    "metrics": self.metrics_engine.summary(),
                    "triage": self.metrics_engine.triage(),
                })
        return all_events
    
    def get_provenance_summary(self) -> Dict[str, Any]:
        """Get provenance summary for all observations."""
        return {
            "observations": [obs.to_summary() for obs in self.observations],
            "total_events": sum(len(obs.events) for obs in self.observations),
            "total_sources": len(self.observations),
        }


def observe_log_file(filepath: str) -> Generator[Event, None, SystemObservation]:
    """
    Convenience function to observe a log file.
    
    Usage:
        for event in observe_log_file("access.log"):
            print(event)
    """
    observer = SystemObserver()
    return observer.observe_file(filepath)


def observe_log_stream(lines: List[str], source: str = "stream") -> Generator[Event, None, SystemObservation]:
    """
    Convenience function to observe log lines.
    
    Usage:
        lines = log_text.split("\\n")
        for event in observe_log_stream(lines):
            print(event)
    """
    observer = SystemObserver()
    return observer.observe_lines(lines, source)


# ═══════════════════════════════════════════════════════════════════════════════
# TAPE WRITING - Write observations to tape for playback
# ═══════════════════════════════════════════════════════════════════════════════

def write_system_tape(observation: SystemObservation, tape_dir: str = "./logs") -> str:
    """
    Write system observation to tape file for playback.
    
    Args:
        observation: SystemObservation to write
        tape_dir: Directory for tape files
        
    Returns:
        Path to tape file
    """
    tape_path = Path(tape_dir)
    tape_path.mkdir(parents=True, exist_ok=True)
    
    session_id = int(time.time())
    filename = tape_path / f"system_tape_{session_id}.jsonl"
    
    with open(filename, "w", encoding="utf-8") as f:
        # Write header
        header = {
            "seq": 0,
            "ts": time.time(),
            "type": "header",
            "source": observation.source,
            "adapter": observation.adapter_name,
            "merkle_root": observation.merkle_root,
            "chain_length": observation.chain_length,
        }
        f.write(json.dumps(header) + "\n")
        
        # Write events
        for i, parsed in enumerate(observation.events, 1):
            record = {
                "seq": i,
                "ts": parsed.timestamp,
                "event": parsed.to_cascade_event(),
            }
            f.write(json.dumps(record, default=str) + "\n")
    
    return str(filename)
