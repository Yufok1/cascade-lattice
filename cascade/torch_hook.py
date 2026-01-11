"""
Cascade PyTorch Hook - Deep Neural Network Instrumentation.

This is the missing piece: direct integration with PyTorch training loops
to capture what stdout never shows:
- Per-layer gradient norms
- Weight statistics  
- Activation patterns
- Attention maps
- Memory allocation

Usage:
    from cascade.torch_hook import CascadeHook
    
    model = YourModel()
    hook = CascadeHook(model, monitor)
    
    # Training loop
    for batch in dataloader:
        loss = model(batch)
        loss.backward()  # Hook automatically captures gradients
        optimizer.step()
        
        # Hook auto-logs per-layer stats to monitor
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import weakref

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


@dataclass
class LayerStats:
    """Statistics for a single layer."""
    name: str
    param_count: int
    grad_norm: Optional[float] = None
    grad_mean: Optional[float] = None
    grad_std: Optional[float] = None
    weight_norm: Optional[float] = None
    weight_mean: Optional[float] = None
    weight_std: Optional[float] = None
    activation_norm: Optional[float] = None
    activation_mean: Optional[float] = None


class CascadeHook:
    """
    PyTorch hook for deep instrumentation.
    
    Captures per-layer metrics that stdout logging misses:
    - Gradient flow through each layer
    - Weight evolution
    - Activation statistics
    - Memory usage
    
    Example:
        >>> from cascade import Monitor
        >>> from cascade.torch_hook import CascadeHook
        >>> 
        >>> monitor = Monitor()
        >>> model = nn.Sequential(...)
        >>> hook = CascadeHook(model, monitor)
        >>> 
        >>> # Training happens...
        >>> # Hook automatically captures:
        >>> #   - grad_norm/layer_0, grad_norm/layer_1, ...
        >>> #   - weight_norm/layer_0, ...
        >>> #   - activation_mean/layer_0, ...
    """
    
    def __init__(
        self,
        model: "nn.Module",
        monitor: Optional[Any] = None,
        track_gradients: bool = True,
        track_weights: bool = True,
        track_activations: bool = False,  # Can be expensive
        layer_filter: Optional[Callable[[str, "nn.Module"], bool]] = None,
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required for CascadeHook. pip install torch")
        
        self.model = model
        self.monitor = monitor
        self.track_gradients = track_gradients
        self.track_weights = track_weights
        self.track_activations = track_activations
        self.layer_filter = layer_filter or self._default_filter
        
        self._handles: List[Any] = []
        self._layer_stats: Dict[str, LayerStats] = {}
        self._step = 0
        
        # Register hooks
        self._register_hooks()
    
    def _default_filter(self, name: str, module: "nn.Module") -> bool:
        """Default: track Linear, Conv, and Attention layers."""
        return isinstance(module, (
            nn.Linear, 
            nn.Conv1d, nn.Conv2d, nn.Conv3d,
            nn.MultiheadAttention,
            nn.LayerNorm, nn.BatchNorm1d, nn.BatchNorm2d,
            nn.Embedding,
        ))
    
    def _register_hooks(self):
        """Register forward and backward hooks on tracked layers."""
        for name, module in self.model.named_modules():
            if self.layer_filter(name, module):
                # Count params
                param_count = sum(p.numel() for p in module.parameters())
                self._layer_stats[name] = LayerStats(name=name, param_count=param_count)
                
                # Gradient hook
                if self.track_gradients:
                    handle = module.register_full_backward_hook(
                        self._make_grad_hook(name)
                    )
                    self._handles.append(handle)
                
                # Activation hook
                if self.track_activations:
                    handle = module.register_forward_hook(
                        self._make_activation_hook(name)
                    )
                    self._handles.append(handle)
    
    def _make_grad_hook(self, layer_name: str):
        """Create gradient hook for a specific layer."""
        def hook(module, grad_input, grad_output):
            stats = self._layer_stats[layer_name]
            
            # Get gradient from output
            if grad_output and grad_output[0] is not None:
                grad = grad_output[0]
                if grad.numel() > 0:
                    stats.grad_norm = grad.norm().item()
                    stats.grad_mean = grad.mean().item()
                    stats.grad_std = grad.std().item()
        
        return hook
    
    def _make_activation_hook(self, layer_name: str):
        """Create activation hook for a specific layer."""
        def hook(module, input, output):
            stats = self._layer_stats[layer_name]
            
            if isinstance(output, torch.Tensor):
                stats.activation_norm = output.norm().item()
                stats.activation_mean = output.mean().item()
        
        return hook
    
    def capture_weights(self):
        """Capture current weight statistics."""
        for name, module in self.model.named_modules():
            if name in self._layer_stats:
                stats = self._layer_stats[name]
                
                # Get weight tensor
                if hasattr(module, 'weight') and module.weight is not None:
                    w = module.weight.data
                    stats.weight_norm = w.norm().item()
                    stats.weight_mean = w.mean().item()
                    stats.weight_std = w.std().item()
    
    def step(self, extra_data: Optional[Dict[str, Any]] = None):
        """
        Call after each training step to log metrics.
        
        Args:
            extra_data: Additional data to include (loss, lr, etc.)
        """
        self._step += 1
        
        if self.track_weights:
            self.capture_weights()
        
        # Build event data
        data = {"step": self._step}
        
        if extra_data:
            data.update(extra_data)
        
        # Add per-layer stats
        for layer_name, stats in self._layer_stats.items():
            prefix = layer_name.replace(".", "_")
            
            if stats.grad_norm is not None:
                data[f"grad_norm/{prefix}"] = stats.grad_norm
            if stats.grad_mean is not None:
                data[f"grad_mean/{prefix}"] = stats.grad_mean
            if stats.weight_norm is not None:
                data[f"weight_norm/{prefix}"] = stats.weight_norm
            if stats.activation_mean is not None:
                data[f"activation_mean/{prefix}"] = stats.activation_mean
        
        # Aggregate metrics
        grad_norms = [s.grad_norm for s in self._layer_stats.values() if s.grad_norm is not None]
        if grad_norms:
            data["grad_norm_min"] = min(grad_norms)
            data["grad_norm_max"] = max(grad_norms)
            data["grad_norm_mean"] = sum(grad_norms) / len(grad_norms)
        
        weight_norms = [s.weight_norm for s in self._layer_stats.values() if s.weight_norm is not None]
        if weight_norms:
            data["weight_norm_total"] = sum(weight_norms)
        
        # Log to monitor
        if self.monitor:
            self.monitor.observe(data, event_type="training_step", component="torch_hook")
        
        return data
    
    def get_layer_report(self) -> Dict[str, Dict[str, Any]]:
        """Get current stats for all tracked layers."""
        return {
            name: {
                "param_count": stats.param_count,
                "grad_norm": stats.grad_norm,
                "weight_norm": stats.weight_norm,
                "activation_mean": stats.activation_mean,
            }
            for name, stats in self._layer_stats.items()
        }
    
    def detect_issues(self) -> List[str]:
        """Quick check for common issues."""
        issues = []
        
        for name, stats in self._layer_stats.items():
            # Vanishing gradients
            if stats.grad_norm is not None and stats.grad_norm < 1e-7:
                issues.append(f"Vanishing gradient in {name}: {stats.grad_norm:.2e}")
            
            # Exploding gradients
            if stats.grad_norm is not None and stats.grad_norm > 100:
                issues.append(f"Exploding gradient in {name}: {stats.grad_norm:.2f}")
            
            # Dead layer (no gradient flow)
            if stats.grad_norm == 0:
                issues.append(f"Dead layer (zero gradient): {name}")
            
            # Weight explosion
            if stats.weight_norm is not None and stats.weight_norm > 1000:
                issues.append(f"Large weights in {name}: {stats.weight_norm:.2f}")
        
        return issues
    
    def remove(self):
        """Remove all hooks."""
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
    
    def __del__(self):
        self.remove()
    
    @property
    def tracked_layers(self) -> List[str]:
        """List of tracked layer names."""
        return list(self._layer_stats.keys())
    
    @property  
    def total_params(self) -> int:
        """Total parameters in tracked layers."""
        return sum(s.param_count for s in self._layer_stats.values())
    
    # =========================================================================
    # BRANCHING: From observation to understanding to action
    # =========================================================================
    
    def trace_anomaly(self, metric_name: str = "loss") -> Dict[str, Any]:
        """
        BACKWARD BRANCH: When something goes wrong, which layer caused it?
        
        Correlates metric anomaly with per-layer gradient behavior.
        Returns the likely culprit layer(s).
        """
        if not self.monitor or not self.monitor.metrics:
            return {"culprit": None, "reason": "No monitor data"}
        
        # Get anomalies from the metric
        anomalies = self.monitor.metrics.recent_anomalies
        if not anomalies:
            return {"culprit": None, "reason": "No anomalies detected"}
        
        # Find layers with extreme gradients at the time of anomaly
        suspects = []
        for name, stats in self._layer_stats.items():
            if stats.grad_norm is not None:
                if stats.grad_norm < 1e-7:
                    suspects.append({"layer": name, "issue": "vanishing", "grad_norm": stats.grad_norm})
                elif stats.grad_norm > 50:
                    suspects.append({"layer": name, "issue": "exploding", "grad_norm": stats.grad_norm})
        
        if suspects:
            # Sort by severity
            suspects.sort(key=lambda x: abs(x["grad_norm"]) if x["issue"] == "exploding" else -x["grad_norm"], reverse=True)
            return {
                "culprit": suspects[0]["layer"],
                "issue": suspects[0]["issue"],
                "all_suspects": suspects,
                "recommendation": self._recommend_fix(suspects[0])
            }
        
        return {"culprit": None, "reason": "No layer anomalies found"}
    
    def _recommend_fix(self, suspect: Dict[str, Any]) -> str:
        """Generate actionable recommendation."""
        if suspect["issue"] == "exploding":
            return f"Gradient explosion in {suspect['layer']}. Try: lower LR, add gradient clipping, check for NaN inputs."
        elif suspect["issue"] == "vanishing":
            return f"Vanishing gradient in {suspect['layer']}. Try: residual connections, different activation, layer norm."
        return "Unknown issue"
    
    def predict_failure(self, lookahead: int = 5) -> Dict[str, Any]:
        """
        FORWARD BRANCH: Predict if training is about to fail.
        
        Uses gradient trends to predict explosion/vanishing before it happens.
        """
        if not self.monitor or not self.monitor.metrics:
            return {"risk": "unknown", "reason": "No history"}
        
        warnings = []
        
        for name, stats in self._layer_stats.items():
            # Check gradient history via monitor
            grad_key = f"grad_norm/{name.replace('.', '_')}"
            series = self.monitor.metrics.get_metric(grad_key)
            
            if series and series.count >= 5:
                trend = series.trend()
                roc = series.rate_of_change()
                
                if trend == "rising" and roc and roc > 0:
                    # Project forward
                    projected = series.current + (roc * lookahead)
                    if projected > 100:
                        warnings.append({
                            "layer": name,
                            "prediction": "explosion",
                            "current": series.current,
                            "projected": projected,
                            "steps_until": int(100 / roc) if roc > 0 else None
                        })
                
                elif trend == "falling" and series.current < 0.001:
                    warnings.append({
                        "layer": name,
                        "prediction": "vanishing",
                        "current": series.current,
                        "trend": "falling"
                    })
        
        if warnings:
            return {
                "risk": "high",
                "warnings": warnings,
                "action": "Consider intervention now"
            }
        
        return {"risk": "low", "warnings": [], "action": "Continue monitoring"}
    
    def suggest_intervention(self) -> Optional[Dict[str, Any]]:
        """
        FORWARD BRANCH: Suggest specific parameter changes.
        
        Based on current state, recommend concrete actions.
        """
        prediction = self.predict_failure()
        
        if prediction["risk"] != "high":
            return None
        
        interventions = []
        
        for warning in prediction["warnings"]:
            if warning["prediction"] == "explosion":
                interventions.append({
                    "action": "reduce_lr",
                    "factor": 0.5,
                    "reason": f"Gradient explosion predicted in {warning['layer']}"
                })
                interventions.append({
                    "action": "add_grad_clip",
                    "value": 1.0,
                    "reason": "Prevent gradient explosion"
                })
            
            elif warning["prediction"] == "vanishing":
                interventions.append({
                    "action": "increase_lr",
                    "factor": 1.5,
                    "reason": f"Vanishing gradient in {warning['layer']}"
                })
        
        return {
            "interventions": interventions,
            "urgency": "high" if len(interventions) > 1 else "medium"
        }
    
    def get_attention_pattern(self, layer_name: str) -> Optional[Dict[str, Any]]:
        """
        DEEP BRANCH: Extract attention patterns (for transformer layers).
        
        Returns attention entropy, sparsity, positional bias.
        """
        for name, module in self.model.named_modules():
            if name == layer_name and isinstance(module, nn.MultiheadAttention):
                # Would need forward hook with attention weights
                # This is a stub showing the branch exists
                return {
                    "layer": layer_name,
                    "type": "attention",
                    "note": "Full implementation requires attention weight capture"
                }
        return None
    
    def find_dead_neurons(self, threshold: float = 0.01) -> List[Dict[str, Any]]:
        """
        DEEP BRANCH: Find neurons that never activate.
        
        Dead neurons = wasted parameters = pruning candidates.
        """
        dead = []
        
        for name, stats in self._layer_stats.items():
            if stats.activation_mean is not None:
                if abs(stats.activation_mean) < threshold:
                    dead.append({
                        "layer": name,
                        "activation_mean": stats.activation_mean,
                        "recommendation": "Consider pruning or reinitializing"
                    })
        
        return dead
    
    def branch_report(self) -> Dict[str, Any]:
        """
        Full branch analysis: backward, forward, and deep.
        """
        return {
            "backward": {
                "anomaly_trace": self.trace_anomaly(),
            },
            "forward": {
                "failure_prediction": self.predict_failure(),
                "suggested_interventions": self.suggest_intervention(),
            },
            "deep": {
                "dead_neurons": self.find_dead_neurons(),
                "layer_health": self.detect_issues(),
            },
            "meta": {
                "tracked_layers": len(self._layer_stats),
                "total_params": self.total_params,
                "step": self._step,
            }
        }


# Convenience function
def instrument(model: "nn.Module", monitor=None, **kwargs) -> CascadeHook:
    """
    Quick instrumentation of a PyTorch model.
    
    Usage:
        hook = cascade.torch_hook.instrument(model, monitor)
    """
    return CascadeHook(model, monitor, **kwargs)
