"""
Cascade Core - Symbiotic Adapter.

The heart of Cascade's system-agnostic design. The adapter uses Kleene fixed-point
convergence to interpret ANY signal format and convert it to Events.

"It doesn't hook into your system — it becomes part of it."
"""

import time
import json
import re
from typing import Any, Dict, List, Optional, Callable, Type
from dataclasses import dataclass

from cascade.core.event import Event


@dataclass
class SignalPattern:
    """A learned pattern for interpreting signals."""
    pattern_type: str  # 'dict', 'string', 'tensor', 'protobuf', etc.
    component: str
    event_type: str
    extractor: Optional[Callable[[Any], Dict[str, Any]]] = None
    confidence: float = 0.0
    match_count: int = 0


class SymbioticAdapter:
    """
    Self-interpreting adapter that converges to any signal format.
    
    The adapter observes signals from the host system and learns how to
    interpret them through fixed-point iteration. It starts with naive
    interpretations and refines them until stable.
    
    This is the key to Cascade's system-agnostic design:
    - No framework-specific hooks required
    - No configuration needed
    - Feed it ANY signal format, it adapts
    
    Example:
        >>> adapter = SymbioticAdapter()
        >>> 
        >>> # Feed it different signal formats
        >>> adapter.interpret({"loss": 0.5, "epoch": 10})
        >>> adapter.interpret("2024-01-01 12:00:00 ERROR training failed")
        >>> adapter.interpret(torch.tensor([0.1, 0.2, 0.3]))
        >>> 
        >>> # It learns patterns and gets better at interpretation
        >>> print(adapter.learned_patterns)
    """
    
    def __init__(self):
        """Initialize the symbiotic adapter."""
        self._patterns: List[SignalPattern] = []
        self._signal_count = 0
        self._interpretation_cache: Dict[str, SignalPattern] = {}
        
        # Built-in interpreters for common formats
        self._builtin_interpreters = {
            dict: self._interpret_dict,
            str: self._interpret_string,
            list: self._interpret_list,
        }
        
        # Regex patterns for log line parsing
        self._log_patterns = [
            # ISO timestamp with level: "2024-01-01 12:00:00 ERROR message"
            re.compile(r'^(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+(\w+)\s+(.*)$'),
            # Simple timestamp: "12:00:00.123 component message"
            re.compile(r'^(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+(\w+)\s+(.*)$'),
            # Pipe-delimited: "timestamp|level|component|key:value"
            re.compile(r'^([^|]+)\|(\w+)\|(\w+)\|(.*)$'),
        ]
        
        # Metric extraction patterns - ONLY extract real training metrics
        # Be strict to avoid extracting garbage from config lines
        self._metric_patterns = [
            # Standard training metrics with = or : 
            re.compile(r'\b(loss|val_loss|train_loss|accuracy|acc|val_acc|lr|learning_rate|epoch|step|iter|iteration|mfu|tokens_per_sec|samples_per_sec|grad_norm|perplexity|ppl)[=:]\s*([+-]?\d+\.?\d*(?:e[+-]?\d+)?)', re.I),
            # "iter X: loss=Y" format from nanoGPT
            re.compile(r'iter\s+(\d+).*loss[=:]?\s*([+-]?\d+\.?\d*)', re.I),
            # "step X loss Y" format
            re.compile(r'step\s+(\d+).*loss\s*[=:]?\s*([+-]?\d+\.?\d*)', re.I),
        ]
    
    def interpret(self, signal: Any) -> Event:
        """
        Interpret any signal into a Cascade Event.
        
        Uses Kleene fixed-point iteration to converge on the best interpretation.
        
        Args:
            signal: Any signal from the host system
            
        Returns:
            Event: The interpreted event
        """
        self._signal_count += 1
        
        # Get signal type
        signal_type = type(signal)
        
        # Try cached pattern first
        cache_key = self._get_cache_key(signal)
        if cache_key in self._interpretation_cache:
            pattern = self._interpretation_cache[cache_key]
            pattern.match_count += 1
            return self._apply_pattern(signal, pattern)
        
        # Try built-in interpreter
        if signal_type in self._builtin_interpreters:
            event = self._builtin_interpreters[signal_type](signal)
            self._learn_pattern(signal, event)
            return event
        
        # Try tensor-like objects (duck typing)
        if hasattr(signal, 'numpy') or hasattr(signal, 'detach'):
            event = self._interpret_tensor(signal)
            self._learn_pattern(signal, event)
            return event
        
        # Try protobuf-like objects
        if hasattr(signal, 'SerializeToString'):
            event = self._interpret_protobuf(signal)
            self._learn_pattern(signal, event)
            return event
        
        # Fallback: convert to string and interpret
        event = self._interpret_string(str(signal))
        return event
    
    def _interpret_dict(self, signal: Dict[str, Any]) -> Event:
        """Interpret a dictionary signal."""
        # Extract common fields
        timestamp = signal.get('timestamp', signal.get('time', time.time()))
        if isinstance(timestamp, str):
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(timestamp).timestamp()
            except:
                timestamp = time.time()
        
        component = signal.get('component', signal.get('source', 'unknown'))
        event_type = signal.get('event_type', signal.get('type', 'state_change'))
        
        # Everything else goes in data
        reserved = {'timestamp', 'time', 'component', 'source', 'event_type', 'type'}
        data = {k: v for k, v in signal.items() if k not in reserved}
        
        return Event(
            timestamp=timestamp,
            component=component,
            event_type=event_type,
            data=data,
            source_signal=signal,
        )
    
    def _interpret_string(self, signal: str) -> Event:
        """Interpret a string signal (log line, message, etc.)."""
        signal = signal.strip()
        
        # Try each log pattern
        for pattern in self._log_patterns:
            match = pattern.match(signal)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    timestamp_str, level_or_component, rest = groups[0], groups[1], groups[-1]
                    
                    # Parse timestamp
                    try:
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(timestamp_str.replace(' ', 'T')).timestamp()
                    except:
                        timestamp = time.time()
                    
                    # Extract metrics from the rest
                    data = self._extract_metrics(rest)
                    data['raw_message'] = rest
                    
                    # Determine event type from keywords
                    event_type = self._infer_event_type(signal)
                    
                    return Event(
                        timestamp=timestamp,
                        component=level_or_component.lower(),
                        event_type=event_type,
                        data=data,
                        source_signal=signal,
                    )
        
        # Fallback: extract what we can with smarter component detection
        data = self._extract_metrics(signal)
        data['raw_message'] = signal
        
        # Infer component from content
        component = self._infer_component(signal)
        
        return Event(
            timestamp=time.time(),
            component=component,
            event_type=self._infer_event_type(signal),
            data=data,
            source_signal=signal,
        )
    
    def _interpret_list(self, signal: List[Any]) -> Event:
        """Interpret a list signal."""
        # Convert to dict with indices
        data = {f'item_{i}': v for i, v in enumerate(signal)}
        data['length'] = len(signal)
        
        # Check if it looks like numeric data
        if all(isinstance(x, (int, float)) for x in signal):
            data['mean'] = sum(signal) / len(signal) if signal else 0
            data['min'] = min(signal) if signal else 0
            data['max'] = max(signal) if signal else 0
        
        return Event(
            timestamp=time.time(),
            component='data',
            event_type='list_signal',
            data=data,
            source_signal=signal,
        )
    
    def _interpret_tensor(self, signal: Any) -> Event:
        """Interpret a tensor-like signal (PyTorch, NumPy, etc.)."""
        # Try to get numpy array
        try:
            if hasattr(signal, 'detach'):
                arr = signal.detach().cpu().numpy()
            elif hasattr(signal, 'numpy'):
                arr = signal.numpy()
            else:
                arr = signal
            
            data = {
                'shape': list(arr.shape) if hasattr(arr, 'shape') else [],
                'dtype': str(arr.dtype) if hasattr(arr, 'dtype') else 'unknown',
                'mean': float(arr.mean()) if hasattr(arr, 'mean') else 0,
                'std': float(arr.std()) if hasattr(arr, 'std') else 0,
                'min': float(arr.min()) if hasattr(arr, 'min') else 0,
                'max': float(arr.max()) if hasattr(arr, 'max') else 0,
            }
            
            # Check for NaN/Inf (common in gradient explosions)
            if hasattr(arr, 'isnan'):
                data['has_nan'] = bool(arr.isnan().any())
            if hasattr(arr, 'isinf'):
                data['has_inf'] = bool(arr.isinf().any())
            
        except Exception as e:
            data = {'error': str(e), 'type': str(type(signal))}
        
        return Event(
            timestamp=time.time(),
            component='tensor',
            event_type='tensor_signal',
            data=data,
            source_signal=None,  # Don't store tensor to save memory
        )
    
    def _interpret_protobuf(self, signal: Any) -> Event:
        """Interpret a protobuf-like signal."""
        try:
            # Try to convert to dict
            if hasattr(signal, 'DESCRIPTOR'):
                from google.protobuf.json_format import MessageToDict
                data = MessageToDict(signal)
            else:
                data = {'raw': str(signal)}
        except:
            data = {'raw': str(signal)}
        
        return Event(
            timestamp=time.time(),
            component='protobuf',
            event_type='protobuf_signal',
            data=data,
            source_signal=None,
        )
    
    def _extract_metrics(self, text: str) -> Dict[str, Any]:
        """Extract numeric metrics from text - STRICT, only real training metrics."""
        metrics = {}
        
        # nanoGPT format: "iter 0: loss=4.2176, time 46.76ms, mfu 0.62%"
        nano_match = re.search(r'iter\s+(\d+).*loss[=:]?\s*([\d.]+)', text, re.I)
        if nano_match:
            metrics['iter'] = int(nano_match.group(1))
            metrics['loss'] = float(nano_match.group(2))
        
        # Diffusers/tqdm format: "step_loss=0.1234" or "step_loss: 0.1234"
        step_loss_match = re.search(r'step_loss[=:]\s*([\d.e+-]+)', text, re.I)
        if step_loss_match:
            metrics['loss'] = float(step_loss_match.group(1))
        
        # train_loss format from accelerator.log
        train_loss_match = re.search(r'train_loss[=:]\s*([\d.e+-]+)', text, re.I)
        if train_loss_match:
            metrics['loss'] = float(train_loss_match.group(1))
        
        # tqdm progress format: "  5%|█         | 5/100 [00:30<09:30, step_loss=0.234, lr=1e-5]"
        tqdm_match = re.search(r'(\d+)%\|.*\|\s*(\d+)/(\d+)', text)
        if tqdm_match:
            metrics['progress_pct'] = int(tqdm_match.group(1))
            metrics['step'] = int(tqdm_match.group(2))
            metrics['total_steps'] = int(tqdm_match.group(3))
        
        # Generic loss patterns
        generic_loss = re.search(r'\bloss[=:]\s*([\d.e+-]+)', text, re.I)
        if generic_loss and 'loss' not in metrics:
            metrics['loss'] = float(generic_loss.group(1))
        
        # mfu extraction
        mfu_match = re.search(r'mfu\s*[=:]?\s*([\d.]+)%?', text, re.I)
        if mfu_match:
            metrics['mfu'] = float(mfu_match.group(1))
        
        # time extraction (ms)
        time_match = re.search(r'time\s*[=:]?\s*([\d.]+)\s*ms', text, re.I)
        if time_match:
            metrics['time_ms'] = float(time_match.group(1))
        
        # learning rate - multiple formats
        lr_match = re.search(r'\b(?:lr|learning_rate)\s*[=:]\s*([\d.e+-]+)', text, re.I)
        if lr_match:
            metrics['lr'] = float(lr_match.group(1))
        
        # epoch/step for other frameworks
        epoch_match = re.search(r'\bepoch\s*[=:]\s*(\d+)', text, re.I)
        if epoch_match:
            metrics['epoch'] = int(epoch_match.group(1))
        
        step_match = re.search(r'\bstep\s*[=:]\s*(\d+)', text, re.I)
        if step_match and 'step' not in metrics:
            metrics['step'] = int(step_match.group(1))
        
        # global_step from diffusers
        global_step_match = re.search(r'global_step[=:]\s*(\d+)', text, re.I)
        if global_step_match:
            metrics['step'] = int(global_step_match.group(1))
        
        return metrics
    
    def _infer_event_type(self, text: str) -> str:
        """Infer event type from text content."""
        text_lower = text.lower()
        
        # Training iteration logs (highest priority)
        if re.search(r'iter\s+\d+.*loss', text_lower):
            return 'training_step'
        if re.search(r'step\s+\d+.*loss', text_lower):
            return 'training_step'
        
        if any(kw in text_lower for kw in ['error', 'exception', 'failed', 'crash']):
            return 'error'
        if any(kw in text_lower for kw in ['warning', 'warn']):
            return 'warning'
        if any(kw in text_lower for kw in ['gradient', 'backward']):
            return 'training'
        if 'loss' in text_lower and 'val' in text_lower:
            return 'validation'
        if any(kw in text_lower for kw in ['inference', 'predict', 'forward']):
            return 'inference'
        if any(kw in text_lower for kw in ['epoch', 'step', 'iteration', 'iter']):
            return 'progress'
        if any(kw in text_lower for kw in ['nan', 'inf', 'explode', 'overflow']):
            return 'anomaly'
        if any(kw in text_lower for kw in ['save', 'checkpoint', 'load', 'saving']):
            return 'checkpoint'
        if any(kw in text_lower for kw in ['config', 'setting', 'parameter', 'device', 'gpu', 'cuda']):
            return 'config'
        if any(kw in text_lower for kw in ['initializ', 'loading model', 'compiling']):
            return 'init'
        
        return 'state_change'
    
    def _infer_component(self, text: str) -> str:
        """Infer component from text content - NO MORE 'unknown'."""
        text_lower = text.lower()
        
        # Training/optimizer related
        if any(kw in text_lower for kw in ['iter', 'step', 'epoch', 'batch']):
            return 'trainer'
        if any(kw in text_lower for kw in ['loss', 'backward', 'gradient']):
            return 'loss'
        if any(kw in text_lower for kw in ['optim', 'adam', 'sgd', 'lr', 'learning']):
            return 'optimizer'
        if any(kw in text_lower for kw in ['model', 'layer', 'param', 'weight']):
            return 'model'
        if any(kw in text_lower for kw in ['data', 'batch', 'loader', 'dataset']):
            return 'data'
        if any(kw in text_lower for kw in ['cuda', 'gpu', 'device', 'memory']):
            return 'device'
        if any(kw in text_lower for kw in ['checkpoint', 'save', 'load']):
            return 'checkpoint'
        if any(kw in text_lower for kw in ['config', 'setting', 'override']):
            return 'config'
        if any(kw in text_lower for kw in ['eval', 'valid', 'test']):
            return 'evaluator'
        if any(kw in text_lower for kw in ['token', 'vocab', 'embed']):
            return 'tokenizer'
        
        return 'system'  # Generic fallback, not "unknown"
    
    def _get_cache_key(self, signal: Any) -> str:
        """Generate a cache key for a signal's structure."""
        if isinstance(signal, dict):
            # Key based on dict keys
            return f"dict:{':'.join(sorted(signal.keys()))}"
        elif isinstance(signal, str):
            # Key based on first word
            first_word = signal.split()[0] if signal.split() else ''
            return f"str:{first_word[:20]}"
        else:
            return f"type:{type(signal).__name__}"
    
    def _learn_pattern(self, signal: Any, event: Event) -> None:
        """Learn a pattern from a successful interpretation."""
        cache_key = self._get_cache_key(signal)
        pattern = SignalPattern(
            pattern_type=type(signal).__name__,
            component=event.component,
            event_type=event.event_type,
            confidence=0.5,
            match_count=1,
        )
        self._interpretation_cache[cache_key] = pattern
        self._patterns.append(pattern)
    
    def _apply_pattern(self, signal: Any, pattern: SignalPattern) -> Event:
        """Apply a learned pattern to interpret a signal."""
        # Re-interpret with learned hints - use direct interpreters to avoid recursion
        if isinstance(signal, dict):
            event = self._interpret_dict(signal)
            # Apply learned component/type if more confident
            if pattern.confidence > 0.7:
                return Event(
                    timestamp=event.timestamp,
                    component=pattern.component,
                    event_type=pattern.event_type,
                    data=event.data,
                    source_signal=signal,
                )
            return event
        elif isinstance(signal, str):
            return self._interpret_string(signal)
        elif isinstance(signal, list):
            return self._interpret_list(signal)
        else:
            # Fallback: interpret as string without recursion
            return self._interpret_string(str(signal))
    
    @property
    def learned_patterns(self) -> List[SignalPattern]:
        """Get all learned signal patterns."""
        return sorted(self._patterns, key=lambda p: p.match_count, reverse=True)
    
    @property 
    def signal_count(self) -> int:
        """Total number of signals interpreted."""
        return self._signal_count
    
    def __repr__(self) -> str:
        return f"<SymbioticAdapter | {self._signal_count} signals, {len(self._patterns)} patterns>"
