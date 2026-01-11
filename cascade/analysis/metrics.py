"""
Cascade Analysis - Metrics Engine.

The quantification layer. Extracts, tracks, and correlates numeric data
from the event stream. Provides the WHAT with enough depth that the WHY
becomes self-evident to the observer.

This module does NOT interpret or explain. It quantifies.

Industry-Standard Neural Network Observability Taxonomy:
=========================================================

CATEGORY 1: TRAINING_DYNAMICS
    Core training loop metrics - loss, accuracy, learning rate, throughput
    
CATEGORY 2: GRADIENT_HEALTH  
    Gradient flow diagnostics - norms, clipping, vanishing/exploding
    
CATEGORY 3: WEIGHT_DYNAMICS
    Parameter evolution - norms, update ratios, dead neurons
    
CATEGORY 4: ACTIVATION_FLOW
    Forward pass health - magnitudes, saturation, dead ReLUs
    
CATEGORY 5: ATTENTION_MECHANICS
    Transformer-specific - entropy, sparsity, head importance
    
CATEGORY 6: MEMORY_COMPUTE
    Resource utilization - GPU/CPU memory, MFU, throughput
    
CATEGORY 7: OPTIMIZATION_STATE
    Optimizer internals - Adam moments, momentum, weight decay
    
CATEGORY 8: CONVERGENCE_SIGNALS
    Training health indicators - plateau, overfitting, noise scale
    
CATEGORY 9: DATA_PIPELINE
    Data loading metrics - batch time, queue depth, prefetch
    
CATEGORY 10: REGULARIZATION
    Regularization effects - dropout, batch norm, layer norm stats
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum, auto
import math
import re

from cascade.core.event import Event
from cascade.core.graph import CausationGraph


# =============================================================================
# METRIC CATEGORY TAXONOMY
# =============================================================================

class MetricCategory(Enum):
    """Industry-standard neural network metric categories."""
    TRAINING_DYNAMICS = auto()    # Loss, accuracy, LR, throughput
    GRADIENT_HEALTH = auto()      # Grad norms, clipping, flow
    WEIGHT_DYNAMICS = auto()      # Weight norms, updates, dead neurons
    ACTIVATION_FLOW = auto()      # Activation stats, saturation
    ATTENTION_MECHANICS = auto()  # Attention entropy, sparsity, heads
    MEMORY_COMPUTE = auto()       # GPU/CPU mem, MFU, FLOPS
    OPTIMIZATION_STATE = auto()   # Adam moments, momentum, decay
    CONVERGENCE_SIGNALS = auto()  # Plateau, overfit, noise scale
    DATA_PIPELINE = auto()        # Batch time, queue, prefetch
    REGULARIZATION = auto()       # Dropout, norm layer stats
    SYSTEM = auto()               # Iteration, epoch, timestamps
    UNKNOWN = auto()              # Uncategorized metrics


# Comprehensive metric-to-category mapping
# This is the "knowledge base" of neural network metric taxonomy
METRIC_TAXONOMY: Dict[str, MetricCategory] = {
    # TRAINING_DYNAMICS
    "loss": MetricCategory.TRAINING_DYNAMICS,
    "train_loss": MetricCategory.TRAINING_DYNAMICS,
    "val_loss": MetricCategory.TRAINING_DYNAMICS,
    "test_loss": MetricCategory.TRAINING_DYNAMICS,
    "eval_loss": MetricCategory.TRAINING_DYNAMICS,
    "nll_loss": MetricCategory.TRAINING_DYNAMICS,
    "ce_loss": MetricCategory.TRAINING_DYNAMICS,
    "cross_entropy": MetricCategory.TRAINING_DYNAMICS,
    "mse_loss": MetricCategory.TRAINING_DYNAMICS,
    "mae_loss": MetricCategory.TRAINING_DYNAMICS,
    "perplexity": MetricCategory.TRAINING_DYNAMICS,
    "ppl": MetricCategory.TRAINING_DYNAMICS,
    "accuracy": MetricCategory.TRAINING_DYNAMICS,
    "acc": MetricCategory.TRAINING_DYNAMICS,
    "top1_acc": MetricCategory.TRAINING_DYNAMICS,
    "top5_acc": MetricCategory.TRAINING_DYNAMICS,
    "precision": MetricCategory.TRAINING_DYNAMICS,
    "recall": MetricCategory.TRAINING_DYNAMICS,
    "f1": MetricCategory.TRAINING_DYNAMICS,
    "f1_score": MetricCategory.TRAINING_DYNAMICS,
    "auc": MetricCategory.TRAINING_DYNAMICS,
    "auroc": MetricCategory.TRAINING_DYNAMICS,
    "bleu": MetricCategory.TRAINING_DYNAMICS,
    "rouge": MetricCategory.TRAINING_DYNAMICS,
    "lr": MetricCategory.TRAINING_DYNAMICS,
    "learning_rate": MetricCategory.TRAINING_DYNAMICS,
    "samples_per_sec": MetricCategory.TRAINING_DYNAMICS,
    "tokens_per_sec": MetricCategory.TRAINING_DYNAMICS,
    "throughput": MetricCategory.TRAINING_DYNAMICS,
    "steps_per_sec": MetricCategory.TRAINING_DYNAMICS,
    
    # GRADIENT_HEALTH
    "grad_norm": MetricCategory.GRADIENT_HEALTH,
    "gradient_norm": MetricCategory.GRADIENT_HEALTH,
    "global_grad_norm": MetricCategory.GRADIENT_HEALTH,
    "grad_norm_clipped": MetricCategory.GRADIENT_HEALTH,
    "grad_clip_rate": MetricCategory.GRADIENT_HEALTH,
    "grad_scale": MetricCategory.GRADIENT_HEALTH,
    "grad_mean": MetricCategory.GRADIENT_HEALTH,
    "grad_std": MetricCategory.GRADIENT_HEALTH,
    "grad_max": MetricCategory.GRADIENT_HEALTH,
    "grad_min": MetricCategory.GRADIENT_HEALTH,
    "grad_sparsity": MetricCategory.GRADIENT_HEALTH,
    "vanishing_grad": MetricCategory.GRADIENT_HEALTH,
    "exploding_grad": MetricCategory.GRADIENT_HEALTH,
    
    # WEIGHT_DYNAMICS
    "weight_norm": MetricCategory.WEIGHT_DYNAMICS,
    "param_norm": MetricCategory.WEIGHT_DYNAMICS,
    "weight_mean": MetricCategory.WEIGHT_DYNAMICS,
    "weight_std": MetricCategory.WEIGHT_DYNAMICS,
    "update_ratio": MetricCategory.WEIGHT_DYNAMICS,
    "weight_update": MetricCategory.WEIGHT_DYNAMICS,
    "dead_neurons": MetricCategory.WEIGHT_DYNAMICS,
    "dead_neuron_pct": MetricCategory.WEIGHT_DYNAMICS,
    "param_count": MetricCategory.WEIGHT_DYNAMICS,
    "num_params": MetricCategory.WEIGHT_DYNAMICS,
    "trainable_params": MetricCategory.WEIGHT_DYNAMICS,
    
    # ACTIVATION_FLOW
    "activation_mean": MetricCategory.ACTIVATION_FLOW,
    "activation_std": MetricCategory.ACTIVATION_FLOW,
    "activation_norm": MetricCategory.ACTIVATION_FLOW,
    "activation_max": MetricCategory.ACTIVATION_FLOW,
    "saturation": MetricCategory.ACTIVATION_FLOW,
    "saturation_pct": MetricCategory.ACTIVATION_FLOW,
    "dead_relu": MetricCategory.ACTIVATION_FLOW,
    "dead_relu_pct": MetricCategory.ACTIVATION_FLOW,
    "activation_sparsity": MetricCategory.ACTIVATION_FLOW,
    # Generic activation stats from layer hooks
    "mean": MetricCategory.ACTIVATION_FLOW,
    "std": MetricCategory.ACTIVATION_FLOW,
    "min": MetricCategory.ACTIVATION_FLOW,
    "max": MetricCategory.ACTIVATION_FLOW,
    "sparsity": MetricCategory.ACTIVATION_FLOW,
    "layer_idx": MetricCategory.SYSTEM,
    
    # ATTENTION_MECHANICS
    "attention_entropy": MetricCategory.ATTENTION_MECHANICS,
    "attn_entropy": MetricCategory.ATTENTION_MECHANICS,
    "attention_sparsity": MetricCategory.ATTENTION_MECHANICS,
    "head_importance": MetricCategory.ATTENTION_MECHANICS,
    "attention_weight_norm": MetricCategory.ATTENTION_MECHANICS,
    "position_bias": MetricCategory.ATTENTION_MECHANICS,
    "attention_score_mean": MetricCategory.ATTENTION_MECHANICS,
    "attention_score_std": MetricCategory.ATTENTION_MECHANICS,
    
    # MEMORY_COMPUTE
    "gpu_memory": MetricCategory.MEMORY_COMPUTE,
    "gpu_mem": MetricCategory.MEMORY_COMPUTE,
    "gpu_memory_allocated": MetricCategory.MEMORY_COMPUTE,
    "gpu_memory_cached": MetricCategory.MEMORY_COMPUTE,
    "gpu_memory_peak": MetricCategory.MEMORY_COMPUTE,
    "cpu_memory": MetricCategory.MEMORY_COMPUTE,
    "memory_usage": MetricCategory.MEMORY_COMPUTE,
    "mfu": MetricCategory.MEMORY_COMPUTE,
    "model_flops_utilization": MetricCategory.MEMORY_COMPUTE,
    "flops": MetricCategory.MEMORY_COMPUTE,
    "tflops": MetricCategory.MEMORY_COMPUTE,
    "gpu_utilization": MetricCategory.MEMORY_COMPUTE,
    "gpu_util": MetricCategory.MEMORY_COMPUTE,
    
    # OPTIMIZATION_STATE
    "adam_m_norm": MetricCategory.OPTIMIZATION_STATE,
    "adam_v_norm": MetricCategory.OPTIMIZATION_STATE,
    "momentum": MetricCategory.OPTIMIZATION_STATE,
    "beta1": MetricCategory.OPTIMIZATION_STATE,
    "beta2": MetricCategory.OPTIMIZATION_STATE,
    "weight_decay": MetricCategory.OPTIMIZATION_STATE,
    "effective_weight_decay": MetricCategory.OPTIMIZATION_STATE,
    "warmup_progress": MetricCategory.OPTIMIZATION_STATE,
    "lr_schedule_progress": MetricCategory.OPTIMIZATION_STATE,
    
    # CONVERGENCE_SIGNALS
    "train_val_gap": MetricCategory.CONVERGENCE_SIGNALS,
    "overfit_ratio": MetricCategory.CONVERGENCE_SIGNALS,
    "loss_plateau": MetricCategory.CONVERGENCE_SIGNALS,
    "gradient_noise_scale": MetricCategory.CONVERGENCE_SIGNALS,
    "critical_batch_size": MetricCategory.CONVERGENCE_SIGNALS,
    "effective_batch_size": MetricCategory.CONVERGENCE_SIGNALS,
    "early_stop_score": MetricCategory.CONVERGENCE_SIGNALS,
    "best_val_loss": MetricCategory.CONVERGENCE_SIGNALS,
    "improvement_rate": MetricCategory.CONVERGENCE_SIGNALS,
    
    # DATA_PIPELINE
    "data_time": MetricCategory.DATA_PIPELINE,
    "batch_time": MetricCategory.DATA_PIPELINE,
    "load_time": MetricCategory.DATA_PIPELINE,
    "preprocessing_time": MetricCategory.DATA_PIPELINE,
    "augmentation_time": MetricCategory.DATA_PIPELINE,
    "queue_depth": MetricCategory.DATA_PIPELINE,
    "prefetch_factor": MetricCategory.DATA_PIPELINE,
    "num_workers": MetricCategory.DATA_PIPELINE,
    
    # REGULARIZATION
    "dropout_rate": MetricCategory.REGULARIZATION,
    "dropout": MetricCategory.REGULARIZATION,
    "bn_mean": MetricCategory.REGULARIZATION,
    "bn_var": MetricCategory.REGULARIZATION,
    "bn_running_mean": MetricCategory.REGULARIZATION,
    "bn_running_var": MetricCategory.REGULARIZATION,
    "ln_mean": MetricCategory.REGULARIZATION,
    "ln_var": MetricCategory.REGULARIZATION,
    "l1_penalty": MetricCategory.REGULARIZATION,
    "l2_penalty": MetricCategory.REGULARIZATION,
    
    # SYSTEM
    "iter": MetricCategory.SYSTEM,
    "iteration": MetricCategory.SYSTEM,
    "step": MetricCategory.SYSTEM,
    "total": MetricCategory.SYSTEM,
    "epoch": MetricCategory.SYSTEM,
    "batch": MetricCategory.SYSTEM,
    "batch_idx": MetricCategory.SYSTEM,
    "global_step": MetricCategory.SYSTEM,
    "time": MetricCategory.SYSTEM,
    "dt": MetricCategory.SYSTEM,
    "elapsed": MetricCategory.SYSTEM,
    "wall_time": MetricCategory.SYSTEM,
    "timestamp": MetricCategory.SYSTEM,
    "hooked_layers": MetricCategory.SYSTEM,
    "input_tokens": MetricCategory.SYSTEM,
    "predicted_class": MetricCategory.TRAINING_DYNAMICS,
    
    # MODEL INFO
    "params": MetricCategory.WEIGHT_DYNAMICS,
    "num_params": MetricCategory.WEIGHT_DYNAMICS,
    "total_params": MetricCategory.WEIGHT_DYNAMICS,
    "trainable_params": MetricCategory.WEIGHT_DYNAMICS,
    "parameters": MetricCategory.WEIGHT_DYNAMICS,
    "model_size": MetricCategory.WEIGHT_DYNAMICS,
    
    # INFERENCE METRICS
    "confidence": MetricCategory.TRAINING_DYNAMICS,
    "similarity": MetricCategory.TRAINING_DYNAMICS,
    "score": MetricCategory.TRAINING_DYNAMICS,
    "prob": MetricCategory.TRAINING_DYNAMICS,
    "probability": MetricCategory.TRAINING_DYNAMICS,
    "entropy": MetricCategory.ATTENTION_MECHANICS,
    "latency": MetricCategory.MEMORY_COMPUTE,
    "inference_time": MetricCategory.MEMORY_COMPUTE,
    "input_len": MetricCategory.DATA_PIPELINE,
    "output_len": MetricCategory.DATA_PIPELINE,
    
    # OBSERVATION SYSTEM METRICS
    "hooked_modules": MetricCategory.SYSTEM,
    "total_layers": MetricCategory.SYSTEM,
    "sample_rate": MetricCategory.SYSTEM,
    "layer_num": MetricCategory.SYSTEM,
    "max_depth": MetricCategory.SYSTEM,
    "return_code": MetricCategory.SYSTEM,
    "pid": MetricCategory.SYSTEM,
    "max_iterations": MetricCategory.SYSTEM,
    "total_iterations": MetricCategory.SYSTEM,
    "iterations": MetricCategory.SYSTEM,
    
    # GPU/VRAM
    "vram_gb": MetricCategory.MEMORY_COMPUTE,
    "gpu_count": MetricCategory.MEMORY_COMPUTE,
    "gpu_memory_gb": MetricCategory.MEMORY_COMPUTE,
}

# Patterns for dynamic metric name matching
METRIC_PATTERNS: List[Tuple[str, MetricCategory]] = [
    (r".*loss.*", MetricCategory.TRAINING_DYNAMICS),
    (r".*acc.*", MetricCategory.TRAINING_DYNAMICS),
    (r".*accuracy.*", MetricCategory.TRAINING_DYNAMICS),
    (r".*perplexity.*", MetricCategory.TRAINING_DYNAMICS),
    (r".*lr.*", MetricCategory.TRAINING_DYNAMICS),
    (r".*learning_rate.*", MetricCategory.TRAINING_DYNAMICS),
    (r".*grad.*norm.*", MetricCategory.GRADIENT_HEALTH),
    (r".*gradient.*", MetricCategory.GRADIENT_HEALTH),
    (r".*weight.*norm.*", MetricCategory.WEIGHT_DYNAMICS),
    (r".*param.*norm.*", MetricCategory.WEIGHT_DYNAMICS),
    (r".*activation.*", MetricCategory.ACTIVATION_FLOW),
    (r".*attention.*", MetricCategory.ATTENTION_MECHANICS),
    (r".*attn.*", MetricCategory.ATTENTION_MECHANICS),
    (r".*memory.*", MetricCategory.MEMORY_COMPUTE),
    (r".*gpu.*", MetricCategory.MEMORY_COMPUTE),
    (r".*mfu.*", MetricCategory.MEMORY_COMPUTE),
    (r".*adam.*", MetricCategory.OPTIMIZATION_STATE),
    (r".*momentum.*", MetricCategory.OPTIMIZATION_STATE),
    (r".*overfit.*", MetricCategory.CONVERGENCE_SIGNALS),
    (r".*plateau.*", MetricCategory.CONVERGENCE_SIGNALS),
    (r".*data.*time.*", MetricCategory.DATA_PIPELINE),
    (r".*batch.*time.*", MetricCategory.DATA_PIPELINE),
    (r".*dropout.*", MetricCategory.REGULARIZATION),
    (r".*bn_.*", MetricCategory.REGULARIZATION),
    (r".*ln_.*", MetricCategory.REGULARIZATION),
    (r".*iter.*", MetricCategory.SYSTEM),
    (r".*epoch.*", MetricCategory.SYSTEM),
    (r".*step.*", MetricCategory.SYSTEM),
    (r".*time.*", MetricCategory.SYSTEM),
    (r".*_ms$", MetricCategory.SYSTEM),
    (r".*duration.*", MetricCategory.SYSTEM),
]


def classify_metric(name: str) -> MetricCategory:
    """Classify a metric name into its category."""
    name_lower = name.lower()
    
    # Direct lookup
    if name_lower in METRIC_TAXONOMY:
        return METRIC_TAXONOMY[name_lower]
    
    # Pattern matching
    for pattern, category in METRIC_PATTERNS:
        if re.match(pattern, name_lower):
            return category
    
    return MetricCategory.UNKNOWN


# =============================================================================
# METRIC HEALTH THRESHOLDS (Industry Standards)
# =============================================================================

@dataclass
class MetricHealthSpec:
    """Specification for healthy metric ranges."""
    name: str
    category: MetricCategory
    healthy_min: Optional[float] = None
    healthy_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    expected_trend: Optional[str] = None  # 'falling', 'rising', 'stable'
    
    def is_healthy(self, value: float) -> bool:
        if self.healthy_min is not None and value < self.healthy_min:
            return False
        if self.healthy_max is not None and value > self.healthy_max:
            return False
        return True
    
    def is_critical(self, value: float) -> bool:
        if self.critical_min is not None and value < self.critical_min:
            return True
        if self.critical_max is not None and value > self.critical_max:
            return True
        return False


# Industry-standard health thresholds
HEALTH_SPECS: Dict[str, MetricHealthSpec] = {
    "loss": MetricHealthSpec(
        name="loss",
        category=MetricCategory.TRAINING_DYNAMICS,
        healthy_max=10.0,
        critical_max=100.0,
        expected_trend="falling",
    ),
    "grad_norm": MetricHealthSpec(
        name="grad_norm",
        category=MetricCategory.GRADIENT_HEALTH,
        healthy_min=1e-7,
        healthy_max=10.0,
        critical_min=1e-10,  # Vanishing
        critical_max=1000.0,  # Exploding
    ),
    "lr": MetricHealthSpec(
        name="lr",
        category=MetricCategory.TRAINING_DYNAMICS,
        healthy_min=1e-8,
        healthy_max=1.0,
        critical_max=10.0,
    ),
    "mfu": MetricHealthSpec(
        name="mfu",
        category=MetricCategory.MEMORY_COMPUTE,
        healthy_min=0.1,  # 10% utilization minimum
        healthy_max=1.0,
    ),
    "dead_relu_pct": MetricHealthSpec(
        name="dead_relu_pct",
        category=MetricCategory.ACTIVATION_FLOW,
        healthy_max=0.3,  # 30% dead is concerning
        critical_max=0.7,  # 70% dead is critical
    ),
    "train_val_gap": MetricHealthSpec(
        name="train_val_gap",
        category=MetricCategory.CONVERGENCE_SIGNALS,
        healthy_max=0.5,  # Gap shouldn't exceed 50% of train loss
        critical_max=2.0,  # Severe overfitting
    ),
}


@dataclass
class MetricSeries:
    """A time series of a single metric with category awareness."""
    name: str
    category: MetricCategory = field(default=MetricCategory.UNKNOWN)
    values: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    event_ids: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.category == MetricCategory.UNKNOWN:
            self.category = classify_metric(self.name)
    
    @property
    def count(self) -> int:
        return len(self.values)
    
    @property
    def current(self) -> Optional[float]:
        return self.values[-1] if self.values else None
    
    @property
    def previous(self) -> Optional[float]:
        return self.values[-2] if len(self.values) >= 2 else None
    
    @property
    def delta(self) -> Optional[float]:
        """Change from previous to current."""
        if len(self.values) >= 2:
            return self.values[-1] - self.values[-2]
        return None
    
    @property
    def delta_pct(self) -> Optional[float]:
        """Percentage change from previous to current."""
        if len(self.values) >= 2 and self.values[-2] != 0:
            return (self.values[-1] - self.values[-2]) / abs(self.values[-2])
        return None
    
    @property
    def mean(self) -> Optional[float]:
        return sum(self.values) / len(self.values) if self.values else None
    
    @property
    def std(self) -> Optional[float]:
        if len(self.values) < 2:
            return None
        mean = self.mean
        variance = sum((x - mean) ** 2 for x in self.values) / len(self.values)
        return math.sqrt(variance)
    
    @property
    def min(self) -> Optional[float]:
        return min(self.values) if self.values else None
    
    @property
    def max(self) -> Optional[float]:
        return max(self.values) if self.values else None
    
    @property 
    def range(self) -> Optional[float]:
        if self.values:
            return self.max - self.min
        return None
    
    def moving_average(self, window: int = 5) -> Optional[float]:
        """Compute moving average over last N values."""
        if len(self.values) < window:
            return self.mean
        return sum(self.values[-window:]) / window
    
    def rate_of_change(self, window: int = 5) -> Optional[float]:
        """Average rate of change over last N values."""
        if len(self.values) < 2:
            return None
        window = min(window, len(self.values))
        recent = self.values[-window:]
        deltas = [recent[i] - recent[i-1] for i in range(1, len(recent))]
        return sum(deltas) / len(deltas) if deltas else None
    
    def is_anomaly(self, threshold_std: float = 2.0) -> bool:
        """Is current value anomalous (outside N standard deviations)?"""
        if len(self.values) < 5 or self.std is None or self.std == 0:
            return False
        return abs(self.values[-1] - self.mean) > threshold_std * self.std
    
    def trend(self, window: int = 10) -> str:
        """Determine trend: 'rising', 'falling', 'stable', 'volatile'."""
        if len(self.values) < 3:
            return "unknown"
        
        window = min(window, len(self.values))
        recent = self.values[-window:]
        deltas = [recent[i] - recent[i-1] for i in range(1, len(recent))]
        
        positive = sum(1 for d in deltas if d > 0)
        negative = sum(1 for d in deltas if d < 0)
        
        if positive > 0.7 * len(deltas):
            return "rising"
        elif negative > 0.7 * len(deltas):
            return "falling"
        elif self.std and self.mean and self.std > 0.1 * abs(self.mean):
            return "volatile"
        else:
            return "stable"
    
    def health_status(self) -> str:
        """Check health against industry standards. Returns 'healthy', 'warning', 'critical', 'unknown'."""
        if self.current is None:
            return "unknown"
        
        name_lower = self.name.lower()
        if name_lower in HEALTH_SPECS:
            spec = HEALTH_SPECS[name_lower]
            if spec.is_critical(self.current):
                return "critical"
            if not spec.is_healthy(self.current):
                return "warning"
            return "healthy"
        
        # Default heuristics for unknown metrics
        if self.is_anomaly(threshold_std=3.0):
            return "critical"
        if self.is_anomaly(threshold_std=2.0):
            return "warning"
        return "healthy"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.name,
            "count": self.count,
            "current": self.current,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "trend": self.trend(),
            "health": self.health_status(),
            "is_anomaly": self.is_anomaly(),
            "rate_of_change": self.rate_of_change(),
        }


@dataclass
class Anomaly:
    """A detected anomaly in the metric stream."""
    metric_name: str
    category: MetricCategory
    event_id: str
    timestamp: float
    value: float
    expected_range: Tuple[float, float]  # (low, high)
    deviation_std: float
    severity: str  # 'minor', 'major', 'critical'


@dataclass
class Correlation:
    """A detected correlation between two metrics."""
    metric_a: str
    metric_b: str
    category_a: MetricCategory
    category_b: MetricCategory
    coefficient: float  # -1 to 1
    strength: str  # 'weak', 'moderate', 'strong'
    direction: str  # 'positive', 'negative'


@dataclass
class ThresholdCrossing:
    """A metric crossing a significant threshold."""
    metric_name: str
    category: MetricCategory
    event_id: str
    timestamp: float
    old_value: float
    new_value: float
    threshold: float
    direction: str  # 'above', 'below'


class MetricsEngine:
    """
    Quantification engine for the event stream.
    
    Extracts numeric metrics from events, tracks them over time,
    detects anomalies, correlations, and threshold crossings.
    
    Does NOT interpret or explain. Provides raw quantified data
    for human or AI observers to divine meaning from.
    
    Example:
        >>> engine = MetricsEngine(graph)
        >>> engine.ingest(event)
        >>> 
        >>> # Get metric statistics
        >>> loss = engine.get_metric("loss")
        >>> print(f"Loss: {loss.current} (delta: {loss.delta}, trend: {loss.trend()})")
        >>> 
        >>> # Get anomalies
        >>> for anomaly in engine.anomalies:
        ...     print(f"ANOMALY: {anomaly.metric_name} = {anomaly.value}")
        >>> 
        >>> # Get correlations
        >>> for corr in engine.get_correlations():
        ...     print(f"{corr.metric_a} ~ {corr.metric_b}: {corr.coefficient:.2f}")
    """
    
    def __init__(self, graph: Optional[CausationGraph] = None):
        self.graph = graph
        self._metrics: Dict[str, MetricSeries] = {}
        self._anomalies: List[Anomaly] = []
        self._threshold_crossings: List[ThresholdCrossing] = []
        self._event_count = 0
        
        # Configurable thresholds
        self.anomaly_std_threshold = 2.5
        self.correlation_min_samples = 10
        
        # Known significant thresholds for ML metrics
        self._known_thresholds = {
            "loss": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            "accuracy": [0.5, 0.8, 0.9, 0.95, 0.99],
            "lr": [1e-5, 1e-4, 1e-3, 1e-2, 0.1],
            "learning_rate": [1e-5, 1e-4, 1e-3, 1e-2, 0.1],
            "grad_norm": [0.1, 1.0, 10.0, 100.0],
            "gradient_norm": [0.1, 1.0, 10.0, 100.0],
        }
    
    def ingest(self, event: Event) -> Dict[str, MetricSeries]:
        """
        Ingest an event and extract/track all numeric metrics.
        
        Returns dict of updated metric series.
        """
        self._event_count += 1
        updated = {}
        
        for key, value in event.data.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                category = classify_metric(key)
                
                if math.isnan(value) or math.isinf(value):
                    # Track NaN/Inf as anomalies but don't add to series
                    self._anomalies.append(Anomaly(
                        metric_name=key,
                        category=category,
                        event_id=event.event_id,
                        timestamp=event.timestamp,
                        value=value,
                        expected_range=(0, 0),
                        deviation_std=float('inf'),
                        severity='critical',
                    ))
                    continue
                
                # Get or create metric series with proper category
                if key not in self._metrics:
                    self._metrics[key] = MetricSeries(name=key, category=category)
                
                series = self._metrics[key]
                old_value = series.current
                
                # Add new value
                series.values.append(float(value))
                series.timestamps.append(event.timestamp)
                series.event_ids.append(event.event_id)
                
                # Check for anomaly
                if series.is_anomaly(self.anomaly_std_threshold):
                    deviation = abs(value - series.mean) / series.std if series.std else 0
                    severity = 'critical' if deviation > 4 else 'major' if deviation > 3 else 'minor'
                    self._anomalies.append(Anomaly(
                        metric_name=key,
                        category=category,
                        event_id=event.event_id,
                        timestamp=event.timestamp,
                        value=value,
                        expected_range=(
                            series.mean - 2*series.std,
                            series.mean + 2*series.std
                        ),
                        deviation_std=deviation,
                        severity=severity,
                    ))
                
                # Check for threshold crossing
                if old_value is not None:
                    self._check_threshold_crossing(
                        key, event.event_id, event.timestamp, old_value, value
                    )
                
                updated[key] = series
        
        return updated
    
    def _check_threshold_crossing(
        self, 
        metric: str, 
        event_id: str, 
        timestamp: float,
        old_value: float, 
        new_value: float
    ):
        """Check if a metric crossed a known threshold."""
        thresholds = self._known_thresholds.get(metric, [])
        category = classify_metric(metric)
        
        for threshold in thresholds:
            # Crossed upward
            if old_value < threshold <= new_value:
                self._threshold_crossings.append(ThresholdCrossing(
                    metric_name=metric,
                    category=category,
                    event_id=event_id,
                    timestamp=timestamp,
                    old_value=old_value,
                    new_value=new_value,
                    threshold=threshold,
                    direction='above',
                ))
            # Crossed downward
            elif old_value > threshold >= new_value:
                self._threshold_crossings.append(ThresholdCrossing(
                    metric_name=metric,
                    category=category,
                    event_id=event_id,
                    timestamp=timestamp,
                    old_value=old_value,
                    new_value=new_value,
                    threshold=threshold,
                    direction='below',
                ))
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series by name."""
        return self._metrics.get(name)
    
    @property
    def metrics(self) -> Dict[str, MetricSeries]:
        """All tracked metrics."""
        return self._metrics
    
    @property
    def metric_names(self) -> List[str]:
        """Names of all tracked metrics."""
        return list(self._metrics.keys())
    
    @property
    def anomalies(self) -> List[Anomaly]:
        """All detected anomalies."""
        return self._anomalies
    
    @property
    def recent_anomalies(self) -> List[Anomaly]:
        """Anomalies from last 10 events."""
        if not self._anomalies:
            return []
        recent_ids = set()
        for series in self._metrics.values():
            recent_ids.update(series.event_ids[-10:])
        return [a for a in self._anomalies if a.event_id in recent_ids]
    
    @property
    def threshold_crossings(self) -> List[ThresholdCrossing]:
        """All threshold crossings."""
        return self._threshold_crossings
    
    def get_correlations(self, min_coefficient: float = 0.5) -> List[Correlation]:
        """
        Compute correlations between all metric pairs.
        
        Returns correlations with |coefficient| >= min_coefficient.
        """
        correlations = []
        metric_names = list(self._metrics.keys())
        
        for i, name_a in enumerate(metric_names):
            series_a = self._metrics[name_a]
            for name_b in metric_names[i+1:]:
                series_b = self._metrics[name_b]
                coef = self._pearson_correlation(name_a, name_b)
                if coef is not None and abs(coef) >= min_coefficient:
                    strength = 'strong' if abs(coef) > 0.8 else 'moderate' if abs(coef) > 0.5 else 'weak'
                    direction = 'positive' if coef > 0 else 'negative'
                    correlations.append(Correlation(
                        metric_a=name_a,
                        metric_b=name_b,
                        category_a=series_a.category,
                        category_b=series_b.category,
                        coefficient=coef,
                        strength=strength,
                        direction=direction,
                    ))
        
        return sorted(correlations, key=lambda c: abs(c.coefficient), reverse=True)
    
    def _pearson_correlation(self, name_a: str, name_b: str) -> Optional[float]:
        """Compute Pearson correlation between two metrics."""
        series_a = self._metrics.get(name_a)
        series_b = self._metrics.get(name_b)
        
        if not series_a or not series_b:
            return None
        
        # Need enough samples
        if series_a.count < self.correlation_min_samples or series_b.count < self.correlation_min_samples:
            return None
        
        # Align by taking min length
        n = min(series_a.count, series_b.count)
        a = series_a.values[-n:]
        b = series_b.values[-n:]
        
        # Compute correlation
        mean_a = sum(a) / n
        mean_b = sum(b) / n
        
        numerator = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
        
        var_a = sum((x - mean_a) ** 2 for x in a)
        var_b = sum((x - mean_b) ** 2 for x in b)
        
        denominator = math.sqrt(var_a * var_b)
        
        if denominator == 0:
            return None
        
        return numerator / denominator
    
    def summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics and detections."""
        return {
            "event_count": self._event_count,
            "metric_count": len(self._metrics),
            "metrics": {name: series.to_dict() for name, series in self._metrics.items()},
            "metrics_by_category": self.metrics_by_category_summary(),
            "anomaly_count": len(self._anomalies),
            "recent_anomalies": [
                {"metric": a.metric_name, "category": a.category.name, "value": a.value, "severity": a.severity}
                for a in self.recent_anomalies
            ],
            "threshold_crossings": len(self._threshold_crossings),
            "correlations": [
                {"a": c.metric_a, "b": c.metric_b, "r": c.coefficient, 
                 "cat_a": c.category_a.name, "cat_b": c.category_b.name}
                for c in self.get_correlations()[:5]  # Top 5
            ],
            "health_status": self.health_summary(),
        }
    
    # =========================================================================
    # CATEGORY-AWARE QUERIES
    # =========================================================================
    
    def get_metrics_by_category(self, category: MetricCategory) -> Dict[str, MetricSeries]:
        """Get all metrics in a specific category."""
        return {
            name: series for name, series in self._metrics.items()
            if series.category == category
        }
    
    def metrics_by_category_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get metric count and names grouped by category."""
        by_cat: Dict[str, Dict[str, Any]] = {}
        for name, series in self._metrics.items():
            cat_name = series.category.name
            if cat_name not in by_cat:
                by_cat[cat_name] = {"count": 0, "metrics": [], "health": []}
            by_cat[cat_name]["count"] += 1
            by_cat[cat_name]["metrics"].append(name)
            by_cat[cat_name]["health"].append(series.health_status())
        return by_cat
    
    def get_training_metrics(self) -> Dict[str, MetricSeries]:
        """Convenience: get all TRAINING_DYNAMICS metrics."""
        return self.get_metrics_by_category(MetricCategory.TRAINING_DYNAMICS)
    
    def get_gradient_metrics(self) -> Dict[str, MetricSeries]:
        """Convenience: get all GRADIENT_HEALTH metrics."""
        return self.get_metrics_by_category(MetricCategory.GRADIENT_HEALTH)
    
    def get_memory_metrics(self) -> Dict[str, MetricSeries]:
        """Convenience: get all MEMORY_COMPUTE metrics."""
        return self.get_metrics_by_category(MetricCategory.MEMORY_COMPUTE)
    
    def get_convergence_metrics(self) -> Dict[str, MetricSeries]:
        """Convenience: get all CONVERGENCE_SIGNALS metrics."""
        return self.get_metrics_by_category(MetricCategory.CONVERGENCE_SIGNALS)
    
    def health_summary(self) -> Dict[str, Any]:
        """Get overall health status of all metrics."""
        statuses = {"healthy": 0, "warning": 0, "critical": 0, "unknown": 0}
        issues = []
        
        for name, series in self._metrics.items():
            status = series.health_status()
            statuses[status] += 1
            if status in ("warning", "critical"):
                issues.append({
                    "metric": name,
                    "category": series.category.name,
                    "status": status,
                    "value": series.current,
                    "trend": series.trend(),
                })
        
        overall = "critical" if statuses["critical"] > 0 else \
                  "warning" if statuses["warning"] > 0 else "healthy"
        
        return {
            "overall": overall,
            "counts": statuses,
            "issues": issues,
        }
    
    def get_cross_category_correlations(self) -> List[Correlation]:
        """Get correlations between metrics in different categories."""
        all_corr = self.get_correlations(min_coefficient=0.3)
        return [c for c in all_corr if c.category_a != c.category_b]
    
    def get_category_coverage(self) -> Dict[str, bool]:
        """Check which metric categories are being tracked."""
        tracked = {series.category for series in self._metrics.values()}
        return {cat.name: cat in tracked for cat in MetricCategory}
    
    # =========================================================================
    # TRIAGE SYSTEM - Common Sense Diagnostics (Occam's Razor)
    # =========================================================================
    # 
    # Five questions that matter:
    # 1. Is training working? (loss trend)
    # 2. Is it about to explode? (gradient health)
    # 3. Am I wasting compute? (efficiency)
    # 4. Am I overfitting? (generalization gap)
    # 5. What broke and why? (anomaly + correlation)
    #
    
    def triage(self) -> Dict[str, Any]:
        """
        Quick diagnostic: Is training healthy? What's wrong?
        
        Returns a simple, actionable assessment.
        Occam's Razor: simplest useful answer.
        """
        diagnosis = {
            "status": "LISTENING",  # Not UNKNOWN - we're actively waiting
            "confidence": 0.0,
            "checks": {},
            "action": "Collecting initial metrics...",
            "details": [],
        }
        
        checks_passed = 0
        checks_total = 0
        
        # CHECK 1: Is loss going down?
        loss_check = self._check_loss_progress()
        diagnosis["checks"]["loss_progress"] = loss_check
        checks_total += 1
        if loss_check["ok"]:
            checks_passed += 1
        
        # CHECK 2: Are gradients healthy?
        grad_check = self._check_gradient_health()
        diagnosis["checks"]["gradient_health"] = grad_check
        checks_total += 1
        if grad_check["ok"]:
            checks_passed += 1
        
        # CHECK 3: Am I using compute efficiently?
        efficiency_check = self._check_efficiency()
        diagnosis["checks"]["efficiency"] = efficiency_check
        checks_total += 1
        if efficiency_check["ok"]:
            checks_passed += 1
        
        # CHECK 4: Am I overfitting?
        overfit_check = self._check_overfitting()
        diagnosis["checks"]["overfitting"] = overfit_check
        checks_total += 1
        if overfit_check["ok"]:
            checks_passed += 1
        
        # CHECK 5: Any anomalies pointing to root cause?
        anomaly_check = self._check_anomalies()
        diagnosis["checks"]["anomalies"] = anomaly_check
        checks_total += 1
        if anomaly_check["ok"]:
            checks_passed += 1
        
        # Overall status
        diagnosis["confidence"] = checks_passed / checks_total if checks_total > 0 else 0
        
        if checks_passed == checks_total:
            diagnosis["status"] = "HEALTHY"
            diagnosis["action"] = "Training looks good. Continue monitoring."
        elif checks_passed >= checks_total * 0.6:
            diagnosis["status"] = "WARNING"
            # Find what's wrong
            issues = [k for k, v in diagnosis["checks"].items() if not v["ok"]]
            diagnosis["action"] = f"Review: {', '.join(issues)}"
        else:
            diagnosis["status"] = "CRITICAL"
            diagnosis["action"] = "Stop and investigate. Multiple issues detected."
        
        # Collect all details
        for check_name, check_result in diagnosis["checks"].items():
            if check_result.get("detail"):
                diagnosis["details"].append(f"{check_name}: {check_result['detail']}")
        
        return diagnosis
    
    def _check_loss_progress(self) -> Dict[str, Any]:
        """Is loss decreasing as expected?"""
        # Find loss metric (try common names)
        loss_series = None
        for name in ["loss", "train_loss", "nll_loss", "ce_loss"]:
            if name in self._metrics:
                loss_series = self._metrics[name]
                break
        
        if loss_series is None or loss_series.count < 3:
            return {"ok": True, "detail": "Waiting for loss metrics (need 3+)", "status": "waiting"}
        
        trend = loss_series.trend()
        roc = loss_series.rate_of_change()
        
        if trend == "falling":
            return {"ok": True, "detail": f"Loss falling (Δ={roc:.4f}/step)", "status": "good"}
        elif trend == "stable" and loss_series.current < 1.0:
            return {"ok": True, "detail": f"Loss stable at {loss_series.current:.4f}", "status": "converged"}
        elif trend == "rising":
            return {"ok": False, "detail": f"Loss RISING! Current: {loss_series.current:.4f}", "status": "diverging"}
        elif trend == "volatile":
            return {"ok": False, "detail": f"Loss unstable (std={loss_series.std:.4f})", "status": "unstable"}
        else:
            return {"ok": True, "detail": f"Loss: {loss_series.current:.4f} (trend unclear)", "status": "stable"}
    
    def _check_gradient_health(self) -> Dict[str, Any]:
        """Are gradients in a healthy range?"""
        grad_series = None
        for name in ["grad_norm", "gradient_norm", "global_grad_norm"]:
            if name in self._metrics:
                grad_series = self._metrics[name]
                break
        
        if grad_series is None or grad_series.count < 2:
            return {"ok": True, "detail": "Waiting for grad_norm metrics", "status": "waiting"}
        
        current = grad_series.current
        
        # Vanishing gradients
        if current < 1e-7:
            return {"ok": False, "detail": f"VANISHING gradients: {current:.2e}", "status": "vanishing"}
        
        # Exploding gradients
        if current > 100:
            return {"ok": False, "detail": f"EXPLODING gradients: {current:.2f}", "status": "exploding"}
        
        # Healthy range
        if 1e-5 < current < 10:
            return {"ok": True, "detail": f"Gradients healthy: {current:.4f}", "status": "healthy"}
        
        # Warning zone
        return {"ok": True, "detail": f"Gradients marginal: {current:.4f}", "status": "marginal"}
    
    def _check_efficiency(self) -> Dict[str, Any]:
        """Am I using compute efficiently?"""
        # Check MFU (Model FLOP Utilization)
        mfu_series = self._metrics.get("mfu")
        if mfu_series and mfu_series.count > 0:
            mfu = mfu_series.current
            if mfu < 0.1:
                return {"ok": False, "detail": f"Low GPU utilization: {mfu*100:.1f}%", "status": "inefficient"}
            elif mfu < 0.3:
                return {"ok": True, "detail": f"Moderate efficiency: {mfu*100:.1f}%", "status": "moderate"}
            else:
                return {"ok": True, "detail": f"Good efficiency: {mfu*100:.1f}%", "status": "efficient"}
        
        # Fallback: check timing
        time_series = self._metrics.get("dt") or self._metrics.get("time") or self._metrics.get("batch_time")
        if time_series and time_series.count > 2:
            trend = time_series.trend()
            if trend == "rising":
                return {"ok": False, "detail": "Step time increasing (slowdown)", "status": "degrading"}
            return {"ok": True, "detail": f"Step time: {time_series.current:.3f}s", "status": "stable"}
        
        return {"ok": True, "detail": "Need mfu or dt/time metrics", "status": "waiting"}
    
    def _check_overfitting(self) -> Dict[str, Any]:
        """Is model overfitting?"""
        train_loss = None
        val_loss = None
        
        # Find train and val loss
        for name in ["loss", "train_loss"]:
            if name in self._metrics:
                train_loss = self._metrics[name]
                break
        
        for name in ["val_loss", "eval_loss", "test_loss"]:
            if name in self._metrics:
                val_loss = self._metrics[name]
                break
        
        if train_loss is None or val_loss is None:
            return {"ok": True, "detail": "Need train_loss + val_loss to check", "status": "waiting"}
        
        if train_loss.count < 3 or val_loss.count < 3:
            return {"ok": True, "detail": f"Collecting ({train_loss.count}/3 train, {val_loss.count}/3 val)", "status": "waiting"}
        
        gap = val_loss.current - train_loss.current
        gap_pct = gap / train_loss.current if train_loss.current > 0 else 0
        
        # Check if gap is widening
        train_trend = train_loss.trend()
        val_trend = val_loss.trend()
        
        if train_trend == "falling" and val_trend == "rising":
            return {"ok": False, "detail": f"OVERFITTING: train↓ val↑ (gap={gap:.4f})", "status": "overfitting"}
        
        if gap_pct > 0.5:  # Val loss 50% higher than train
            return {"ok": False, "detail": f"Large generalization gap: {gap_pct*100:.1f}%", "status": "high_gap"}
        
        if gap_pct > 0.2:
            return {"ok": True, "detail": f"Moderate gap: {gap_pct*100:.1f}%", "status": "moderate_gap"}
        
        return {"ok": True, "detail": f"Good generalization (gap={gap:.4f})", "status": "healthy"}
    
    def _check_anomalies(self) -> Dict[str, Any]:
        """Any recent anomalies that need attention?"""
        recent = self.recent_anomalies
        
        if not recent:
            return {"ok": True, "detail": "No anomalies", "status": "clean"}
        
        critical = [a for a in recent if a.severity == "critical"]
        major = [a for a in recent if a.severity == "major"]
        
        if critical:
            names = list(set(a.metric_name for a in critical))
            return {"ok": False, "detail": f"CRITICAL anomalies in: {', '.join(names)}", "status": "critical"}
        
        if major:
            names = list(set(a.metric_name for a in major))
            return {"ok": False, "detail": f"Major anomalies in: {', '.join(names)}", "status": "major"}
        
        return {"ok": True, "detail": f"{len(recent)} minor anomalies", "status": "minor"}
    
    def quick_status(self) -> str:
        """One-line status for dashboards."""
        t = self.triage()
        return f"[{t['status']}] {t['action']} (confidence: {t['confidence']*100:.0f}%)"
    
    def __repr__(self) -> str:
        return f"<MetricsEngine | {len(self._metrics)} metrics, {len(self._anomalies)} anomalies>"
