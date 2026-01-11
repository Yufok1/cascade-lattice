"""
CASCADE System Observatory - Log Adapters

Transform any log format into CASCADE events.
Each adapter parses a specific log format and emits standardized events.

The key insight: all logs are just events with timestamps, components, and data.
CASCADE doesn't care WHERE the events come from - it visualizes causation.

Enhanced with:
- drain3: IBM's template mining for auto-discovering log structure
- dateparser: Universal timestamp parsing for any format
"""

import re
import json
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Generator, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Universal parsing libraries
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False

try:
    from drain3 import TemplateMiner
    from drain3.template_miner_config import TemplateMinerConfig
    HAS_DRAIN3 = True
except ImportError:
    HAS_DRAIN3 = False


@dataclass
class ParsedEvent:
    """Standardized event parsed from any log format."""
    timestamp: float
    event_type: str
    component: str
    data: Dict[str, Any]
    raw_line: str = ""
    
    # Hash chain for provenance
    event_hash: str = field(default="")
    parent_hash: str = field(default="")
    
    def __post_init__(self):
        if not self.event_hash:
            self.event_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute deterministic hash of this event."""
        content = json.dumps({
            "ts": self.timestamp,
            "type": self.event_type,
            "component": self.component,
            "data": self.data,
            "parent": self.parent_hash,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_cascade_event(self) -> Dict[str, Any]:
        """Convert to CASCADE event format for visualization."""
        return {
            "event_id": f"sys_{self.event_hash}",
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "component": self.component,
            "data": {
                **self.data,
                "hash": self.event_hash,
                "parent_hash": self.parent_hash,
            },
        }


class LogAdapter(ABC):
    """
    Base class for log adapters.
    
    Implement parse_line() to convert your log format to ParsedEvent.
    """
    
    name: str = "base"
    description: str = "Base log adapter"
    
    def __init__(self):
        self.event_count = 0
        self.last_hash = ""
    
    @abstractmethod
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        """
        Parse a single log line.
        
        Args:
            line: Raw log line
            
        Returns:
            ParsedEvent if successfully parsed, None to skip this line
        """
        pass
    
    def parse_file(self, filepath: str) -> Generator[ParsedEvent, None, None]:
        """Parse all lines in a file."""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                event = self.parse_line(line.strip())
                if event:
                    event.parent_hash = self.last_hash
                    event.event_hash = event._compute_hash()
                    self.last_hash = event.event_hash
                    self.event_count += 1
                    yield event
    
    def parse_lines(self, lines: List[str]) -> Generator[ParsedEvent, None, None]:
        """Parse a list of lines."""
        for line in lines:
            event = self.parse_line(line.strip())
            if event:
                event.parent_hash = self.last_hash
                event.event_hash = event._compute_hash()
                self.last_hash = event.event_hash
                self.event_count += 1
                yield event


class UniversalAdapter(LogAdapter):
    """
    THE UNIVERSAL ADAPTER - One parser to rule them all.
    
    Handles ANY log format through recursive field discovery:
    - JSON at any nesting depth (CASCADE, ELK, Datadog, custom)
    - Apache/Nginx access logs
    - Kubernetes events
    - Syslog format
    - Generic timestamped text
    - Raw text (fallback)
    
    The philosophy: logs are just events. Every line has:
    - A timestamp (explicit or implicit from order)
    - A source/component (explicit or inferred)
    - A severity/type (explicit or inferred)
    - A message (always present)
    
    This adapter finds these fields regardless of format.
    """
    
    name = "universal"
    description = "Universal Log Parser - handles any format"
    
    # Field name variations (searched recursively in JSON)
    TIMESTAMP_ALIASES = {
        "timestamp", "time", "ts", "@timestamp", "datetime", "date", "t",
        "created", "created_at", "logged_at", "event_time", "log_time",
        "when", "epoch", "unix_time", "utc_time", "local_time"
    }
    
    COMPONENT_ALIASES = {
        "component", "service", "logger", "source", "module", "name",
        "app", "application", "origin", "host", "hostname", "container",
        "pod", "namespace", "class", "category", "tag", "facility"
    }
    
    EVENT_TYPE_ALIASES = {
        "event_type", "level", "severity", "type", "log_level", "loglevel",
        "priority", "status", "kind", "action", "verb", "method"
    }
    
    MESSAGE_ALIASES = {
        "message", "msg", "text", "body", "content", "raw", "raw_message",
        "description", "detail", "details", "info", "payload", "log"
    }
    
    # Severity indicators (for inferring event type from text)
    SEVERITY_PATTERNS = {
        "critical": r'\b(CRITICAL|FATAL|EMERGENCY|PANIC)\b',
        "error": r'\b(ERROR|ERR|EXCEPTION|FAIL(ED|URE)?)\b',
        "warning": r'\b(WARN(ING)?|CAUTION|ALERT)\b',
        "info": r'\b(INFO|NOTICE|LOG)\b',
        "debug": r'\b(DEBUG|TRACE|VERBOSE)\b',
    }
    
    # Timestamp regex patterns (ordered by specificity)
    TIMESTAMP_PATTERNS = [
        # ISO 8601 variants
        (r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)', 'iso'),
        # Unix timestamp (float or int)
        (r'\b(1[5-9]\d{8}(?:\.\d+)?)\b', 'unix'),  # 1500000000+ range
        # Apache/Nginx format
        (r'\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}(?:\s*[+-]\d{4})?)\]', 'apache'),
        # Syslog format
        (r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})', 'syslog'),
        # Common date formats
        (r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})', 'slash'),
        (r'(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})', 'us'),
    ]
    
    # Component extraction patterns (handle leading whitespace after timestamp removal)
    COMPONENT_PATTERNS = [
        # [component] or (component) - with optional leading whitespace
        r'^\s*\[([^\]]+)\]',
        r'^\s*\(([^\)]+)\)',
        # component: at start (with optional leading whitespace)
        r'^\s*([A-Za-z][\w\-\.]+):',
        # Kubernetes style: namespace/pod
        r'\b([a-z][\w\-]+/[a-z][\w\-]+)\b',
        # Docker container ID
        r'\b([a-f0-9]{12})\b',
    ]
    
    # Common delimiters to auto-detect (ordered by specificity)
    DELIMITERS = [' | ', ' - ', '\t', ' :: ', ' -- ']
    
    def __init__(self):
        super().__init__()
        self._line_number = 0
        self._base_time = time.time()
        self._detected_delimiter = None
        self._detected_format = None  # Cached format info after learning
        self._sample_lines = []  # Collect lines for format learning
        self._learning_complete = False
        
        # Initialize drain3 template miner if available
        self._template_miner = None
        if HAS_DRAIN3:
            config = TemplateMinerConfig()
            # drain3 config is ready to use without explicit load
            self._template_miner = TemplateMiner(config=config)
    
    def parse_lines(self, lines: List[str]) -> Generator[ParsedEvent, None, None]:
        """
        Parse lines with upfront format learning.
        Override base class to learn format from first N lines before parsing any.
        """
        # Learn format from first 50 lines (or all if less)
        sample = [l.strip() for l in lines[:50] if l.strip() and not l.strip().startswith('{')]
        if sample and not self._learning_complete:
            self._learn_format(sample)
        
        # Now parse all lines with learned format
        for line in lines:
            event = self.parse_line(line.strip())
            if event:
                event.parent_hash = self.last_hash
                event.event_hash = event._compute_hash()
                self.last_hash = event.event_hash
                self.event_count += 1
                yield event
    
    def parse_file(self, filepath: str) -> Generator[ParsedEvent, None, None]:
        """
        Parse file with upfront format learning.
        Override base class to learn format before yielding events.
        """
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            # Read first batch to learn format
            sample_lines = []
            all_lines = []
            for i, line in enumerate(f):
                all_lines.append(line)
                if i < 50 and line.strip() and not line.strip().startswith('{'):
                    sample_lines.append(line.strip())
            
            # Learn format
            if sample_lines and not self._learning_complete:
                self._learn_format(sample_lines)
        
        # Re-read and parse with learned format
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                event = self.parse_line(line.strip())
                if event:
                    event.parent_hash = self.last_hash
                    event.event_hash = event._compute_hash()
                    self.last_hash = event.event_hash
                    self.event_count += 1
                    yield event
    
    def _learn_format(self, lines: List[str]) -> None:
        """
        Learn log format from sample lines using statistical analysis.
        Detects: delimiter, field positions, timestamp format.
        """
        if self._learning_complete or len(lines) < 3:
            return
        
        # Count delimiter occurrences across lines
        delimiter_counts = {d: 0 for d in self.DELIMITERS}
        for line in lines[:50]:  # Sample first 50 lines
            for delim in self.DELIMITERS:
                count = line.count(delim)
                if count >= 2:  # At least 3 fields
                    delimiter_counts[delim] += count
        
        # Find most common delimiter
        best_delim = max(delimiter_counts, key=delimiter_counts.get)
        if delimiter_counts[best_delim] > len(lines) * 2:  # Significant presence
            self._detected_delimiter = best_delim
            self._analyze_delimited_format(lines, best_delim)
        
        self._learning_complete = True
    
    def _analyze_delimited_format(self, lines: List[str], delimiter: str) -> None:
        """
        Analyze field positions in delimiter-separated log format.
        Learns which field contains timestamp, level, component, message.
        """
        # Split sample lines
        field_samples = []
        for line in lines[:20]:
            parts = [p.strip() for p in line.split(delimiter)]
            if len(parts) >= 3:
                field_samples.append(parts)
        
        if not field_samples:
            return
        
        # Analyze each field position
        num_fields = min(len(s) for s in field_samples)
        format_info = {
            'delimiter': delimiter,
            'timestamp_idx': None,
            'level_idx': None,
            'component_idx': None,
            'message_idx': num_fields - 1,  # Default: last field is message
        }
        
        LEVEL_KEYWORDS = {'DEBUG', 'INFO', 'WARNING', 'WARN', 'ERROR', 'CRITICAL', 'FATAL', 'TRACE'}
        
        for idx in range(num_fields):
            field_values = [s[idx] if idx < len(s) else '' for s in field_samples]
            
            # Check if this field contains timestamps
            timestamp_score = sum(1 for v in field_values if self._looks_like_timestamp(v))
            if timestamp_score > len(field_values) * 0.7:
                format_info['timestamp_idx'] = idx
                continue
            
            # Check if this field contains log levels
            level_score = sum(1 for v in field_values if v.upper() in LEVEL_KEYWORDS)
            if level_score > len(field_values) * 0.5:
                format_info['level_idx'] = idx
                continue
            
            # Check if this field looks like component names
            # Components are typically: lowercase, underscores/dots, consistent format
            component_score = sum(1 for v in field_values 
                                 if v and re.match(r'^[a-zA-Z][\w\.\-]*$', v)
                                 and v.upper() not in LEVEL_KEYWORDS
                                 and not self._looks_like_timestamp(v))
            if component_score > len(field_values) * 0.5 and format_info['component_idx'] is None:
                format_info['component_idx'] = idx
        
        self._detected_format = format_info
    
    def _looks_like_timestamp(self, value: str) -> bool:
        """Check if a string looks like a timestamp."""
        if not value:
            return False
        # Check for time-like patterns: digits with : or - or .
        if re.match(r'^\d{1,4}[-/:]\d{1,2}[-/:T]', value):
            return True
        if re.match(r'^\d{2}:\d{2}:\d{2}', value):
            return True
        # Unix timestamp
        if re.match(r'^1[5-9]\d{8}', value):
            return True
        return False
    
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        """
        Universal parse - handles any format with intelligent auto-detection.
        """
        if not line or not line.strip():
            return None
        
        line = line.strip()
        self._line_number += 1
        
        # Collect samples for format learning
        if not self._learning_complete and len(self._sample_lines) < 50:
            self._sample_lines.append(line)
            if len(self._sample_lines) >= 10:
                self._learn_format(self._sample_lines)
        
        # Try JSON first (handles all structured formats)
        if line.startswith('{'):
            try:
                obj = json.loads(line)
                return self._parse_json(obj, line)
            except json.JSONDecodeError:
                pass
        
        # Use learned delimited format if detected
        if self._detected_format:
            return self._parse_delimited(line)
        
        # Fall back to traditional text parsing
        return self._parse_text(line)
    
    def _parse_delimited(self, line: str) -> ParsedEvent:
        """
        Parse line using auto-detected delimiter format.
        This is the intelligent parsing path for structured text logs.
        """
        fmt = self._detected_format
        parts = [p.strip() for p in line.split(fmt['delimiter'])]
        
        # Extract fields by learned positions
        timestamp = None
        level = 'info'
        component = 'system'
        message = line
        
        if fmt['timestamp_idx'] is not None and fmt['timestamp_idx'] < len(parts):
            ts_str = parts[fmt['timestamp_idx']]
            timestamp = self._parse_timestamp_universal(ts_str)
        
        if fmt['level_idx'] is not None and fmt['level_idx'] < len(parts):
            level = self._normalize_event_type(parts[fmt['level_idx']])
        
        if fmt['component_idx'] is not None and fmt['component_idx'] < len(parts):
            component = parts[fmt['component_idx']]
        
        if fmt['message_idx'] is not None and fmt['message_idx'] < len(parts):
            # Message is everything from message_idx onwards (may be split by delimiter)
            msg_start = fmt['message_idx']
            message = fmt['delimiter'].join(parts[msg_start:])
        
        if timestamp is None:
            timestamp = self._base_time + (self._line_number * 0.001)
        
        # Feed to drain3 for template mining (if available)
        if self._template_miner:
            result = self._template_miner.add_log_message(message)
            # Could use result.get_template() for pattern analysis
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=level,
            component=component,
            data={"message": message},
            raw_line=line,
        )
    
    def _parse_timestamp_universal(self, ts_str: str) -> Optional[float]:
        """
        Parse any timestamp format using dateparser (if available) or fallback regex.
        """
        if not ts_str:
            return None
        
        # Try dateparser first (handles almost any format)
        if HAS_DATEPARSER:
            try:
                parsed = dateparser.parse(ts_str, settings={
                    'RETURN_AS_TIMEZONE_AWARE': False,
                    'PREFER_DATES_FROM': 'past',
                })
                if parsed:
                    return parsed.timestamp()
            except Exception:
                pass
        
        # Fallback to existing patterns
        return self._parse_timestamp_string(ts_str, 'auto')
    
    def _parse_json(self, obj: dict, raw_line: str) -> ParsedEvent:
        """
        Parse JSON object with recursive field discovery.
        Handles any nesting depth - finds fields wherever they are.
        """
        # Recursively search for known fields
        timestamp = self._find_field(obj, self.TIMESTAMP_ALIASES)
        component = self._find_field(obj, self.COMPONENT_ALIASES)
        event_type = self._find_field(obj, self.EVENT_TYPE_ALIASES)
        message = self._find_field(obj, self.MESSAGE_ALIASES)
        
        # Parse timestamp
        if timestamp is not None:
            ts = self._parse_timestamp_value(timestamp)
        else:
            ts = self._base_time + (self._line_number * 0.001)
        
        # Normalize event type
        if event_type:
            event_type = self._normalize_event_type(str(event_type))
        else:
            # Infer from message content
            event_type = self._infer_severity(str(message) if message else str(obj))
        
        # Default component
        if not component:
            component = "system"
        else:
            component = str(component)
        
        # Build data dict
        data = self._flatten_to_data(obj, message)
        
        return ParsedEvent(
            timestamp=ts,
            event_type=event_type,
            component=component,
            data=data,
            raw_line=raw_line,
        )
    
    def _find_field(self, obj: Any, aliases: set, depth: int = 0) -> Any:
        """
        Recursively search for a field by any of its aliases.
        Returns the first match found (breadth-first within each level).
        """
        if depth > 10:  # Prevent infinite recursion
            return None
        
        if isinstance(obj, dict):
            # Check this level first
            for key in obj:
                if key.lower() in aliases:
                    return obj[key]
            
            # Then recurse into nested dicts
            for key, value in obj.items():
                if isinstance(value, dict):
                    result = self._find_field(value, aliases, depth + 1)
                    if result is not None:
                        return result
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    # Check first item of list of dicts
                    result = self._find_field(value[0], aliases, depth + 1)
                    if result is not None:
                        return result
        
        return None
    
    def _flatten_to_data(self, obj: dict, message: Any = None) -> Dict[str, Any]:
        """
        Flatten JSON object to data dict for visualization.
        Preserves important nested structures while making data accessible.
        """
        data = {}
        
        # Set message
        if message is not None:
            if isinstance(message, dict):
                data.update(message)
            else:
                data["message"] = str(message)
        
        # Extract key fields at any level
        for key, value in obj.items():
            key_lower = key.lower()
            
            # Skip already processed fields
            if key_lower in self.TIMESTAMP_ALIASES | self.MESSAGE_ALIASES:
                continue
            
            # Include scalar values directly
            if isinstance(value, (str, int, float, bool)) or value is None:
                data[key] = value
            # Include small dicts inline
            elif isinstance(value, dict) and len(value) <= 5:
                for k, v in value.items():
                    if isinstance(v, (str, int, float, bool)):
                        data[f"{key}.{k}"] = v
            # Summarize large structures
            elif isinstance(value, dict):
                data[f"_{key}_keys"] = list(value.keys())[:10]
            elif isinstance(value, list):
                data[f"_{key}_count"] = len(value)
        
        return data
    
    def _parse_text(self, line: str) -> ParsedEvent:
        """
        Parse unstructured text log line.
        Extracts timestamp, component, severity from text patterns.
        """
        timestamp = None
        component = "system"
        remaining = line
        
        # Try to extract timestamp
        for pattern, fmt in self.TIMESTAMP_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                ts_str = match.group(1)
                timestamp = self._parse_timestamp_string(ts_str, fmt)
                # Remove timestamp from remaining text
                remaining = line[:match.start()] + line[match.end():]
                break
        
        if timestamp is None:
            timestamp = self._base_time + (self._line_number * 0.001)
        
        # Try to extract component
        SEVERITY_WORDS = {'error', 'err', 'warn', 'warning', 'info', 'debug', 'trace', 'fatal', 'critical'}
        for pattern in self.COMPONENT_PATTERNS:
            match = re.search(pattern, remaining)
            if match:
                candidate = match.group(1)
                # Don't treat severity keywords as components
                if candidate.lower() not in SEVERITY_WORDS:
                    component = candidate
                remaining = remaining[match.end():].strip()
                break
        
        # Infer severity from text
        event_type = self._infer_severity(line)
        
        # Clean up message
        message = remaining.strip()
        if message.startswith(':'):
            message = message[1:].strip()
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            component=component,
            data={"message": message},
            raw_line=line,
        )
    
    def _parse_timestamp_value(self, value: Any) -> float:
        """Parse timestamp from any format."""
        if isinstance(value, (int, float)):
            # Unix timestamp - check if milliseconds
            if value > 1e12:
                return value / 1000
            return float(value)
        
        if isinstance(value, str):
            return self._parse_timestamp_string(value, 'auto')
        
        return self._base_time + (self._line_number * 0.001)
    
    def _parse_timestamp_string(self, ts_str: str, fmt: str) -> float:
        """Parse timestamp string to Unix timestamp."""
        try:
            if fmt == 'unix' or (fmt == 'auto' and ts_str.replace('.', '').isdigit()):
                val = float(ts_str)
                return val / 1000 if val > 1e12 else val
            
            if fmt == 'iso' or fmt == 'auto':
                # ISO 8601
                try:
                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    return dt.timestamp()
                except:
                    pass
            
            if fmt == 'apache':
                # Apache: 10/Oct/2000:13:55:36 +0700
                dt = datetime.strptime(ts_str.split()[0], "%d/%b/%Y:%H:%M:%S")
                return dt.timestamp()
            
            if fmt == 'syslog':
                # Syslog: Oct 10 13:55:36 (no year)
                current_year = datetime.now().year
                dt = datetime.strptime(f"{current_year} {ts_str}", "%Y %b %d %H:%M:%S")
                return dt.timestamp()
            
            # Try common formats
            for date_fmt in [
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S",
            ]:
                try:
                    dt = datetime.strptime(ts_str.split('+')[0].split('Z')[0], date_fmt)
                    return dt.timestamp()
                except:
                    continue
        except:
            pass
        
        return self._base_time + (self._line_number * 0.001)
    
    def _normalize_event_type(self, event_type: str) -> str:
        """Normalize event type to standard values."""
        et = event_type.lower().strip()
        
        # Map common variations
        if et in ('err', 'exception', 'fail', 'failed', 'failure', 'fatal', 'critical', 'emergency', 'panic'):
            return 'error'
        if et in ('warn', 'caution', 'alert'):
            return 'warning'
        if et in ('information', 'notice', 'log'):
            return 'info'
        if et in ('trace', 'verbose', 'fine', 'finer', 'finest'):
            return 'debug'
        if et in ('state_change', 'transition', 'change'):
            return 'state_change'
        if et in ('checkpoint', 'save', 'snapshot'):
            return 'checkpoint'
        if et in ('progress', 'step', 'iteration'):
            return 'progress'
        if et in ('config', 'configuration', 'setting', 'setup'):
            return 'config'
        if et in ('metric', 'measure', 'stat', 'stats'):
            return 'metric'
        if et in ('anomaly', 'outlier', 'unusual'):
            return 'anomaly'
        
        return et if et else 'info'
    
    def _infer_severity(self, text: str) -> str:
        """Infer severity/event type from text content."""
        for severity, pattern in self.SEVERITY_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return severity
        return 'info'


class JSONLAdapter(LogAdapter):
    """
    Parse JSON Lines format (one JSON object per line).
    
    Expected fields (flexible):
    - timestamp/time/ts/@timestamp: Unix timestamp or ISO string
    - level/severity/type: Event type (info, error, warning, etc.)
    - component/service/logger/source: Which component
    - message/msg/data: Event data
    
    Also supports CASCADE's nested format:
    - {"event": {"timestamp": ..., "component": ..., "event_type": ...}, "metrics": {...}, "triage": {...}}
    """
    
    name = "jsonl"
    description = "JSON Lines (structured logs)"
    
    TIMESTAMP_FIELDS = ["timestamp", "time", "ts", "@timestamp", "datetime", "date"]
    LEVEL_FIELDS = ["level", "severity", "type", "log_level", "loglevel", "event_type"]
    COMPONENT_FIELDS = ["component", "service", "logger", "source", "module", "name"]
    MESSAGE_FIELDS = ["message", "msg", "data", "content", "text", "body", "raw_message", "raw"]
    
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        if not line:
            return None
        
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        
        # Check for CASCADE nested format: {"event": {...}, "metrics": {...}, "triage": {...}}
        if "event" in obj and isinstance(obj["event"], dict):
            return self._parse_cascade_format(obj)
        
        # Standard JSONL parsing
        return self._parse_standard_format(obj, line)
    
    def _parse_cascade_format(self, obj: dict) -> Optional[ParsedEvent]:
        """Parse CASCADE's nested tape format."""
        evt = obj["event"]
        
        # Direct field extraction from CASCADE format
        timestamp = evt.get("timestamp", time.time())
        event_type = evt.get("event_type", "info")
        component = evt.get("component", "system")
        
        # Build data from CASCADE event
        data = {}
        
        # Get raw message
        if "raw" in evt:
            data["message"] = evt["raw"]
        elif "data" in evt and isinstance(evt["data"], dict):
            if "raw_message" in evt["data"]:
                data["message"] = evt["data"]["raw_message"]
            data.update(evt["data"])
        
        # Include event_id if present
        if "event_id" in evt:
            data["event_id"] = evt["event_id"]
        
        # Include metrics summary if present (for visualization)
        if "metrics" in obj and isinstance(obj["metrics"], dict):
            metrics = obj["metrics"]
            if "event_count" in metrics:
                data["_event_count"] = metrics["event_count"]
            if "health_status" in metrics:
                data["_health"] = metrics["health_status"].get("overall", "unknown")
        
        # Include triage status if present
        if "triage" in obj and isinstance(obj["triage"], dict):
            triage = obj["triage"]
            data["_triage_status"] = triage.get("status", "UNKNOWN")
            data["_triage_action"] = triage.get("action", "")
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            component=component,
            data=data,
            raw_line=json.dumps(obj),
        )
    
    def _parse_standard_format(self, obj: dict, line: str) -> Optional[ParsedEvent]:
        """Parse standard JSONL format."""
        # Extract timestamp
        timestamp = None
        for field in self.TIMESTAMP_FIELDS:
            if field in obj:
                timestamp = self._parse_timestamp(obj[field])
                break
        if timestamp is None:
            timestamp = time.time()
        
        # Extract event type
        event_type = "info"
        for field in self.LEVEL_FIELDS:
            if field in obj:
                event_type = str(obj[field]).lower()
                break
        
        # Extract component
        component = "system"
        for field in self.COMPONENT_FIELDS:
            if field in obj:
                component = str(obj[field])
                break
        
        # Extract message/data
        data = {}
        for field in self.MESSAGE_FIELDS:
            if field in obj:
                msg = obj[field]
                if isinstance(msg, dict):
                    data.update(msg)
                else:
                    data["message"] = str(msg)
                break
        
        # Include all other fields in data
        for k, v in obj.items():
            if k not in self.TIMESTAMP_FIELDS + self.LEVEL_FIELDS + self.COMPONENT_FIELDS + self.MESSAGE_FIELDS:
                data[k] = v
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            component=component,
            data=data,
            raw_line=line,
        )
    
    def _parse_timestamp(self, value: Any) -> float:
        """Parse various timestamp formats to Unix timestamp."""
        if isinstance(value, (int, float)):
            # Already numeric - check if milliseconds
            if value > 1e12:
                return value / 1000
            return value
        
        if isinstance(value, str):
            # Try ISO format
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.timestamp()
            except:
                pass
            
            # Try common formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%b/%Y:%H:%M:%S",
            ]:
                try:
                    dt = datetime.strptime(value.split("+")[0].split("-")[0] if "+" in value else value, fmt)
                    return dt.timestamp()
                except:
                    continue
        
        return time.time()


class ApacheLogAdapter(LogAdapter):
    """
    Parse Apache Combined Log Format.
    
    Format: %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-agent}i"
    Example: 127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/start.html" "Mozilla/4.08 [en] (Win98; I ;Nav)"
    """
    
    name = "apache"
    description = "Apache Combined Log Format"
    
    # Regex for Apache combined format
    PATTERN = re.compile(
        r'^(?P<ip>[\d\.]+)\s+'
        r'(?P<ident>\S+)\s+'
        r'(?P<user>\S+)\s+'
        r'\[(?P<timestamp>[^\]]+)\]\s+'
        r'"(?P<method>\w+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+'
        r'(?P<status>\d+)\s+'
        r'(?P<size>\S+)'
        r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<useragent>[^"]*)")?'
    )
    
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        if not line:
            return None
        
        match = self.PATTERN.match(line)
        if not match:
            return None
        
        d = match.groupdict()
        
        # Parse timestamp [10/Oct/2000:13:55:36 -0700]
        try:
            ts_str = d["timestamp"].split()[0]  # Remove timezone
            dt = datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S")
            timestamp = dt.timestamp()
        except:
            timestamp = time.time()
        
        # Determine event type by status code
        status = int(d.get("status", 200))
        if status >= 500:
            event_type = "error"
        elif status >= 400:
            event_type = "warning"
        elif status >= 300:
            event_type = "redirect"
        else:
            event_type = "request"
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            component=f"http:{d.get('method', 'GET')}",
            data={
                "ip": d.get("ip"),
                "method": d.get("method"),
                "path": d.get("path"),
                "status": status,
                "size": int(d.get("size", 0)) if d.get("size", "-") != "-" else 0,
                "referer": d.get("referer", ""),
                "user_agent": d.get("useragent", ""),
            },
            raw_line=line,
        )


class NginxLogAdapter(ApacheLogAdapter):
    """
    Parse Nginx access logs (same format as Apache combined by default).
    """
    
    name = "nginx"
    description = "Nginx Access Log Format"


class KubernetesLogAdapter(LogAdapter):
    """
    Parse Kubernetes events and pod logs.
    
    Handles:
    - kubectl get events output
    - Pod log format: timestamp stdout/stderr F message
    - JSON structured logs from pods
    """
    
    name = "kubernetes"
    description = "Kubernetes Events & Pod Logs"
    
    # Pod log pattern: 2024-01-01T00:00:00.000000000Z stdout F message
    POD_LOG_PATTERN = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:.]+Z?)\s+'
        r'(?P<stream>stdout|stderr)\s+'
        r'(?P<flag>\S+)\s+'
        r'(?P<message>.*)$'
    )
    
    # Kubectl events pattern
    EVENT_PATTERN = re.compile(
        r'^(?P<last_seen>\S+)\s+'
        r'(?P<type>\S+)\s+'
        r'(?P<reason>\S+)\s+'
        r'(?P<object>\S+)\s+'
        r'(?P<message>.*)$'
    )
    
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        if not line:
            return None
        
        # Try JSON first (structured pod logs)
        if line.startswith("{"):
            jsonl = JSONLAdapter()
            result = jsonl.parse_line(line)
            if result:
                result.component = f"k8s:{result.component}"
                return result
        
        # Try pod log format
        match = self.POD_LOG_PATTERN.match(line)
        if match:
            d = match.groupdict()
            try:
                dt = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
                timestamp = dt.timestamp()
            except:
                timestamp = time.time()
            
            return ParsedEvent(
                timestamp=timestamp,
                event_type="error" if d["stream"] == "stderr" else "log",
                component=f"k8s:pod",
                data={
                    "stream": d["stream"],
                    "message": d["message"],
                },
                raw_line=line,
            )
        
        # Try kubectl events format
        match = self.EVENT_PATTERN.match(line)
        if match:
            d = match.groupdict()
            event_type = d.get("type", "Normal").lower()
            if event_type == "warning":
                event_type = "warning"
            elif event_type == "normal":
                event_type = "info"
            
            return ParsedEvent(
                timestamp=time.time(),  # Events don't have exact timestamp in this format
                event_type=event_type,
                component=f"k8s:{d.get('object', 'unknown').split('/')[0]}",
                data={
                    "reason": d.get("reason"),
                    "object": d.get("object"),
                    "message": d.get("message"),
                },
                raw_line=line,
            )
        
        return None


class GenericLogAdapter(LogAdapter):
    """
    Parse generic timestamped logs.
    
    Attempts to extract:
    - Timestamp from beginning of line
    - Log level (INFO, ERROR, WARN, DEBUG, etc.)
    - Component name (often in brackets)
    - Message
    """
    
    name = "generic"
    description = "Generic Timestamped Logs"
    
    # Common timestamp patterns at start of line
    TIMESTAMP_PATTERNS = [
        (re.compile(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)'), "%Y-%m-%dT%H:%M:%S"),
        (re.compile(r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})'), "%Y/%m/%d %H:%M:%S"),
        (re.compile(r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'), None),  # Syslog
        (re.compile(r'^(\d{10,13})'), None),  # Unix timestamp
    ]
    
    # Level patterns
    LEVEL_PATTERN = re.compile(r'\b(DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRIT(?:ICAL)?|FATAL|SEVERE|TRACE)\b', re.I)
    
    # Component patterns (in brackets or before colon)
    COMPONENT_PATTERN = re.compile(r'\[([^\]]+)\]|^[^:]+:\s*(\S+):')
    
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        if not line:
            return None
        
        timestamp = time.time()
        remaining = line
        
        # Extract timestamp
        for pattern, fmt in self.TIMESTAMP_PATTERNS:
            match = pattern.match(line)
            if match:
                ts_str = match.group(1)
                try:
                    if fmt:
                        dt = datetime.strptime(ts_str.split(".")[0].replace("T", " "), fmt.replace("T", " "))
                        timestamp = dt.timestamp()
                    elif ts_str.isdigit():
                        ts = int(ts_str)
                        timestamp = ts / 1000 if ts > 1e12 else ts
                except:
                    pass
                remaining = line[match.end():].strip()
                break
        
        # Extract level
        event_type = "info"
        level_match = self.LEVEL_PATTERN.search(remaining)
        if level_match:
            level = level_match.group(1).upper()
            if level in ("ERROR", "CRITICAL", "CRIT", "FATAL", "SEVERE"):
                event_type = "error"
            elif level in ("WARN", "WARNING"):
                event_type = "warning"
            elif level == "DEBUG":
                event_type = "debug"
            elif level == "TRACE":
                event_type = "trace"
        
        # Extract component
        component = "system"
        comp_match = self.COMPONENT_PATTERN.search(remaining)
        if comp_match:
            component = comp_match.group(1) or comp_match.group(2) or "system"
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            component=component,
            data={"message": remaining},
            raw_line=line,
        )


class RegexAdapter(LogAdapter):
    r"""
    Parse logs using a custom regex pattern.
    
    The regex should have named groups:
    - timestamp (optional): Timestamp string
    - type/level (optional): Event type
    - component (optional): Component name
    - message (optional): Message or data
    
    Example pattern:
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<component>\S+) (?P<message>.*)$'
    """
    
    name = "regex"
    description = "Custom Regex Pattern"
    
    def __init__(self, pattern: str, timestamp_format: str = None):
        """
        Args:
            pattern: Regex pattern with named groups
            timestamp_format: strptime format for timestamp group
        """
        super().__init__()
        self.pattern = re.compile(pattern)
        self.timestamp_format = timestamp_format
    
    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        if not line:
            return None
        
        match = self.pattern.match(line)
        if not match:
            return None
        
        d = match.groupdict()
        
        # Parse timestamp
        timestamp = time.time()
        if "timestamp" in d and d["timestamp"]:
            if self.timestamp_format:
                try:
                    dt = datetime.strptime(d["timestamp"], self.timestamp_format)
                    timestamp = dt.timestamp()
                except:
                    pass
            else:
                # Try to parse automatically
                try:
                    dt = datetime.fromisoformat(d["timestamp"])
                    timestamp = dt.timestamp()
                except:
                    pass
        
        # Event type
        event_type = d.get("type") or d.get("level") or "info"
        event_type = event_type.lower()
        
        # Component
        component = d.get("component") or d.get("source") or "system"
        
        # Message/data
        message = d.get("message") or d.get("data") or ""
        data = {"message": message}
        
        # Include any other captured groups
        for k, v in d.items():
            if k not in ("timestamp", "type", "level", "component", "source", "message", "data") and v:
                data[k] = v
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            component=component,
            data=data,
            raw_line=line,
        )


def auto_detect_adapter(sample_lines: List[str]) -> LogAdapter:
    """
    Auto-detect the best adapter for a set of sample lines.
    
    In practice, UniversalAdapter handles everything.
    This function exists for backwards compatibility and edge cases.
    
    Args:
        sample_lines: First N lines of the log file
        
    Returns:
        Most suitable LogAdapter instance (usually UniversalAdapter)
    """
    # UniversalAdapter handles everything - it's the future-proof choice
    return UniversalAdapter()


def detect_log_format(filepath: str) -> str:
    """
    Detect log format from file.
    
    Returns adapter name: 'universal', 'jsonl', 'apache', 'nginx', 'kubernetes', 'generic'
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [f.readline() for _ in range(20)]
        
        # Quick heuristic for reporting purposes
        samples = [l.strip() for l in lines if l.strip()][:5]
        if not samples:
            return "universal"
        
        # Check if JSON
        json_count = sum(1 for s in samples if s.startswith('{'))
        if json_count >= len(samples) // 2:
            return "jsonl"
        
        # Check for Apache format
        if any(re.search(r'\[\d{2}/\w{3}/\d{4}:', s) for s in samples):
            return "apache"
        
        # Check for Kubernetes
        if any('"kind"' in s or 'namespace' in s.lower() for s in samples):
            return "kubernetes"
        
        return "universal"
    except:
        return "universal"


def detect_data_type(lines: List[str]) -> Dict[str, Any]:
    """
    Detect whether data looks like logs vs a dataset.
    
    Returns:
        {
            "type": "logs" | "dataset" | "mixed" | "unknown",
            "confidence": 0.0-1.0,
            "signals": ["what made us think this"],
            "recommendation": "Use Log Observatory" | "Use Dataset Forensics"
        }
    """
    if not lines:
        return {"type": "unknown", "confidence": 0.0, "signals": [], "recommendation": "No data"}
    
    # Sample up to 100 lines
    samples = [l.strip() for l in lines[:100] if l.strip()]
    if not samples:
        return {"type": "unknown", "confidence": 0.0, "signals": [], "recommendation": "No data"}
    
    log_signals = []
    dataset_signals = []
    
    # === LOG SIGNALS ===
    
    # Timestamps in log format
    timestamp_patterns = [
        r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',  # ISO
        r'\[\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}',   # Apache
        r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}',     # Syslog
    ]
    timestamp_matches = sum(1 for s in samples 
                           for p in timestamp_patterns 
                           if re.search(p, s))
    if timestamp_matches > len(samples) * 0.3:
        log_signals.append(f"timestamps_found:{timestamp_matches}")
    
    # Log level indicators
    log_levels = r'\b(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL|TRACE)\b'
    level_matches = sum(1 for s in samples if re.search(log_levels, s, re.IGNORECASE))
    if level_matches > len(samples) * 0.2:
        log_signals.append(f"log_levels:{level_matches}")
    
    # Component patterns [component] or component:
    component_pattern = r'(\[[\w.-]+\]|^[\w.-]+:)'
    component_matches = sum(1 for s in samples if re.search(component_pattern, s))
    if component_matches > len(samples) * 0.2:
        log_signals.append(f"components:{component_matches}")
    
    # JSON with event-like keys
    event_keys = ['timestamp', 'time', 'ts', 'level', 'message', 'msg', 'component', 
                  'event', 'event_type', 'severity', 'logger', 'source']
    json_event_count = 0
    for s in samples:
        if s.startswith('{'):
            try:
                obj = json.loads(s)
                if any(k in obj for k in event_keys):
                    json_event_count += 1
            except:
                pass
    if json_event_count > len(samples) * 0.3:
        log_signals.append(f"json_events:{json_event_count}")
    
    # HTTP methods/status codes
    http_pattern = r'\b(GET|POST|PUT|DELETE|PATCH)\b|\s[1-5]\d{2}\s'
    http_matches = sum(1 for s in samples if re.search(http_pattern, s))
    if http_matches > len(samples) * 0.1:
        log_signals.append(f"http_traffic:{http_matches}")
    
    # === DATASET SIGNALS ===
    
    # CSV-like structure (consistent columns)
    if samples:
        first = samples[0]
        if ',' in first:
            comma_counts = [s.count(',') for s in samples[:10]]
            if len(set(comma_counts)) <= 2:  # Consistent column count
                dataset_signals.append(f"csv_structure:cols={comma_counts[0]+1}")
    
    # JSON with data-like keys (not event keys)
    data_keys = ['id', 'name', 'title', 'text', 'content', 'label', 'category',
                 'value', 'price', 'count', 'score', 'rating', 'description',
                 'user', 'author', 'url', 'image', 'date', 'created']
    json_data_count = 0
    for s in samples:
        if s.startswith('{'):
            try:
                obj = json.loads(s)
                # Data if has data keys but NOT event keys
                has_data = any(k in obj for k in data_keys)
                has_event = any(k in obj for k in event_keys)
                if has_data and not has_event:
                    json_data_count += 1
            except:
                pass
    if json_data_count > len(samples) * 0.3:
        dataset_signals.append(f"json_data:{json_data_count}")
    
    # Long text content (datasets often have text fields)
    long_text_count = sum(1 for s in samples if len(s) > 500)
    if long_text_count > len(samples) * 0.2:
        dataset_signals.append(f"long_text:{long_text_count}")
    
    # Numeric-heavy (datasets often have numbers)
    numeric_heavy = sum(1 for s in samples if len(re.findall(r'\d+\.?\d*', s)) > 5)
    if numeric_heavy > len(samples) * 0.5:
        dataset_signals.append(f"numeric_data:{numeric_heavy}")
    
    # === DECISION ===
    
    log_score = len(log_signals)
    data_score = len(dataset_signals)
    total = log_score + data_score
    
    if total == 0:
        return {
            "type": "unknown",
            "confidence": 0.3,
            "signals": ["no clear signals"],
            "recommendation": "Try both - Logs tab and Dataset tab"
        }
    
    if log_score > data_score * 2:
        return {
            "type": "logs",
            "confidence": min(log_score / 5, 1.0),
            "signals": log_signals,
            "recommendation": "Use Log Observatory (Observe tab)"
        }
    elif data_score > log_score * 2:
        return {
            "type": "dataset",
            "confidence": min(data_score / 4, 1.0),
            "signals": dataset_signals,
            "recommendation": "Use Dataset Forensics (Extract Ghost Log)"
        }
    else:
        return {
            "type": "mixed",
            "confidence": 0.5,
            "signals": log_signals + dataset_signals,
            "recommendation": "Data has both log and dataset characteristics - try Logs first"
        }

