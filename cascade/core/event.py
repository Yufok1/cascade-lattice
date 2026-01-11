"""
Cascade Core - Event and CausationLink primitives.

These are the fundamental data structures that represent causation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import uuid


def _generate_event_id() -> str:
    """Generate a unique event ID with timestamp prefix for ordering."""
    timestamp = int(time.time() * 1000000)
    unique = uuid.uuid4().hex[:8]
    return f"evt_{timestamp}_{unique}"


@dataclass
class Event:
    """
    A discrete event in the causation graph.
    
    Events are the nodes in your causation graph. Each event represents
    something that happened in your system at a point in time.
    
    Attributes:
        event_id: Unique identifier (auto-generated if not provided)
        timestamp: Unix timestamp when event occurred
        component: Which system component generated this event
        event_type: Category of event (e.g., 'training', 'inference', 'error')
        data: Arbitrary key-value data associated with the event
        source_signal: The original signal that created this event (for debugging)
        
    Example:
        >>> event = Event(
        ...     timestamp=time.time(),
        ...     component="neural_network",
        ...     event_type="gradient_explosion",
        ...     data={"layer": "fc3", "magnitude": 1e12}
        ... )
    """
    timestamp: float
    component: str
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=_generate_event_id)
    source_signal: Optional[Any] = field(default=None, repr=False)
    
    def __post_init__(self):
        """Ensure timestamp is float."""
        if isinstance(self.timestamp, datetime):
            self.timestamp = self.timestamp.timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "component": self.component,
            "event_type": self.event_type,
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        """Deserialize event from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_event_id()),
            timestamp=d["timestamp"],
            component=d["component"],
            event_type=d["event_type"],
            data=d.get("data", {}),
        )
    
    def __hash__(self):
        return hash(self.event_id)
    
    def __eq__(self, other):
        if isinstance(other, Event):
            return self.event_id == other.event_id
        return False


@dataclass  
class CausationLink:
    """
    A causal relationship between two events.
    
    Links are the edges in your causation graph. Each link represents
    a cause-effect relationship: event A caused event B.
    
    Attributes:
        from_event: ID of the causing event
        to_event: ID of the caused event
        causation_type: How the causation was detected
            - 'temporal': A happened shortly before B
            - 'correlation': A and B metrics moved together
            - 'threshold': A crossed a threshold triggering B
            - 'direct': Explicit causation declared in code
        strength: Confidence in the causal relationship (0.0 to 1.0)
        explanation: Human-readable explanation of the link
        metrics_involved: Which metrics connect these events
        
    Example:
        >>> link = CausationLink(
        ...     from_event="evt_123",
        ...     to_event="evt_456",
        ...     causation_type="threshold",
        ...     strength=0.95,
        ...     explanation="Loss exceeded 10.0, triggering gradient clipping"
        ... )
    """
    from_event: str
    to_event: str
    causation_type: str  # 'temporal', 'correlation', 'threshold', 'direct'
    strength: float = 1.0
    explanation: str = ""
    metrics_involved: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate strength is in range."""
        self.strength = max(0.0, min(1.0, self.strength))
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize link to dictionary."""
        return {
            "from_event": self.from_event,
            "to_event": self.to_event,
            "causation_type": self.causation_type,
            "strength": self.strength,
            "explanation": self.explanation,
            "metrics_involved": self.metrics_involved,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CausationLink":
        """Deserialize link from dictionary."""
        return cls(
            from_event=d["from_event"],
            to_event=d["to_event"],
            causation_type=d["causation_type"],
            strength=d.get("strength", 1.0),
            explanation=d.get("explanation", ""),
            metrics_involved=d.get("metrics_involved", []),
        )


@dataclass
class CausationChain:
    """
    A chain of causal events from origin to destination.
    
    Represents a full causal path through the graph.
    
    Attributes:
        events: List of events in causal order
        links: List of links connecting the events
        total_strength: Combined strength of all links
        depth: Number of hops in the chain
        narrative: Human-readable story of what happened
    """
    events: List[Event]
    links: List[CausationLink]
    total_strength: float = 1.0
    depth: int = 0
    narrative: str = ""
    
    def __post_init__(self):
        self.depth = len(self.links)
        if not self.total_strength and self.links:
            # Calculate combined strength
            self.total_strength = 1.0
            for link in self.links:
                self.total_strength *= link.strength
