"""
CASCADE MoE System Analyzer - Mixture of Expert Specialists.

The MoE routes system observations to domain-specific analysts based on
detected topology. Each specialist understands the causal patterns
unique to their domain.

Architecture:
    ParsedEvents → SystemClassifier (Router) → Specialist Analyzer → CausationGraph + Insights

Specialists:
    - MLTrainingSpecialist: loss curves, gradient health, convergence
    - WebServiceSpecialist: request flows, latency chains, error cascades
    - MicroservicesSpecialist: distributed traces, service dependencies
    - DatabaseSpecialist: query patterns, lock chains, transaction flows
    - ContainerSpecialist: pod lifecycles, resource pressure, scheduling
    - GenericSpecialist: fallback temporal analysis
"""

import re
import math
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from collections import defaultdict

from cascade.core.event import Event, CausationLink
from cascade.core.graph import CausationGraph
from cascade.system.adapter import ParsedEvent


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM TOPOLOGY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class SystemTopology:
    """Detected system topology with confidence scores."""
    
    ML_TRAINING = "ml_training"
    WEB_SERVICE = "web_service"
    MICROSERVICES = "microservices"
    DATABASE = "database"
    CONTAINER_ORCHESTRATION = "container_orchestration"
    MESSAGE_QUEUE = "message_queue"
    GENERIC = "generic"
    
    # Signal patterns for each topology
    TOPOLOGY_SIGNALS: Dict[str, Dict[str, List[str]]] = {
        ML_TRAINING: {
            "components": ["model", "trainer", "optimizer", "scheduler", "checkpoint", 
                          "dataloader", "loss", "gradient", "epoch", "batch"],
            "event_types": ["checkpoint", "training", "validation", "inference",
                           "gradient_update", "lr_schedule", "early_stop"],
            "metrics": ["loss", "accuracy", "lr", "grad_norm", "epoch", "batch",
                       "perplexity", "mfu", "tokens_per_sec"],
            "patterns": [r"epoch.*\d+", r"loss.*\d+\.\d+", r"step.*\d+", r"grad.*norm"]
        },
        WEB_SERVICE: {
            "components": ["nginx", "apache", "api", "gateway", "handler", "router",
                          "controller", "middleware", "auth", "session"],
            "event_types": ["request", "response", "redirect", "error", "timeout",
                           "rate_limit", "auth_failure", "cache_hit", "cache_miss"],
            "metrics": ["latency", "response_time", "status_code", "request_count",
                       "error_rate", "throughput", "p99", "p95"],
            "patterns": [r"GET|POST|PUT|DELETE", r"\d{3}\s", r"HTTP/\d\.\d", r"/api/"]
        },
        MICROSERVICES: {
            "components": ["service", "svc", "grpc", "rpc", "proxy", "envoy", "istio",
                          "consul", "eureka", "discovery"],
            "event_types": ["trace", "span", "call", "rpc_start", "rpc_end",
                           "circuit_breaker", "retry", "fallback", "timeout"],
            "metrics": ["trace_id", "span_id", "parent_span", "duration_ms",
                       "service_latency", "hop_count", "retry_count"],
            "patterns": [r"trace[-_]?id", r"span[-_]?id", r"correlation[-_]?id"]
        },
        DATABASE: {
            "components": ["mysql", "postgres", "postgresql", "mongodb", "redis",
                          "oracle", "sqlserver", "query", "transaction", "connection"],
            "event_types": ["query", "transaction_start", "transaction_commit",
                           "transaction_rollback", "deadlock", "lock_wait", "slow_query"],
            "metrics": ["query_time", "rows_affected", "rows_scanned", "lock_time",
                       "connections", "buffer_pool", "cache_hit_ratio"],
            "patterns": [r"SELECT|INSERT|UPDATE|DELETE", r"BEGIN|COMMIT|ROLLBACK"]
        },
        CONTAINER_ORCHESTRATION: {
            "components": ["kubernetes", "k8s", "docker", "pod", "container", "node",
                          "deployment", "kubelet", "scheduler", "controller"],
            "event_types": ["pod_scheduled", "container_started", "container_killed",
                           "oom_killed", "evicted", "scaling", "rolling_update"],
            "metrics": ["cpu_usage", "memory_usage", "cpu_limit", "memory_limit",
                       "restart_count", "ready_replicas", "available_replicas"],
            "patterns": [r"pod/", r"deployment/", r"namespace/", r"k8s\.io"]
        },
        MESSAGE_QUEUE: {
            "components": ["kafka", "rabbitmq", "sqs", "pubsub", "nats", "activemq",
                          "producer", "consumer", "queue", "topic", "broker"],
            "event_types": ["message_published", "message_consumed", "message_acked",
                           "message_nacked", "consumer_lag", "rebalance"],
            "metrics": ["queue_depth", "consumer_lag", "messages_per_sec",
                       "partition_offset", "consumer_group_lag"],
            "patterns": [r"topic[-_]", r"partition[-_]?\d+", r"offset[-_]?\d+"]
        },
    }


@dataclass
class TopologyClassification:
    """Result of system topology classification."""
    primary: str  # Primary detected topology
    confidence: float  # 0.0 - 1.0
    all_scores: Dict[str, float]  # Scores for all topologies
    evidence: Dict[str, List[str]]  # What signals matched
    hybrid: bool = False  # Is this a hybrid system?
    secondary: Optional[str] = None  # Secondary topology if hybrid


class SystemClassifier:
    """
    MoE Router - Classifies system topology from parsed events.
    
    Examines components, event types, metrics, and text patterns
    to determine what kind of system produced these logs.
    """
    
    def __init__(self):
        self.signals = SystemTopology.TOPOLOGY_SIGNALS
    
    def classify(self, events: List[ParsedEvent]) -> TopologyClassification:
        """
        Classify the system topology from parsed events.
        
        Args:
            events: List of parsed events from adapter
            
        Returns:
            TopologyClassification with scores and evidence
        """
        if not events:
            return TopologyClassification(
                primary=SystemTopology.GENERIC,
                confidence=0.0,
                all_scores={},
                evidence={},
            )
        
        # Collect all signals from events
        all_components: Set[str] = set()
        all_event_types: Set[str] = set()
        all_metrics: Set[str] = set()
        all_text: List[str] = []
        
        for event in events:
            all_components.add(event.component.lower())
            all_event_types.add(event.event_type.lower())
            
            # Extract metrics from data
            if isinstance(event.data, dict):
                all_metrics.update(k.lower() for k in event.data.keys())
            
            # Collect raw text for pattern matching
            if event.data.get("message"):
                all_text.append(str(event.data["message"]))
            if event.data.get("raw"):
                all_text.append(str(event.data["raw"]))
        
        combined_text = " ".join(all_text)
        
        # Score each topology
        scores: Dict[str, float] = {}
        evidence: Dict[str, List[str]] = {}
        
        for topology, signals in self.signals.items():
            score, matched = self._score_topology(
                topology, signals,
                all_components, all_event_types, all_metrics, combined_text
            )
            scores[topology] = score
            evidence[topology] = matched
        
        # Determine primary topology
        if not scores or max(scores.values()) == 0:
            return TopologyClassification(
                primary=SystemTopology.GENERIC,
                confidence=0.0,
                all_scores=scores,
                evidence=evidence,
            )
        
        # Sort by score
        sorted_topologies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_topologies[0][0]
        primary_score = sorted_topologies[0][1]
        
        # Normalize confidence to 0-1
        max_possible = 4.0  # 4 signal types
        confidence = min(primary_score / max_possible, 1.0)
        
        # Check for hybrid (second topology has significant score)
        hybrid = False
        secondary = None
        if len(sorted_topologies) > 1:
            second_score = sorted_topologies[1][1]
            if second_score > primary_score * 0.5:  # Second is at least 50% of primary
                hybrid = True
                secondary = sorted_topologies[1][0]
        
        return TopologyClassification(
            primary=primary,
            confidence=confidence,
            all_scores=scores,
            evidence=evidence,
            hybrid=hybrid,
            secondary=secondary,
        )
    
    def _score_topology(
        self,
        topology: str,
        signals: Dict[str, List[str]],
        components: Set[str],
        event_types: Set[str],
        metrics: Set[str],
        text: str,
    ) -> Tuple[float, List[str]]:
        """Score how well events match a topology."""
        score = 0.0
        matched = []
        
        # Component matches
        comp_matches = components & set(s.lower() for s in signals.get("components", []))
        if comp_matches:
            score += len(comp_matches) / max(len(signals.get("components", [1])), 1)
            matched.extend([f"component:{c}" for c in list(comp_matches)[:3]])
        
        # Event type matches
        type_matches = event_types & set(s.lower() for s in signals.get("event_types", []))
        if type_matches:
            score += len(type_matches) / max(len(signals.get("event_types", [1])), 1)
            matched.extend([f"type:{t}" for t in list(type_matches)[:3]])
        
        # Metric matches
        metric_signals = set(s.lower() for s in signals.get("metrics", []))
        metric_matches = metrics & metric_signals
        # Also check partial matches (e.g., "train_loss" contains "loss")
        for metric in metrics:
            for signal in metric_signals:
                if signal in metric and signal not in metric_matches:
                    metric_matches.add(signal)
        if metric_matches:
            score += len(metric_matches) / max(len(signals.get("metrics", [1])), 1)
            matched.extend([f"metric:{m}" for m in list(metric_matches)[:3]])
        
        # Pattern matches
        text_lower = text.lower()
        pattern_matches = 0
        for pattern in signals.get("patterns", []):
            if re.search(pattern, text, re.IGNORECASE):
                pattern_matches += 1
                matched.append(f"pattern:{pattern[:20]}")
        if pattern_matches:
            score += pattern_matches / max(len(signals.get("patterns", [1])), 1)
        
        return score, matched


# ═══════════════════════════════════════════════════════════════════════════════
# SPECIALIST ANALYZERS - Domain Experts
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AnalysisInsight:
    """A single insight from specialist analysis."""
    category: str  # "causal", "anomaly", "pattern", "recommendation"
    severity: str  # "info", "warning", "critical"
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)
    affected_events: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "affected_events": self.affected_events,
        }


@dataclass
class SpecialistAnalysis:
    """Complete analysis from a specialist."""
    topology: str
    specialist: str
    confidence: float
    insights: List[AnalysisInsight] = field(default_factory=list)
    causal_links: List[CausationLink] = field(default_factory=list)
    metrics_summary: Dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topology": self.topology,
            "specialist": self.specialist,
            "confidence": self.confidence,
            "insights": [i.to_dict() for i in self.insights],
            "causal_links_count": len(self.causal_links),
            "metrics_summary": self.metrics_summary,
            "narrative": self.narrative,
        }


class BaseSpecialist(ABC):
    """Base class for domain specialist analyzers."""
    
    name: str = "base"
    topology: str = SystemTopology.GENERIC
    
    @abstractmethod
    def analyze(self, events: List[ParsedEvent], graph: CausationGraph) -> SpecialistAnalysis:
        """
        Analyze events and build causal understanding.
        
        Args:
            events: Parsed events from the system
            graph: CausationGraph to populate with causal links
            
        Returns:
            SpecialistAnalysis with insights and causal links
        """
        pass
    
    def _find_temporal_chains(
        self,
        events: List[ParsedEvent],
        window_ms: float = 1000.0
    ) -> List[Tuple[ParsedEvent, ParsedEvent]]:
        """Find temporally close event pairs (potential causation)."""
        chains = []
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        for i, event in enumerate(sorted_events[:-1]):
            for j in range(i + 1, min(i + 10, len(sorted_events))):
                next_event = sorted_events[j]
                time_delta = (next_event.timestamp - event.timestamp) * 1000
                if 0 < time_delta <= window_ms:
                    chains.append((event, next_event))
                elif time_delta > window_ms:
                    break
        
        return chains
    
    def _create_causal_link(
        self,
        from_event: ParsedEvent,
        to_event: ParsedEvent,
        causation_type: str,
        strength: float = 0.5,
        explanation: str = "",
    ) -> CausationLink:
        """Create a causal link between events."""
        return CausationLink(
            from_event=from_event.event_hash,
            to_event=to_event.event_hash,
            causation_type=causation_type,
            strength=strength,
            explanation=explanation or f"{from_event.component} → {to_event.component}",
        )


class MLTrainingSpecialist(BaseSpecialist):
    """
    Specialist for ML Training systems.
    
    Understands:
    - Training loops (epoch → batch → step)
    - Loss dynamics and convergence
    - Gradient health (vanishing/exploding)
    - Checkpoint causation
    - Learning rate schedules
    """
    
    name = "ml_training_specialist"
    topology = SystemTopology.ML_TRAINING
    
    def analyze(self, events: List[ParsedEvent], graph: CausationGraph) -> SpecialistAnalysis:
        analysis = SpecialistAnalysis(
            topology=self.topology,
            specialist=self.name,
            confidence=0.0,
        )
        
        # Group events by epoch/step
        epochs: Dict[int, List[ParsedEvent]] = defaultdict(list)
        losses: List[Tuple[float, float]] = []  # (timestamp, loss)
        grad_norms: List[Tuple[float, float]] = []
        checkpoints: List[ParsedEvent] = []
        
        for event in events:
            data = event.data or {}
            
            # Extract epoch
            epoch = data.get("epoch") or data.get("ep")
            if epoch is not None:
                try:
                    epochs[int(epoch)].append(event)
                except (ValueError, TypeError):
                    pass
            
            # Extract loss
            loss = data.get("loss") or data.get("train_loss")
            if loss is not None:
                try:
                    losses.append((event.timestamp, float(loss)))
                except (ValueError, TypeError):
                    pass
            
            # Extract gradient norm
            grad = data.get("grad_norm") or data.get("gradient_norm")
            if grad is not None:
                try:
                    grad_norms.append((event.timestamp, float(grad)))
                except (ValueError, TypeError):
                    pass
            
            # Find checkpoints
            if event.event_type == "checkpoint" or "checkpoint" in event.component.lower():
                checkpoints.append(event)
        
        # Build causal chains: epoch flow
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        prev_event = None
        for event in sorted_events:
            if prev_event and prev_event.component == event.component:
                # Same component temporal chain
                link = self._create_causal_link(
                    prev_event, event,
                    causation_type="temporal_sequence",
                    strength=0.7,
                    explanation=f"Sequential {event.component} events"
                )
                analysis.causal_links.append(link)
            prev_event = event
        
        # Checkpoint causation (checkpoint follows training events)
        for checkpoint in checkpoints:
            # Find training events just before checkpoint
            for event in sorted_events:
                if event.timestamp < checkpoint.timestamp:
                    time_delta = checkpoint.timestamp - event.timestamp
                    if time_delta < 60:  # Within 60 seconds
                        link = self._create_causal_link(
                            event, checkpoint,
                            causation_type="checkpoint_trigger",
                            strength=0.8,
                            explanation="Training event triggered checkpoint"
                        )
                        analysis.causal_links.append(link)
                        break  # Only link to most recent
        
        # Analyze loss curve
        if len(losses) >= 3:
            losses_sorted = sorted(losses, key=lambda x: x[0])
            loss_values = [l[1] for l in losses_sorted]
            
            # Check convergence
            if loss_values[-1] < loss_values[0]:
                trend = "converging"
                analysis.insights.append(AnalysisInsight(
                    category="pattern",
                    severity="info",
                    title="Training Converging",
                    description=f"Loss decreased from {loss_values[0]:.4f} to {loss_values[-1]:.4f}",
                    evidence=[f"loss_start={loss_values[0]:.4f}", f"loss_end={loss_values[-1]:.4f}"]
                ))
            else:
                trend = "diverging"
                analysis.insights.append(AnalysisInsight(
                    category="anomaly",
                    severity="warning",
                    title="Training May Be Diverging",
                    description=f"Loss increased from {loss_values[0]:.4f} to {loss_values[-1]:.4f}",
                    evidence=[f"loss_start={loss_values[0]:.4f}", f"loss_end={loss_values[-1]:.4f}"]
                ))
            
            # Check for loss spikes
            mean_loss = sum(loss_values) / len(loss_values)
            for i, loss in enumerate(loss_values):
                if loss > mean_loss * 3:
                    analysis.insights.append(AnalysisInsight(
                        category="anomaly",
                        severity="critical",
                        title="Loss Spike Detected",
                        description=f"Loss spiked to {loss:.4f} (mean: {mean_loss:.4f})",
                        evidence=[f"spike_value={loss:.4f}", f"mean={mean_loss:.4f}"]
                    ))
        
        # Analyze gradient health
        if grad_norms:
            grad_values = [g[1] for g in grad_norms]
            mean_grad = sum(grad_values) / len(grad_values)
            
            if mean_grad < 1e-7:
                analysis.insights.append(AnalysisInsight(
                    category="anomaly",
                    severity="critical",
                    title="Vanishing Gradients",
                    description=f"Mean gradient norm {mean_grad:.2e} is dangerously low",
                    evidence=[f"mean_grad_norm={mean_grad:.2e}"]
                ))
            elif mean_grad > 100:
                analysis.insights.append(AnalysisInsight(
                    category="anomaly",
                    severity="critical",
                    title="Exploding Gradients",
                    description=f"Mean gradient norm {mean_grad:.2f} is very high",
                    evidence=[f"mean_grad_norm={mean_grad:.2f}"]
                ))
        
        # Build narrative
        analysis.confidence = min(len(events) / 50, 1.0)
        analysis.metrics_summary = {
            "epochs_observed": len(epochs),
            "loss_samples": len(losses),
            "gradient_samples": len(grad_norms),
            "checkpoints": len(checkpoints),
        }
        
        analysis.narrative = self._build_narrative(analysis, losses, grad_norms, epochs)
        
        return analysis
    
    def _build_narrative(
        self,
        analysis: SpecialistAnalysis,
        losses: List[Tuple[float, float]],
        grad_norms: List[Tuple[float, float]],
        epochs: Dict[int, List[ParsedEvent]]
    ) -> str:
        """Build human-readable narrative."""
        parts = [f"🧠 **ML Training Analysis** (confidence: {analysis.confidence:.0%})"]
        
        if epochs:
            parts.append(f"\n📊 Observed {len(epochs)} epochs")
        if losses:
            loss_values = [l[1] for l in losses]
            parts.append(f"📉 Loss range: {min(loss_values):.4f} → {max(loss_values):.4f}")
        if grad_norms:
            grad_values = [g[1] for g in grad_norms]
            parts.append(f"🔬 Gradient norm range: {min(grad_values):.2e} → {max(grad_values):.2e}")
        
        if analysis.insights:
            critical = [i for i in analysis.insights if i.severity == "critical"]
            warnings = [i for i in analysis.insights if i.severity == "warning"]
            if critical:
                parts.append(f"\n⚠️ **{len(critical)} critical issues detected**")
            if warnings:
                parts.append(f"⚡ {len(warnings)} warnings")
        
        parts.append(f"\n🔗 Identified {len(analysis.causal_links)} causal relationships")
        
        return "\n".join(parts)


class WebServiceSpecialist(BaseSpecialist):
    """
    Specialist for Web Service systems.
    
    Understands:
    - Request → Response chains
    - Error cascades (4xx → retry → 5xx)
    - Latency bottlenecks
    - Rate limiting effects
    """
    
    name = "web_service_specialist"
    topology = SystemTopology.WEB_SERVICE
    
    def analyze(self, events: List[ParsedEvent], graph: CausationGraph) -> SpecialistAnalysis:
        analysis = SpecialistAnalysis(
            topology=self.topology,
            specialist=self.name,
            confidence=0.0,
        )
        
        # Categorize events
        requests: List[ParsedEvent] = []
        errors: List[ParsedEvent] = []
        latencies: List[float] = []
        status_codes: Dict[int, int] = defaultdict(int)
        
        for event in events:
            data = event.data or {}
            
            # Identify requests
            if event.event_type in ["request", "response"] or "request" in str(data).lower():
                requests.append(event)
            
            # Identify errors
            if event.event_type in ["error", "exception", "failure"]:
                errors.append(event)
            
            # Extract status codes
            status = data.get("status") or data.get("status_code") or data.get("http_status")
            if status:
                try:
                    status_codes[int(status)] += 1
                except (ValueError, TypeError):
                    pass
            
            # Extract latency
            latency = data.get("latency") or data.get("response_time") or data.get("duration")
            if latency:
                try:
                    latencies.append(float(latency))
                except (ValueError, TypeError):
                    pass
        
        # Build request → error causal chains
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        for i, event in enumerate(sorted_events):
            if event.event_type in ["error", "exception", "failure"]:
                # Look for preceding request
                for j in range(i - 1, max(i - 10, -1), -1):
                    prev = sorted_events[j]
                    if prev.event_type in ["request", "info"]:
                        time_delta = event.timestamp - prev.timestamp
                        if time_delta < 30:  # Within 30 seconds
                            link = self._create_causal_link(
                                prev, event,
                                causation_type="request_failure",
                                strength=0.8,
                                explanation="Request led to error response"
                            )
                            analysis.causal_links.append(link)
                            break
        
        # Analyze error patterns
        error_count = len(errors)
        total_count = len(events)
        if total_count > 0:
            error_rate = error_count / total_count
            if error_rate > 0.1:
                analysis.insights.append(AnalysisInsight(
                    category="anomaly",
                    severity="critical" if error_rate > 0.3 else "warning",
                    title="High Error Rate",
                    description=f"Error rate is {error_rate:.1%} ({error_count}/{total_count} events)",
                    evidence=[f"error_rate={error_rate:.1%}"]
                ))
        
        # Analyze status codes
        error_statuses = sum(v for k, v in status_codes.items() if k >= 400)
        if error_statuses > 0:
            analysis.insights.append(AnalysisInsight(
                category="pattern",
                severity="warning" if error_statuses > 10 else "info",
                title="HTTP Errors Detected",
                description=f"Found {error_statuses} 4xx/5xx responses",
                evidence=[f"{k}: {v}" for k, v in status_codes.items() if k >= 400]
            ))
        
        # Analyze latency
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            p95_idx = int(len(latencies) * 0.95)
            p95 = sorted(latencies)[p95_idx] if p95_idx < len(latencies) else max_latency
            
            analysis.metrics_summary["avg_latency"] = avg_latency
            analysis.metrics_summary["max_latency"] = max_latency
            analysis.metrics_summary["p95_latency"] = p95
            
            if p95 > avg_latency * 3:
                analysis.insights.append(AnalysisInsight(
                    category="anomaly",
                    severity="warning",
                    title="Latency Outliers",
                    description=f"P95 latency ({p95:.0f}ms) is 3x+ average ({avg_latency:.0f}ms)",
                    evidence=[f"avg={avg_latency:.0f}ms", f"p95={p95:.0f}ms"]
                ))
        
        analysis.confidence = min(len(events) / 100, 1.0)
        analysis.metrics_summary["total_requests"] = len(requests)
        analysis.metrics_summary["total_errors"] = error_count
        analysis.metrics_summary["status_codes"] = dict(status_codes)
        
        analysis.narrative = self._build_narrative(analysis, status_codes, latencies)
        
        return analysis
    
    def _build_narrative(
        self,
        analysis: SpecialistAnalysis,
        status_codes: Dict[int, int],
        latencies: List[float]
    ) -> str:
        parts = [f"🌐 **Web Service Analysis** (confidence: {analysis.confidence:.0%})"]
        
        total_requests = sum(status_codes.values())
        if total_requests:
            success = sum(v for k, v in status_codes.items() if 200 <= k < 400)
            parts.append(f"\n📊 {total_requests} requests, {success} successful")
        
        if latencies:
            parts.append(f"⏱️ Avg latency: {sum(latencies)/len(latencies):.0f}ms")
        
        if analysis.insights:
            critical = [i for i in analysis.insights if i.severity == "critical"]
            if critical:
                parts.append(f"\n🚨 **{len(critical)} critical issues**")
        
        parts.append(f"\n🔗 {len(analysis.causal_links)} causal chains identified")
        
        return "\n".join(parts)


class MicroservicesSpecialist(BaseSpecialist):
    """Specialist for distributed microservices systems."""
    
    name = "microservices_specialist"
    topology = SystemTopology.MICROSERVICES
    
    def analyze(self, events: List[ParsedEvent], graph: CausationGraph) -> SpecialistAnalysis:
        analysis = SpecialistAnalysis(
            topology=self.topology,
            specialist=self.name,
            confidence=0.0,
        )
        
        # Group by trace_id
        traces: Dict[str, List[ParsedEvent]] = defaultdict(list)
        services: Set[str] = set()
        
        for event in events:
            data = event.data or {}
            trace_id = data.get("trace_id") or data.get("traceId") or data.get("correlation_id")
            if trace_id:
                traces[str(trace_id)].append(event)
            services.add(event.component)
        
        # Build service dependency graph from traces
        service_calls: Dict[Tuple[str, str], int] = defaultdict(int)
        
        for trace_id, trace_events in traces.items():
            sorted_trace = sorted(trace_events, key=lambda e: e.timestamp)
            for i in range(len(sorted_trace) - 1):
                from_svc = sorted_trace[i].component
                to_svc = sorted_trace[i + 1].component
                if from_svc != to_svc:
                    service_calls[(from_svc, to_svc)] += 1
                    
                    # Create causal link
                    link = self._create_causal_link(
                        sorted_trace[i], sorted_trace[i + 1],
                        causation_type="service_call",
                        strength=0.9,
                        explanation=f"Trace {trace_id[:8]}... call chain"
                    )
                    analysis.causal_links.append(link)
        
        # Identify hot paths
        if service_calls:
            hottest = max(service_calls.items(), key=lambda x: x[1])
            analysis.insights.append(AnalysisInsight(
                category="pattern",
                severity="info",
                title="Hot Service Path",
                description=f"{hottest[0][0]} → {hottest[0][1]} called {hottest[1]} times",
                evidence=[f"call_count={hottest[1]}"]
            ))
        
        analysis.confidence = min(len(traces) / 20, 1.0)
        analysis.metrics_summary = {
            "services": list(services),
            "traces": len(traces),
            "service_calls": len(service_calls),
        }
        
        analysis.narrative = f"🔀 **Microservices Analysis**\n{len(services)} services, {len(traces)} traces\n🔗 {len(analysis.causal_links)} call chains"
        
        return analysis


class GenericSpecialist(BaseSpecialist):
    """Fallback specialist for unrecognized systems."""
    
    name = "generic_specialist"
    topology = SystemTopology.GENERIC
    
    def analyze(self, events: List[ParsedEvent], graph: CausationGraph) -> SpecialistAnalysis:
        analysis = SpecialistAnalysis(
            topology=self.topology,
            specialist=self.name,
            confidence=0.3,  # Low confidence for generic
        )
        
        # Basic temporal chaining
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        components = defaultdict(list)
        
        for event in sorted_events:
            components[event.component].append(event)
        
        # Chain events within same component
        for comp, comp_events in components.items():
            for i in range(len(comp_events) - 1):
                link = self._create_causal_link(
                    comp_events[i], comp_events[i + 1],
                    causation_type="temporal",
                    strength=0.5,
                    explanation=f"Temporal sequence in {comp}"
                )
                analysis.causal_links.append(link)
        
        # Find error cascades
        errors = [e for e in sorted_events if e.event_type in ["error", "exception", "failure", "warning"]]
        if errors:
            analysis.insights.append(AnalysisInsight(
                category="pattern",
                severity="warning" if len(errors) > 5 else "info",
                title="Error Events Detected",
                description=f"Found {len(errors)} error/warning events",
                evidence=[f"error_count={len(errors)}"]
            ))
        
        analysis.metrics_summary = {
            "total_events": len(events),
            "components": len(components),
            "error_events": len(errors),
        }
        
        analysis.narrative = f"📋 **Generic Analysis**\n{len(events)} events across {len(components)} components\n🔗 {len(analysis.causal_links)} temporal chains"
        
        return analysis


# ═══════════════════════════════════════════════════════════════════════════════
# MoE ANALYZER - The Router + Specialists Combined
# ═══════════════════════════════════════════════════════════════════════════════

class MoEAnalyzer:
    """
    Mixture of Experts System Analyzer.
    
    Routes system observations to domain-specific specialists based on
    detected topology. Combines classification + specialist analysis
    into a unified analysis pipeline.
    
    Usage:
        analyzer = MoEAnalyzer()
        result = analyzer.analyze(parsed_events)
        
        print(result.classification)  # What system was detected
        print(result.analysis)        # Deep specialist analysis
        print(result.graph)           # Populated CausationGraph
    """
    
    def __init__(self):
        self.classifier = SystemClassifier()
        
        # Register specialists
        self.specialists: Dict[str, BaseSpecialist] = {
            SystemTopology.ML_TRAINING: MLTrainingSpecialist(),
            SystemTopology.WEB_SERVICE: WebServiceSpecialist(),
            SystemTopology.MICROSERVICES: MicroservicesSpecialist(),
            SystemTopology.GENERIC: GenericSpecialist(),
            # Add more as needed:
            # SystemTopology.DATABASE: DatabaseSpecialist(),
            # SystemTopology.CONTAINER_ORCHESTRATION: ContainerSpecialist(),
        }
        
        self.default_specialist = GenericSpecialist()
    
    def analyze(self, events: List[ParsedEvent]) -> 'MoEAnalysisResult':
        """
        Analyze events through the MoE pipeline.
        
        1. Classify system topology
        2. Route to appropriate specialist
        3. Build causation graph
        4. Return combined analysis
        
        Args:
            events: Parsed events from UniversalAdapter
            
        Returns:
            MoEAnalysisResult with classification, analysis, and graph
        """
        # Step 1: Classify
        classification = self.classifier.classify(events)
        
        # Step 2: Create causation graph
        graph = CausationGraph()
        
        # Add all events to graph
        for event in events:
            cascade_event = Event(
                timestamp=event.timestamp,
                event_type=event.event_type,
                component=event.component,
                data={
                    **event.data,
                    "hash": event.event_hash,
                    "parent_hash": event.parent_hash,
                },
            )
            graph.add_event(cascade_event)
        
        # Step 3: Route to specialist
        specialist = self.specialists.get(
            classification.primary,
            self.default_specialist
        )
        
        analysis = specialist.analyze(events, graph)
        
        # Add causal links to graph
        for link in analysis.causal_links:
            graph.add_link(link)
        
        # Step 4: If hybrid, also run secondary specialist
        secondary_analysis = None
        if classification.hybrid and classification.secondary:
            secondary_specialist = self.specialists.get(
                classification.secondary,
                self.default_specialist
            )
            if secondary_specialist.name != specialist.name:
                secondary_analysis = secondary_specialist.analyze(events, graph)
                for link in secondary_analysis.causal_links:
                    graph.add_link(link)
        
        return MoEAnalysisResult(
            classification=classification,
            primary_analysis=analysis,
            secondary_analysis=secondary_analysis,
            graph=graph,
            events=events,
        )
    
    def get_available_specialists(self) -> List[str]:
        """List all available specialists."""
        return list(self.specialists.keys())


@dataclass
class MoEAnalysisResult:
    """Complete result from MoE analysis pipeline."""
    
    classification: TopologyClassification
    primary_analysis: SpecialistAnalysis
    secondary_analysis: Optional[SpecialistAnalysis]
    graph: CausationGraph
    events: List[ParsedEvent]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON/display."""
        return {
            "classification": {
                "primary": self.classification.primary,
                "confidence": self.classification.confidence,
                "hybrid": self.classification.hybrid,
                "secondary": self.classification.secondary,
                "all_scores": self.classification.all_scores,
                "evidence": self.classification.evidence,
            },
            "primary_analysis": self.primary_analysis.to_dict(),
            "secondary_analysis": self.secondary_analysis.to_dict() if self.secondary_analysis else None,
            "graph_stats": self.graph.get_stats(),
            "event_count": len(self.events),
        }
    
    def get_narrative(self) -> str:
        """Get combined narrative from all analyses."""
        parts = []
        
        # Classification summary
        parts.append(f"## 🔍 System Classification")
        parts.append(f"**Detected:** {self.classification.primary.replace('_', ' ').title()}")
        parts.append(f"**Confidence:** {self.classification.confidence:.0%}")
        
        if self.classification.hybrid:
            parts.append(f"**Hybrid with:** {self.classification.secondary.replace('_', ' ').title()}")
        
        # Evidence
        if self.classification.evidence.get(self.classification.primary):
            parts.append(f"\n**Evidence:** {', '.join(self.classification.evidence[self.classification.primary][:5])}")
        
        # Primary analysis
        parts.append(f"\n---\n{self.primary_analysis.narrative}")
        
        # Secondary analysis
        if self.secondary_analysis:
            parts.append(f"\n---\n{self.secondary_analysis.narrative}")
        
        # Graph stats
        stats = self.graph.get_stats()
        parts.append(f"\n---\n## 🕸️ Causation Graph")
        parts.append(f"- **Events:** {stats['event_count']}")
        parts.append(f"- **Causal Links:** {stats['link_count']}")
        parts.append(f"- **Root Causes:** {stats['root_count']}")
        parts.append(f"- **Leaf Effects:** {stats['leaf_count']}")
        
        return "\n".join(parts)
    
    def get_all_insights(self) -> List[AnalysisInsight]:
        """Get all insights from all analyses."""
        insights = list(self.primary_analysis.insights)
        if self.secondary_analysis:
            insights.extend(self.secondary_analysis.insights)
        return insights
    
    def get_critical_insights(self) -> List[AnalysisInsight]:
        """Get only critical severity insights."""
        return [i for i in self.get_all_insights() if i.severity == "critical"]
