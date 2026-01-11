"""
Cascade Core - Causation Graph Engine.

The graph stores events and their causal relationships, enabling
bidirectional traversal through time.
"""

import threading
from typing import Dict, List, Optional, Set, Any, Iterator
from collections import defaultdict
from datetime import datetime

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from cascade.core.event import Event, CausationLink


class CausationGraph:
    """
    A directed graph of causal relationships between events.
    
    The graph enables bidirectional traversal:
    - Backwards: "What caused this event?"
    - Forwards: "What did this event cause?"
    
    Thread-safe for concurrent event ingestion.
    
    Example:
        >>> graph = CausationGraph()
        >>> graph.add_event(event1)
        >>> graph.add_event(event2)
        >>> graph.add_link(CausationLink(
        ...     from_event=event1.event_id,
        ...     to_event=event2.event_id,
        ...     causation_type="temporal",
        ...     strength=0.9
        ... ))
        >>> 
        >>> # Find what caused event2
        >>> causes = graph.get_causes(event2.event_id)
    """
    
    def __init__(self):
        """Initialize an empty causation graph."""
        self._lock = threading.RLock()
        
        # Event storage
        self._events: Dict[str, Event] = {}
        self._events_by_component: Dict[str, List[str]] = defaultdict(list)
        self._events_by_type: Dict[str, List[str]] = defaultdict(list)
        self._events_by_time: List[str] = []  # Ordered by timestamp
        
        # Link storage
        self._links: Dict[str, CausationLink] = {}  # link_id -> link
        self._causes: Dict[str, Set[str]] = defaultdict(set)  # event_id -> set of cause event_ids
        self._effects: Dict[str, Set[str]] = defaultdict(set)  # event_id -> set of effect event_ids
        
        # NetworkX graph for advanced algorithms (optional)
        if HAS_NETWORKX:
            self._nx_graph = nx.DiGraph()
        else:
            self._nx_graph = None
        
        # Statistics
        self._event_count = 0
        self._link_count = 0
    
    def add_event(self, event: Event) -> None:
        """
        Add an event to the graph.
        
        Thread-safe. Automatically detects potential causations with recent events.
        
        Args:
            event: The event to add
        """
        with self._lock:
            if event.event_id in self._events:
                return  # Already exists
            
            self._events[event.event_id] = event
            self._events_by_component[event.component].append(event.event_id)
            self._events_by_type[event.event_type].append(event.event_id)
            self._events_by_time.append(event.event_id)
            self._event_count += 1
            
            if self._nx_graph is not None:
                self._nx_graph.add_node(event.event_id, **event.to_dict())
    
    def add_link(self, link: CausationLink) -> None:
        """
        Add a causal link between two events.
        
        Thread-safe.
        
        Args:
            link: The causation link to add
        """
        with self._lock:
            link_id = f"{link.from_event}->{link.to_event}"
            
            if link_id in self._links:
                # Update existing link if new one is stronger
                if link.strength > self._links[link_id].strength:
                    self._links[link_id] = link
                return
            
            self._links[link_id] = link
            self._causes[link.to_event].add(link.from_event)
            self._effects[link.from_event].add(link.to_event)
            self._link_count += 1
            
            if self._nx_graph is not None:
                self._nx_graph.add_edge(
                    link.from_event, 
                    link.to_event,
                    **link.to_dict()
                )
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        with self._lock:
            return self._events.get(event_id)
    
    def get_causes(self, event_id: str) -> List[Event]:
        """
        Get all events that directly caused this event.
        
        Args:
            event_id: ID of the effect event
            
        Returns:
            List of causing events
        """
        with self._lock:
            cause_ids = self._causes.get(event_id, set())
            return [self._events[cid] for cid in cause_ids if cid in self._events]
    
    def get_effects(self, event_id: str) -> List[Event]:
        """
        Get all events that were directly caused by this event.
        
        Args:
            event_id: ID of the cause event
            
        Returns:
            List of effect events
        """
        with self._lock:
            effect_ids = self._effects.get(event_id, set())
            return [self._events[eid] for eid in effect_ids if eid in self._events]
    
    def get_link(self, from_event: str, to_event: str) -> Optional[CausationLink]:
        """Get the causation link between two events."""
        with self._lock:
            link_id = f"{from_event}->{to_event}"
            return self._links.get(link_id)
    
    def get_all_links(self) -> List[CausationLink]:
        """Get all causal links in the graph."""
        with self._lock:
            return list(self._links.values())
    
    def get_component_connections(self) -> Dict[str, Dict[str, float]]:
        """
        Aggregate causal links into component-to-component connections.
        
        Returns:
            Dict mapping (from_component, to_component) -> total strength
        """
        with self._lock:
            connections: Dict[tuple, float] = {}
            
            for link in self._links.values():
                from_event = self._events.get(link.from_event)
                to_event = self._events.get(link.to_event)
                
                if from_event and to_event:
                    from_comp = from_event.component
                    to_comp = to_event.component
                    
                    if from_comp != to_comp:  # Skip self-links
                        key = (from_comp, to_comp)
                        connections[key] = connections.get(key, 0) + link.strength
            
            return connections
    
    def get_recent_events(self, count: int = 100) -> List[Event]:
        """Get the most recent events by timestamp."""
        with self._lock:
            ids = self._events_by_time[-count:]
            return [self._events[eid] for eid in reversed(ids)]
    
    def get_events_by_component(self, component: str) -> List[Event]:
        """Get all events from a specific component."""
        with self._lock:
            ids = self._events_by_component.get(component, [])
            return [self._events[eid] for eid in ids]
    
    def get_events_by_type(self, event_type: str) -> List[Event]:
        """Get all events of a specific type."""
        with self._lock:
            ids = self._events_by_type.get(event_type, [])
            return [self._events[eid] for eid in ids]
    
    def find_path(self, from_event: str, to_event: str) -> Optional[List[str]]:
        """
        Find the shortest causal path between two events.
        
        Uses NetworkX if available, otherwise falls back to BFS.
        
        Args:
            from_event: Starting event ID
            to_event: Target event ID
            
        Returns:
            List of event IDs in the path, or None if no path exists
        """
        with self._lock:
            if self._nx_graph is not None:
                try:
                    return nx.shortest_path(self._nx_graph, from_event, to_event)
                except nx.NetworkXNoPath:
                    return None
                except nx.NodeNotFound:
                    return None
            else:
                # BFS fallback
                return self._bfs_path(from_event, to_event)
    
    def _bfs_path(self, from_event: str, to_event: str) -> Optional[List[str]]:
        """BFS path finding without NetworkX."""
        from collections import deque
        
        if from_event not in self._events or to_event not in self._events:
            return None
        
        queue = deque([(from_event, [from_event])])
        visited = {from_event}
        
        while queue:
            current, path = queue.popleft()
            
            if current == to_event:
                return path
            
            for effect_id in self._effects.get(current, set()):
                if effect_id not in visited:
                    visited.add(effect_id)
                    queue.append((effect_id, path + [effect_id]))
        
        return None
    
    def get_root_events(self) -> List[Event]:
        """Get events with no causes (entry points)."""
        with self._lock:
            roots = []
            for event_id, event in self._events.items():
                if not self._causes.get(event_id):
                    roots.append(event)
            return sorted(roots, key=lambda e: e.timestamp)
    
    def get_leaf_events(self) -> List[Event]:
        """Get events with no effects (endpoints)."""
        with self._lock:
            leaves = []
            for event_id, event in self._events.items():
                if not self._effects.get(event_id):
                    leaves.append(event)
            return sorted(leaves, key=lambda e: e.timestamp, reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the graph."""
        with self._lock:
            return {
                "event_count": self._event_count,
                "link_count": self._link_count,
                "components": list(self._events_by_component.keys()),
                "event_types": list(self._events_by_type.keys()),
                "root_count": len(self.get_root_events()),
                "leaf_count": len(self.get_leaf_events()),
            }
    
    def __len__(self) -> int:
        return self._event_count
    
    def __repr__(self) -> str:
        return f"<CausationGraph | {self._event_count} events, {self._link_count} links>"
