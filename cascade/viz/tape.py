"""
CASCADE Tape Utilities - JSONL tape file handling.

Tape files are the primary persistence format for CASCADE observations.
They use JSONL (JSON Lines) format for easy streaming and append operations.

TAPE FILES:
- Model Observatory: logs/cascade_tape_*.jsonl
- Data Unity: logs/unity_tape_*.jsonl
- Provenance: logs/provenance_tape_*.jsonl

Usage:
    from cascade.viz.tape import load_tape_file, find_latest_tape, list_tape_files
    
    # Load a specific tape
    events = load_tape_file("logs/cascade_tape_1234567890.jsonl")
    
    # Find the most recent tape
    latest = find_latest_tape(tape_type="cascade")
    
    # List all available tapes
    all_tapes = list_tape_files()
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


def load_tape_file(tape_path: str) -> List[Dict[str, Any]]:
    """
    Load events from a tape file (JSONL format).
    
    Works with all tape types:
    - Model Observatory tapes: logs/cascade_tape_*.jsonl
    - Data Unity tapes: logs/unity_tape_*.jsonl
    - Provenance tapes: logs/provenance_tape_*.jsonl
    
    Args:
        tape_path: Path to the .jsonl tape file
        
    Returns:
        List of event records in chronological order
    """
    events = []
    with open(tape_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip malformed lines
    return events


def write_tape_event(tape_path: str, event: Dict[str, Any]) -> None:
    """
    Append a single event to a tape file.
    
    Args:
        tape_path: Path to the .jsonl tape file
        event: Event dict to append
    """
    with open(tape_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def find_latest_tape(log_dir: str = "./logs", tape_type: str = "cascade") -> Optional[str]:
    """
    Find the most recent tape file of a given type.
    
    Args:
        log_dir: Directory containing tape files
        tape_type: "cascade" for Model Observatory, "unity" for Data Unity,
                   "provenance" for provenance tapes
        
    Returns:
        Path to the latest tape file, or None if not found
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return None
    
    pattern = f"{tape_type}_tape_*.jsonl"
    tapes = list(log_path.glob(pattern))
    
    if not tapes:
        return None
    
    # Sort by modification time (most recent first)
    tapes.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(tapes[0])


def list_tape_files(log_dir: str = "./logs") -> Dict[str, List[str]]:
    """
    List all available tape files by type.
    
    Args:
        log_dir: Directory containing tape files
    
    Returns:
        Dict with keys "cascade", "unity", and "provenance",
        each containing list of tape paths sorted by recency
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return {"cascade": [], "unity": [], "provenance": []}
    
    cascade_tapes = sorted(
        log_path.glob("cascade_tape_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    unity_tapes = sorted(
        log_path.glob("unity_tape_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    provenance_tapes = sorted(
        log_path.glob("provenance_tape_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    return {
        "cascade": [str(p) for p in cascade_tapes],
        "unity": [str(p) for p in unity_tapes],
        "provenance": [str(p) for p in provenance_tapes],
    }


def create_tape_path(log_dir: str = "./logs", tape_type: str = "cascade", session_id: Optional[int] = None) -> str:
    """
    Generate a new tape file path.
    
    Args:
        log_dir: Directory for tape files
        tape_type: Type prefix ("cascade", "unity", "provenance")
        session_id: Optional session ID; if None, uses current timestamp
        
    Returns:
        Path string for the new tape file
    """
    import time
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    if session_id is None:
        session_id = int(time.time())
    
    return str(log_path / f"{tape_type}_tape_{session_id}.jsonl")


@dataclass
class PlaybackEvent:
    """A single event in the playback buffer."""
    timestamp: float
    event_type: str
    data: Dict[str, Any]
    

@dataclass 
class PlaybackBuffer:
    """
    Buffer of events for playback/analysis.
    
    Useful for loading tape files and iterating through events.
    """
    events: List[PlaybackEvent] = field(default_factory=list)
    current_index: int = 0
    is_complete: bool = False
    
    def add(self, event: PlaybackEvent):
        """Add an event to the buffer."""
        self.events.append(event)
    
    def get_events_up_to(self, index: int) -> List[PlaybackEvent]:
        """Get all events up to and including the given index."""
        return self.events[:index + 1]
    
    def __len__(self):
        return len(self.events)
    
    def __iter__(self):
        return iter(self.events)
    
    @classmethod
    def from_tape(cls, tape_path: str) -> "PlaybackBuffer":
        """
        Create a PlaybackBuffer from a tape file.
        
        Args:
            tape_path: Path to JSONL tape file
            
        Returns:
            PlaybackBuffer populated with events from the tape
        """
        buffer = cls()
        records = load_tape_file(tape_path)
        
        for record in records:
            event_data = record.get("event", record)
            buffer.add(PlaybackEvent(
                timestamp=event_data.get("timestamp", 0),
                event_type=event_data.get("event_type", "unknown"),
                data=event_data,
            ))
        
        buffer.is_complete = True
        return buffer
