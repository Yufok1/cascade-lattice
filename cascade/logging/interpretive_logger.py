"""
CASCADE Interpretive Logger
Human-readable causation flow logging for operators and stakeholders.

Translates mathematical events into stories humans can understand and act upon.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class ImpactLevel(Enum):
    """Business impact levels"""
    CRITICAL = "🔴 CRITICAL"  # Service down, data loss
    HIGH = "🟠 HIGH"         # Degraded performance, user impact
    MEDIUM = "🟡 MEDIUM"     # Issues detected, monitoring needed
    LOW = "🟢 LOW"          # Informational, routine operations
    TRACE = "🔵 TRACE"      # Detailed flow, debugging


@dataclass
class InterpretiveEntry:
    """A human-readable system event"""
    timestamp: float = field(default_factory=time.time)
    impact: ImpactLevel = ImpactLevel.LOW
    system: str = ""  # High-level system name
    component: str = ""  # Specific component
    event: str = ""  # What happened
    context: str = ""  # Why it matters
    consequence: str = ""  # What happens next
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[str] = None
    
    def format_display(self) -> str:
        """Format for beautiful terminal output with colors"""
        time_str = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        
        # ANSI color codes
        colors = {
            "CRITICAL": ("\033[91m", "🔴"),  # Bright red
            "HIGH": ("\033[31m", "🟠"),       # Red
            "MEDIUM": ("\033[33m", "🟡"),     # Yellow
            "LOW": ("\033[32m", "🟢"),        # Green
            "TRACE": ("\033[90m", "🔵"),      # Gray
            "RESET": "\033[0m",
            "BOLD": "\033[1m",
            "DIM": "\033[2m",
            "CYAN": "\033[36m",
            "MAGENTA": "\033[35m",
        }
        
        color, icon = colors.get(self.impact.value, ("\033[0m", "⚪"))
        reset = colors["RESET"]
        bold = colors["BOLD"]
        dim = colors["DIM"]
        cyan = colors["CYAN"]
        magenta = colors["MAGENTA"]
        
        lines = [
            f"\n{color}{bold}{icon} {self.impact.value} [{time_str}] {self.system}{reset}",
            f"├─ {cyan}Component:{reset} {self.component}",
            f"├─ {magenta}Event:{reset} {self.event}",
            f"├─ {dim}Context:{reset} {self.context}",
            f"├─ {dim}Consequence:{reset} {self.consequence}",
        ]
        
        if self.metrics:
            lines.append(f"├─ {cyan}Metrics:{reset} {self._format_metrics()}")
        
        if self.recommendation:
            lines.append(f"└─ {bold}Recommendation:{reset} {self.recommendation}")
        else:
            lines.append(f"└─ {dim}Status: Monitoring{reset}")
            
        return "\n".join(lines)
    
    def _format_metrics(self) -> str:
        """Format metrics nicely"""
        return ", ".join([f"{k}={v}" for k, v in self.metrics.items()])


class InterpretiveLogger:
    """Human-readable system storytelling"""
    
    def __init__(self, system_name: str):
        self.system = system_name
        self.entries: List[InterpretiveEntry] = []
        self.start_time = time.time()
        
    def log(self, impact: ImpactLevel, component: str, event: str,
            context: str, consequence: str, 
            metrics: Optional[Dict] = None,
            recommendation: Optional[str] = None):
        """Record a system event"""
        
        entry = InterpretiveEntry(
            impact=impact,
            system=self.system,
            component=component,
            event=event,
            context=context,
            consequence=consequence,
            metrics=metrics or {},
            recommendation=recommendation
        )
        
        self.entries.append(entry)
        self._emit_to_container(entry)
    
    def _emit_to_container(self, entry: InterpretiveEntry):
        """Emit beautiful formatted log to container"""
        print(entry.format_display())
    
    # Convenience methods for common events
    def service_start(self, component: str, port: int = None):
        """Service started successfully"""
        self.log(
            ImpactLevel.LOW,
            component,
            "Service started",
            f"Component initialized and ready for requests",
            f"Accepting connections on port {port}" if port else "Ready for operations",
            metrics={"port": port} if port else {},
            recommendation="Monitor for healthy connections"
        )
    
    def service_error(self, component: str, error: str, impact: ImpactLevel = ImpactLevel.HIGH):
        """Service encountered error"""
        self.log(
            impact,
            component,
            "Service error",
            f"Component failed to process request",
            f"May affect system reliability",
            metrics={"error": error},
            recommendation="Check component logs and restart if needed"
        )
    
    def data_processing(self, dataset: str, records: int, operations: List[str]):
        """Data processing pipeline"""
        self.log(
            ImpactLevel.MEDIUM,
            "DataProcessor",
            f"Processing {dataset}",
            f"Executing pipeline operations on dataset",
            f"Will process {records:,} records through {len(operations)} stages",
            metrics={
                "dataset": dataset,
                "records": records,
                "operations": len(operations)
            },
            recommendation="Monitor processing progress and error rates"
        )
    
    def model_loaded(self, model_id: str, size_gb: float, device: str):
        """AI model loaded into memory"""
        self.log(
            ImpactLevel.MEDIUM,
            "ModelLoader",
            f"Model {model_id} loaded",
            f"Neural network loaded and ready for inference",
            f"Consuming {size_gb:.1f}GB VRAM on {device}",
            metrics={
                "model": model_id,
                "size_gb": size_gb,
                "device": device
            },
            recommendation="Monitor GPU memory usage during inference"
        )
    
    def security_event(self, component: str, event: str, details: str):
        """Security-related event"""
        self.log(
            ImpactLevel.CRITICAL,
            component,
            f"Security: {event}",
            f"Security system detected potential threat",
            f"Immediate investigation required",
            metrics={"details": details},
            recommendation="Review security logs and consider blocking source"
        )
    
    def performance_warning(self, component: str, metric: str, value: float, threshold: float):
        """Performance threshold exceeded"""
        self.log(
            ImpactLevel.HIGH,
            component,
            f"Performance warning: {metric}",
            f"Component performance degraded",
            f"May impact user experience if continues",
            metrics={metric: value, "threshold": threshold},
            recommendation=f"Optimize {metric} or scale resources"
        )
    
    def cascade_observation(self, model: str, layers: int, merkle_root: str):
        """CASCADE observed model execution"""
        self.log(
            ImpactLevel.INFO,
            "CASCADE",
            f"Model observation complete",
            f"Cryptographic proof generated for model execution",
            f"Merkle root provides verifiable audit trail",
            metrics={
                "model": model,
                "layers": layers,
                "merkle": merkle_root[:16] + "..."
            },
            recommendation="Store attestation for permanent records"
        )
    
    def fixed_point_convergence(self, operation: str, iterations: int, entities: int):
        """Mathematical fixed point reached"""
        self.log(
            ImpactLevel.INFO,
            "KleeneEngine",
            f"Fixed point convergence",
            f"{operation} completed after {iterations} iterations",
            f"Resolved relationships for {entities} entities",
            metrics={
                "operation": operation,
                "iterations": iterations,
                "entities": entities
            },
            recommendation="Review convergence quality metrics"
        )


# Global interpretive loggers
_interpretive_loggers: Dict[str, InterpretiveLogger] = {}


def get_interpretive_logger(system: str) -> InterpretiveLogger:
    """Get or create interpretive logger for system"""
    if system not in _interpretive_loggers:
        _interpretive_loggers[system] = InterpretiveLogger(system)
    return _interpretive_loggers[system]


# Bridge function to translate Kleene logs to interpretive
def translate_kleene_to_interpretive(kleene_entry, interpretive_logger):
    """Translate mathematical log to human story"""
    
    # Map Kleene levels to impact levels
    impact_map = {
        "CRITICAL": ImpactLevel.CRITICAL,
        "ERROR": ImpactLevel.HIGH,
        "WARNING": ImpactLevel.MEDIUM,
        "INFO": ImpactLevel.LOW,
        "DEBUG": ImpactLevel.TRACE,
        "TRACE": ImpactLevel.TRACE
    }
    
    # Create human-readable context
    if kleene_entry.fixed_point_reached:
        event = f"Mathematical convergence achieved"
        context = f"Operation {kleene_entry.operation} reached stable state"
        consequence = "System can proceed with verified result"
    else:
        event = f"State transition in {kleene_entry.operation}"
        context = f"Component processing through iterations"
        consequence = "Continuing toward fixed point"
    
    interpretive_logger.log(
        impact_map.get(kleene_entry.level.value, ImpactLevel.LOW),
        kleene_entry.component,
        event,
        context,
        consequence,
        metrics={
            "iterations": kleene_entry.iteration_count,
            "hash": kleene_entry.hash_value
        }
    )
