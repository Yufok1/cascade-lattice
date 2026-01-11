"""
Cascade Analysis - Bidirectional Causation Tracer.

Trace cause-effect chains forwards and backwards through time.
Find root causes. Predict cascading effects.
"""

from typing import List, Dict, Any, Optional, Set
from collections import deque
from dataclasses import dataclass, field

from cascade.core.event import Event, CausationLink, CausationChain
from cascade.core.graph import CausationGraph


@dataclass
class RootCauseAnalysis:
    """Results of a root cause analysis."""
    target_event: Event
    root_causes: List[Event]
    chains: List[CausationChain]
    deepest_depth: int = 0
    narrative: str = ""


@dataclass 
class ImpactAnalysis:
    """Results of an impact/forward analysis."""
    source_event: Event
    effects: List[Event]
    chains: List[CausationChain]
    total_impact_count: int = 0
    severity_score: float = 0.0
    narrative: str = ""


@dataclass
class CascadePrediction:
    """Prediction of likely cascade from an event."""
    source_event: Event
    predicted_effects: List[Dict[str, Any]]  # [{event_type, probability, time_estimate}, ...]
    risk_score: float = 0.0
    intervention_points: List[str] = field(default_factory=list)
    narrative: str = ""


class Tracer:
    """
    Bidirectional causation tracer.
    
    Traces cause-effect chains through the causation graph:
    - Backwards: "What caused this?" → find root causes
    - Forwards: "What will this cause?" → predict cascades
    
    Example:
        >>> tracer = Tracer(graph)
        >>> 
        >>> # What caused this gradient explosion?
        >>> causes = tracer.trace_backwards("evt_123")
        >>> 
        >>> # What will this learning rate change cause?
        >>> effects = tracer.trace_forwards("evt_456")
        >>> 
        >>> # Deep root cause analysis
        >>> roots = tracer.find_root_causes("evt_789")
    """
    
    def __init__(self, graph: CausationGraph):
        """
        Initialize tracer with a causation graph.
        
        Args:
            graph: The causation graph to trace through
        """
        self.graph = graph
        self._prediction_model = None  # Future: ML model for predictions
    
    def trace_backwards(self, event_id: str, max_depth: int = 1000) -> List[CausationChain]:
        """
        Trace causation backwards: what caused this event?
        
        Args:
            event_id: ID of the event to trace from
            max_depth: Maximum depth to trace (default: 1000 - effectively unlimited)
            
        Returns:
            List of CausationChain objects, one per causal path found
        """
        target = self.graph.get_event(event_id)
        if not target:
            return []
        
        chains = []
        self._trace_backwards_recursive(event_id, [], [], max_depth, chains)
        
        # Sort by depth (longest chain first for root cause analysis)
        chains.sort(key=lambda c: c.depth, reverse=True)
        return chains
    
    def _trace_backwards_recursive(
        self, 
        current_id: str, 
        current_events: List[Event],
        current_links: List[CausationLink],
        depth_remaining: int,
        results: List[CausationChain],
        visited: Optional[Set[str]] = None
    ) -> None:
        """Recursive helper for backwards tracing."""
        if visited is None:
            visited = set()
        
        if current_id in visited:
            return  # Avoid cycles
        visited.add(current_id)
        
        current_event = self.graph.get_event(current_id)
        if not current_event:
            return
        
        current_events = [current_event] + current_events
        
        if depth_remaining <= 0:
            # Max depth reached, record this chain
            if len(current_events) > 1:
                results.append(self._build_chain(current_events, current_links))
            return
        
        causes = self.graph.get_causes(current_id)
        
        if not causes:
            # This is a root - record the chain
            if len(current_events) >= 1:
                results.append(self._build_chain(current_events, current_links))
            return
        
        for cause in causes:
            link = self.graph.get_link(cause.event_id, current_id)
            new_links = [link] + current_links if link else current_links
            
            self._trace_backwards_recursive(
                cause.event_id,
                current_events,
                new_links,
                depth_remaining - 1,
                results,
                visited.copy()
            )
    
    def trace_forwards(self, event_id: str, max_depth: int = 1000) -> List[CausationChain]:
        """
        Trace causation forwards: what will this event cause?
        
        Args:
            event_id: ID of the event to trace from
            max_depth: Maximum depth to trace (default: 1000 - effectively unlimited)
            
        Returns:
            List of CausationChain objects, one per effect path found
        """
        source = self.graph.get_event(event_id)
        if not source:
            return []
        
        chains = []
        self._trace_forwards_recursive(event_id, [], [], max_depth, chains)
        
        # Sort by depth
        chains.sort(key=lambda c: c.depth, reverse=True)
        return chains
    
    def _trace_forwards_recursive(
        self,
        current_id: str,
        current_events: List[Event],
        current_links: List[CausationLink],
        depth_remaining: int,
        results: List[CausationChain],
        visited: Optional[Set[str]] = None
    ) -> None:
        """Recursive helper for forwards tracing."""
        if visited is None:
            visited = set()
        
        if current_id in visited:
            return
        visited.add(current_id)
        
        current_event = self.graph.get_event(current_id)
        if not current_event:
            return
        
        current_events = current_events + [current_event]
        
        if depth_remaining <= 0:
            if len(current_events) > 1:
                results.append(self._build_chain(current_events, current_links))
            return
        
        effects = self.graph.get_effects(current_id)
        
        if not effects:
            # This is a leaf - record the chain
            if len(current_events) >= 1:
                results.append(self._build_chain(current_events, current_links))
            return
        
        for effect in effects:
            link = self.graph.get_link(current_id, effect.event_id)
            new_links = current_links + [link] if link else current_links
            
            self._trace_forwards_recursive(
                effect.event_id,
                current_events,
                new_links,
                depth_remaining - 1,
                results,
                visited.copy()
            )
    
    def find_root_causes(self, event_id: str, max_depth: int = 1000) -> RootCauseAnalysis:
        """
        Deep root cause analysis: find the ultimate origins.
        
        Traces all the way back to find events with no causes.
        
        Args:
            event_id: ID of the event to analyze
            max_depth: Maximum depth to search (default: 1000 - effectively unlimited)
            
        Returns:
            RootCauseAnalysis with root causes and narrative
        """
        target = self.graph.get_event(event_id)
        if not target:
            return RootCauseAnalysis(
                target_event=None,
                root_causes=[],
                chains=[],
            )
        
        chains = self.trace_backwards(event_id, max_depth)
        
        # Extract root causes (events at the start of chains)
        root_causes = []
        seen = set()
        for chain in chains:
            if chain.events:
                root = chain.events[0]
                if root.event_id not in seen:
                    root_causes.append(root)
                    seen.add(root.event_id)
        
        # Build narrative
        narrative = self._build_root_cause_narrative(target, root_causes, chains)
        
        return RootCauseAnalysis(
            target_event=target,
            root_causes=root_causes,
            chains=chains,
            deepest_depth=max(c.depth for c in chains) if chains else 0,
            narrative=narrative,
        )
    
    def analyze_impact(self, event_id: str, max_depth: int = 1000) -> ImpactAnalysis:
        """
        Impact analysis: what were ALL downstream effects?
        
        Traces forward to find everything this event set in motion.
        
        Args:
            event_id: ID of the event to analyze
            max_depth: Maximum depth to search (default: 1000 - effectively unlimited)
            
        Returns:
            ImpactAnalysis with effects and severity score
        """
        source = self.graph.get_event(event_id)
        if not source:
            return ImpactAnalysis(
                source_event=None,
                effects=[],
                chains=[],
            )
        
        chains = self.trace_forwards(event_id, max_depth)
        
        # Extract all effects
        effects = []
        seen = set()
        for chain in chains:
            for event in chain.events[1:]:  # Skip source
                if event.event_id not in seen:
                    effects.append(event)
                    seen.add(event.event_id)
        
        # Calculate severity
        severity = self._calculate_impact_severity(source, effects)
        
        # Build narrative
        narrative = self._build_impact_narrative(source, effects, chains)
        
        return ImpactAnalysis(
            source_event=source,
            effects=effects,
            chains=chains,
            total_impact_count=len(effects),
            severity_score=severity,
            narrative=narrative,
        )
    
    def predict_cascade(self, event_id: str) -> CascadePrediction:
        """
        Predict likely cascade from this event.
        
        Uses learned patterns to forecast effects BEFORE they happen.
        This is the "Minority Report" capability.
        
        Args:
            event_id: ID of the event to predict from
            
        Returns:
            CascadePrediction with risk scores and intervention points
        """
        source = self.graph.get_event(event_id)
        if not source:
            return CascadePrediction(
                source_event=None,
                predicted_effects=[],
            )
        
        # Get historical patterns for this event type
        similar_events = self.graph.get_events_by_type(source.event_type)
        
        # Count what typically follows - use all available history for better predictions
        # No artificial cap - system learns from full history
        effect_counts: Dict[str, int] = {}
        analysis_window = similar_events  # Full history, no slice
        for similar in analysis_window:
            effects = self.graph.get_effects(similar.event_id)
            for effect in effects:
                key = effect.event_type
                effect_counts[key] = effect_counts.get(key, 0) + 1
        
        # Convert to predictions
        total = len(analysis_window)
        predictions = []
        for event_type, count in sorted(effect_counts.items(), key=lambda x: -x[1]):
            predictions.append({
                "event_type": event_type,
                "probability": count / total if total > 0 else 0,
                "historical_count": count,
            })
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(source, predictions)
        
        # Identify intervention points
        intervention_points = self._find_intervention_points(source, predictions)
        
        return CascadePrediction(
            source_event=source,
            predicted_effects=predictions[:10],  # Top 10
            risk_score=risk_score,
            intervention_points=intervention_points,
            narrative=f"Based on {total} similar events, predicting {len(predictions)} likely effects.",
        )
    
    def _build_chain(self, events: List[Event], links: List[CausationLink]) -> CausationChain:
        """Build a CausationChain from events and links."""
        total_strength = 1.0
        for link in links:
            total_strength *= link.strength
        
        return CausationChain(
            events=events,
            links=links,
            total_strength=total_strength,
            depth=len(links),
        )
    
    def _build_root_cause_narrative(
        self, 
        target: Event, 
        roots: List[Event],
        chains: List[CausationChain]
    ) -> str:
        """Build human-readable narrative for root cause analysis."""
        if not roots:
            return f"No root causes found for {target.event_type}"
        
        lines = [f"Root cause analysis for {target.event_type}:"]
        lines.append(f"Found {len(roots)} root cause(s) across {len(chains)} causal chain(s).")
        lines.append("")
        
        for i, root in enumerate(roots[:5], 1):  # Top 5
            lines.append(f"{i}. {root.component}/{root.event_type}")
            if root.data:
                key_data = list(root.data.items())[:3]
                lines.append(f"   Data: {dict(key_data)}")
        
        return "\n".join(lines)
    
    def _build_impact_narrative(
        self,
        source: Event,
        effects: List[Event],
        chains: List[CausationChain]
    ) -> str:
        """Build human-readable narrative for impact analysis."""
        if not effects:
            return f"No downstream effects found for {source.event_type}"
        
        lines = [f"Impact analysis for {source.event_type}:"]
        lines.append(f"Found {len(effects)} downstream effect(s).")
        lines.append("")
        
        # Group by event type
        by_type: Dict[str, int] = {}
        for effect in effects:
            by_type[effect.event_type] = by_type.get(effect.event_type, 0) + 1
        
        for event_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  • {event_type}: {count} occurrence(s)")
        
        return "\n".join(lines)
    
    def _calculate_impact_severity(self, source: Event, effects: List[Event]) -> float:
        """Calculate severity score for an impact (0.0 to 1.0)."""
        if not effects:
            return 0.0
        
        # Factors: number of effects, types of effects
        count_score = min(1.0, len(effects) / 20)  # 20+ effects = max
        
        # High-severity event types
        severe_types = {'error', 'anomaly', 'crash', 'failure', 'explosion'}
        severe_count = sum(1 for e in effects if e.event_type in severe_types)
        severity_score = min(1.0, severe_count / 5)
        
        return (count_score + severity_score) / 2
    
    def _calculate_risk_score(
        self, 
        source: Event, 
        predictions: List[Dict[str, Any]]
    ) -> float:
        """Calculate risk score for a cascade prediction."""
        if not predictions:
            return 0.0
        
        # High-risk event types
        risky_types = {'error', 'anomaly', 'crash', 'failure', 'explosion', 'nan', 'overflow'}
        
        risk = 0.0
        for pred in predictions:
            if pred["event_type"] in risky_types:
                risk += pred["probability"] * 2  # Double weight for risky
            else:
                risk += pred["probability"] * 0.5
        
        return min(1.0, risk)
    
    def _find_intervention_points(
        self,
        source: Event,
        predictions: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify points where intervention could prevent bad cascades."""
        points = []
        
        # Look at source event data for intervention hints
        if 'learning_rate' in source.data:
            points.append("Reduce learning rate")
        if 'gradient' in source.event_type.lower():
            points.append("Apply gradient clipping")
        if source.data.get('loss', 0) > 10:
            points.append("Check loss function / data")
        
        # Check predictions for severe outcomes
        for pred in predictions:
            if pred["event_type"] == "nan" and pred["probability"] > 0.3:
                points.append("Enable NaN detection early stopping")
            if pred["event_type"] == "overflow" and pred["probability"] > 0.3:
                points.append("Apply gradient scaling")
        
        return points
