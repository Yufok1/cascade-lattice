"""
Live Document Tracer

Real-time streaming of document-centric provenance events.
This is the LIVE version of what the export system freezes.

Instead of:  Model runs → Process → Export frozen provenance
We do:       Model runs → STREAM events → View live document highlights

Same data model as the observer/exporter, just streamed in real-time
with document snippet context attached.

Usage:
    # Create observer with live streaming
    observer = DatasetObserver("my_pipeline")
    tracer = LiveDocumentTracer(observer)
    
    # Subscribe to events
    tracer.on_event(my_handler)
    
    # Or stream to async consumer
    async for event in tracer.stream():
        render_highlight(event)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple
from queue import Queue
from threading import Lock
from pathlib import Path


class TraceEventType(Enum):
    """Types of document trace events."""
    # Data flow events
    DOCUMENT_TOUCHED = "document_touched"      # Model accessed this document/record
    SPAN_HIGHLIGHTED = "span_highlighted"      # Specific text span being processed
    ASSOCIATION_CREATED = "association_created"  # Link between two spans/documents
    
    # Activity events
    ACTIVITY_STARTED = "activity_started"
    ACTIVITY_PROGRESS = "activity_progress"
    ACTIVITY_COMPLETED = "activity_completed"
    
    # Entity events
    ENTITY_CREATED = "entity_created"
    ENTITY_DERIVED = "entity_derived"
    
    # Relationship events
    LINK_CREATED = "link_created"


@dataclass
class DocumentSpan:
    """
    A span within a document being traced.
    
    This is the atomic unit of live visualization -
    the specific text/content the model is touching.
    """
    document_id: str           # Entity or record ID
    document_name: str         # Human-readable name
    field_name: str = ""       # Column/field if applicable
    row_index: int = -1        # Row if applicable
    
    # The actual content span
    text: str = ""             # The snippet text
    start_char: int = -1       # Start position in full text
    end_char: int = -1         # End position in full text
    
    # Visual hints
    highlight_type: str = "default"  # "source", "target", "match", "attention"
    confidence: float = 1.0    # For attention/relevance visualization
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "field_name": self.field_name,
            "row_index": self.row_index,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "highlight_type": self.highlight_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class DocumentAssociation:
    """
    An association between two document spans.
    
    Represents the model saying "this connects to that".
    """
    source: DocumentSpan
    target: DocumentSpan
    association_type: str = "related"  # "match", "derived", "similar", "references"
    confidence: float = 1.0
    
    # Why this association was made
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "association_type": self.association_type,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass
class TraceEvent:
    """
    A single trace event for live document visualization.
    
    This is what gets streamed to the UI in real-time.
    """
    event_type: TraceEventType
    timestamp: float = field(default_factory=time.time)
    
    # Activity context
    activity_id: Optional[str] = None
    activity_name: Optional[str] = None
    activity_type: Optional[str] = None
    
    # Document spans involved
    spans: List[DocumentSpan] = field(default_factory=list)
    
    # Association if this event creates one
    association: Optional[DocumentAssociation] = None
    
    # Progress for long operations
    progress: Optional[float] = None  # 0.0 to 1.0
    progress_message: Optional[str] = None
    
    # Raw provenance data (for export compatibility)
    entity_id: Optional[str] = None
    relationship_type: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "activity_id": self.activity_id,
            "activity_name": self.activity_name,
            "activity_type": self.activity_type,
            "spans": [s.to_dict() for s in self.spans],
            "association": self.association.to_dict() if self.association else None,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "entity_id": self.entity_id,
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class LiveDocumentTracer:
    """
    Real-time document tracing for live visualization.
    
    Hooks into DatasetObserver to stream events as they happen,
    enriched with document snippet context for visualization.
    
    This is the LIVE version of what CroissantExporter freezes.
    
    NEW: Now writes all events to a tape file (JSONL) for buffered playback!
    """
    
    def __init__(self, observer=None, buffer_size: int = 1000, log_dir: str = "./logs"):
        """
        Initialize tracer.
        
        Args:
            observer: DatasetObserver to hook into (optional)
            buffer_size: Max events to buffer for replay
            log_dir: Directory for tape files (JSONL logs)
        """
        self.observer = observer
        self.buffer_size = buffer_size
        
        # Event subscribers
        self._handlers: List[Callable[[TraceEvent], None]] = []
        self._async_handlers: List[Callable[[TraceEvent], Any]] = []
        
        # Event buffer for replay/late subscribers
        self._buffer: List[TraceEvent] = []
        self._buffer_lock = Lock()
        
        # Async queue for streaming
        self._async_queue: Optional[asyncio.Queue] = None
        
        # Current activity context
        self._current_activity_id: Optional[str] = None
        self._current_activity_name: Optional[str] = None
        self._current_activity_type: Optional[str] = None
        
        # Document context cache
        self._document_cache: Dict[str, Dict[str, Any]] = {}
        
        # === TAPE FILE FOR PLAYBACK ===
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = int(time.time())
        self._tape_path = self._log_dir / f"unity_tape_{self._session_id}.jsonl"
        self._tape_file = None
        self._tape_lock = Lock()
        self._event_count = 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_event(self, handler: Callable[[TraceEvent], None]):
        """Subscribe to trace events (sync handler)."""
        self._handlers.append(handler)
        return self  # Allow chaining
    
    def on_event_async(self, handler: Callable[[TraceEvent], Any]):
        """Subscribe to trace events (async handler)."""
        self._async_handlers.append(handler)
        return self
    
    def remove_handler(self, handler):
        """Unsubscribe a handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)
        if handler in self._async_handlers:
            self._async_handlers.remove(handler)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EVENT EMISSION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def emit(self, event: TraceEvent):
        """
        Emit a trace event to all subscribers.
        
        Called internally when provenance events occur.
        Also writes to tape file for buffered playback!
        """
        self._event_count += 1
        
        # Add to buffer
        with self._buffer_lock:
            self._buffer.append(event)
            if len(self._buffer) > self.buffer_size:
                self._buffer.pop(0)
        
        # === WRITE TO TAPE (JSONL) ===
        self._write_to_tape(event)
        
        # Call sync handlers
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Handler error: {e}")
        
        # Queue for async handlers
        if self._async_queue:
            try:
                self._async_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop if queue full
    
    def _write_to_tape(self, event: TraceEvent):
        """Write event to tape file for later playback."""
        try:
            with self._tape_lock:
                # Lazy open the file
                if self._tape_file is None:
                    self._tape_file = open(self._tape_path, "a", encoding="utf-8")
                    print(f"[CASCADE] 📼 Unity tape started: {self._tape_path}")
                
                # Build tape record with full context
                record = {
                    "seq": self._event_count,
                    "event": event.to_dict(),
                    "session_id": self._session_id,
                }
                
                json_line = json.dumps(record, default=str) + "\n"
                self._tape_file.write(json_line)
                self._tape_file.flush()
                
                # Debug: Log first few events
                if self._event_count <= 3:
                    print(f"[CASCADE] 📝 Wrote event {self._event_count} to tape: {event.event_type}")
        except Exception as e:
            # Don't let tape errors break the main flow
            print(f"[CASCADE] ⚠️ Tape write error: {e}")
            pass
    
    def _write_raw_to_tape(self, record: Dict[str, Any]):
        """Write a raw record to tape file (for docspace events)."""
        try:
            with self._tape_lock:
                # Lazy open the file
                if self._tape_file is None:
                    self._tape_file = open(self._tape_path, "a", encoding="utf-8")
                    print(f"[CASCADE] 📼 Unity tape started: {self._tape_path}")
                
                self._tape_file.write(json.dumps(record, default=str) + "\n")
                self._tape_file.flush()
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DOCUMENT SPACE EVENTS (for polling iframe)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def emit_entity(self, entity_id: str, source: str, text: str, index: int, side: str = "a"):
        """
        Emit an entity for Document Space visualization.
        
        Args:
            entity_id: Unique ID for the entity
            source: Source dataset name
            text: Preview text (truncated)
            index: Row index in dataset
            side: "a" or "b" to indicate which dataset
        """
        self._event_count += 1
        record = {
            "seq": self._event_count,
            "type": "docspace_entity",
            "side": side,
            "data": {
                "id": entity_id,
                "source": source,
                "text": text[:200],
                "index": index,
            },
            "session_id": self._session_id,
        }
        self._write_raw_to_tape(record)
    
    def emit_match(self, doc_a_id: str, doc_b_id: str, score: float):
        """
        Emit a match for Document Space visualization.
        
        Args:
            doc_a_id: ID of entity from dataset A
            doc_b_id: ID of entity from dataset B
            score: Similarity score (0-1)
        """
        self._event_count += 1
        record = {
            "seq": self._event_count,
            "type": "docspace_match",
            "data": {
                "docA": doc_a_id,
                "docB": doc_b_id,
                "score": float(score),
            },
            "session_id": self._session_id,
        }
        self._write_raw_to_tape(record)
    
    def emit_phase(self, phase: str, progress: float, message: str = ""):
        """
        Emit a phase update for Document Space.
        
        Args:
            phase: Current phase (embedding_a, embedding_b, comparing, complete)
            progress: Progress 0-1
            message: Status message
        """
        self._event_count += 1
        record = {
            "seq": self._event_count,
            "type": "docspace_phase",
            "data": {
                "phase": phase,
                "progress": float(progress),
                "message": message,
            },
            "session_id": self._session_id,
        }
        self._write_raw_to_tape(record)
    
    def close_tape(self):
        """Close the tape file (call when session ends)."""
        with self._tape_lock:
            if self._tape_file:
                self._tape_file.close()
                self._tape_file = None
                print(f"[CASCADE] 📼 Unity tape closed: {self._event_count} events → {self._tape_path}")
    
    def get_tape_path(self) -> Optional[Path]:
        """Get the path to the current tape file (whether open or not)."""
        return self._tape_path
    
    @staticmethod
    def load_tape(tape_path: str) -> List[Dict[str, Any]]:
        """
        Load events from a tape file for playback.
        
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
    
    async def stream(self) -> Generator[TraceEvent, None, None]:
        """
        Async generator for streaming events.
        
        Usage:
            async for event in tracer.stream():
                await render(event)
        """
        self._async_queue = asyncio.Queue(maxsize=self.buffer_size)
        
        # Replay buffer first
        with self._buffer_lock:
            for event in self._buffer:
                yield event
        
        # Then stream new events
        while True:
            event = await self._async_queue.get()
            yield event
    
    def get_buffer(self) -> List[TraceEvent]:
        """Get buffered events for replay."""
        with self._buffer_lock:
            return list(self._buffer)
    
    def clear_buffer(self):
        """Clear the event buffer."""
        with self._buffer_lock:
            self._buffer.clear()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRACING API - Call these to emit events
    # ═══════════════════════════════════════════════════════════════════════════
    
    def start_activity(
        self,
        activity_id: str,
        activity_name: str,
        activity_type: str = "transform",
    ):
        """Signal start of an activity (for context)."""
        self._current_activity_id = activity_id
        self._current_activity_name = activity_name
        self._current_activity_type = activity_type
        
        self.emit(TraceEvent(
            event_type=TraceEventType.ACTIVITY_STARTED,
            activity_id=activity_id,
            activity_name=activity_name,
            activity_type=activity_type,
        ))
    
    def end_activity(self, activity_id: str = None):
        """Signal end of an activity."""
        self.emit(TraceEvent(
            event_type=TraceEventType.ACTIVITY_COMPLETED,
            activity_id=activity_id or self._current_activity_id,
            activity_name=self._current_activity_name,
            activity_type=self._current_activity_type,
        ))
        self._current_activity_id = None
        self._current_activity_name = None
        self._current_activity_type = None
    
    def report_progress(
        self,
        progress: float,
        message: str = "",
        activity_id: str = None,
    ):
        """Report progress on current activity."""
        self.emit(TraceEvent(
            event_type=TraceEventType.ACTIVITY_PROGRESS,
            activity_id=activity_id or self._current_activity_id,
            activity_name=self._current_activity_name,
            progress=progress,
            progress_message=message,
        ))
    
    def touch_document(
        self,
        document_id: str,
        document_name: str,
        snippet: str = "",
        field_name: str = "",
        row_index: int = -1,
        highlight_type: str = "default",
        confidence: float = 1.0,
        **metadata,
    ):
        """
        Signal that the model touched a document/record.
        
        This creates a highlight in the live view.
        """
        span = DocumentSpan(
            document_id=document_id,
            document_name=document_name,
            field_name=field_name,
            row_index=row_index,
            text=snippet,
            highlight_type=highlight_type,
            confidence=confidence,
            metadata=metadata,
        )
        
        self.emit(TraceEvent(
            event_type=TraceEventType.DOCUMENT_TOUCHED,
            activity_id=self._current_activity_id,
            activity_name=self._current_activity_name,
            activity_type=self._current_activity_type,
            spans=[span],
            entity_id=document_id,
            metadata=metadata,
        ))
        
        return span
    
    def highlight_span(
        self,
        document_id: str,
        document_name: str,
        text: str,
        start_char: int = -1,
        end_char: int = -1,
        field_name: str = "",
        row_index: int = -1,
        highlight_type: str = "attention",
        confidence: float = 1.0,
        **metadata,
    ):
        """
        Highlight a specific span within a document.
        
        For showing exactly where in the text the model is focusing.
        """
        span = DocumentSpan(
            document_id=document_id,
            document_name=document_name,
            field_name=field_name,
            row_index=row_index,
            text=text,
            start_char=start_char,
            end_char=end_char,
            highlight_type=highlight_type,
            confidence=confidence,
            metadata=metadata,
        )
        
        self.emit(TraceEvent(
            event_type=TraceEventType.SPAN_HIGHLIGHTED,
            activity_id=self._current_activity_id,
            activity_name=self._current_activity_name,
            activity_type=self._current_activity_type,
            spans=[span],
            metadata=metadata,
        ))
        
        return span
    
    def create_association(
        self,
        source_doc_id: str,
        source_doc_name: str,
        source_text: str,
        target_doc_id: str,
        target_doc_name: str,
        target_text: str,
        association_type: str = "related",
        confidence: float = 1.0,
        reason: str = "",
        **metadata,
    ):
        """
        Create an association between two document spans.
        
        This is the "A connects to B" visualization.
        """
        source = DocumentSpan(
            document_id=source_doc_id,
            document_name=source_doc_name,
            text=source_text,
            highlight_type="source",
            confidence=confidence,
        )
        
        target = DocumentSpan(
            document_id=target_doc_id,
            document_name=target_doc_name,
            text=target_text,
            highlight_type="target",
            confidence=confidence,
        )
        
        association = DocumentAssociation(
            source=source,
            target=target,
            association_type=association_type,
            confidence=confidence,
            reason=reason,
        )
        
        self.emit(TraceEvent(
            event_type=TraceEventType.ASSOCIATION_CREATED,
            activity_id=self._current_activity_id,
            activity_name=self._current_activity_name,
            activity_type=self._current_activity_type,
            spans=[source, target],
            association=association,
            metadata=metadata,
        ))
        
        return association
    
    def entity_created(
        self,
        entity_id: str,
        entity_name: str,
        record_count: int = None,
        **metadata,
    ):
        """Signal that a new entity was created in provenance."""
        self.emit(TraceEvent(
            event_type=TraceEventType.ENTITY_CREATED,
            activity_id=self._current_activity_id,
            activity_name=self._current_activity_name,
            entity_id=entity_id,
            metadata={"name": entity_name, "record_count": record_count, **metadata},
        ))
    
    def entity_derived(
        self,
        derived_id: str,
        derived_name: str,
        source_ids: List[str],
        **metadata,
    ):
        """Signal that an entity was derived from others."""
        self.emit(TraceEvent(
            event_type=TraceEventType.ENTITY_DERIVED,
            activity_id=self._current_activity_id,
            activity_name=self._current_activity_name,
            entity_id=derived_id,
            metadata={"name": derived_name, "sources": source_ids, **metadata},
        ))
    
    def link_created(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        **metadata,
    ):
        """Signal that a provenance link was created."""
        self.emit(TraceEvent(
            event_type=TraceEventType.LINK_CREATED,
            activity_id=self._current_activity_id,
            activity_name=self._current_activity_name,
            relationship_type=relationship_type,
            metadata={"source": source_id, "target": target_id, **metadata},
        ))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORT (Freeze the live state)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def export_session(self) -> Dict[str, Any]:
        """
        Export the trace session as frozen data.
        
        This is the bridge between live and export -
        same data, just frozen at a point in time.
        """
        with self._buffer_lock:
            return {
                "events": [e.to_dict() for e in self._buffer],
                "event_count": len(self._buffer),
                "exported_at": time.time(),
            }
    
    def export_associations(self) -> List[Dict[str, Any]]:
        """Export just the associations for visualization."""
        associations = []
        with self._buffer_lock:
            for event in self._buffer:
                if event.association:
                    associations.append(event.association.to_dict())
        return associations
    
    def export_timeline(self) -> List[Dict[str, Any]]:
        """Export events as a timeline."""
        timeline = []
        with self._buffer_lock:
            for event in self._buffer:
                timeline.append({
                    "timestamp": event.timestamp,
                    "type": event.event_type.value,
                    "activity": event.activity_name,
                    "spans": len(event.spans),
                    "has_association": event.association is not None,
                })
        return timeline


# ═══════════════════════════════════════════════════════════════════════════════
# CONSOLE RENDERER - Simple text-based live view
# ═══════════════════════════════════════════════════════════════════════════════

class ConsoleTraceRenderer:
    """
    Simple console renderer for live document traces.
    
    Good for debugging and terminal-based workflows.
    """
    
    def __init__(self, show_snippets: bool = True, max_snippet_len: int = 80):
        self.show_snippets = show_snippets
        self.max_snippet_len = max_snippet_len
    
    def render(self, event: TraceEvent):
        """Render event to console."""
        timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        
        if event.event_type == TraceEventType.ACTIVITY_STARTED:
            print(f"\n[{timestamp}] ▶ {event.activity_name} ({event.activity_type})")
            print("─" * 60)
        
        elif event.event_type == TraceEventType.ACTIVITY_COMPLETED:
            print("─" * 60)
            print(f"[{timestamp}] ✓ {event.activity_name} completed")
        
        elif event.event_type == TraceEventType.ACTIVITY_PROGRESS:
            pct = int((event.progress or 0) * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            msg = event.progress_message or ""
            print(f"\r[{timestamp}] [{bar}] {pct}% {msg}", end="", flush=True)
            if pct >= 100:
                print()
        
        elif event.event_type == TraceEventType.DOCUMENT_TOUCHED:
            for span in event.spans:
                snippet = self._truncate(span.text)
                print(f"[{timestamp}]   📄 {span.document_name}", end="")
                if span.field_name:
                    print(f"[{span.field_name}]", end="")
                if span.row_index >= 0:
                    print(f" row={span.row_index}", end="")
                if self.show_snippets and snippet:
                    print(f"\n            └─ \"{snippet}\"")
                else:
                    print()
        
        elif event.event_type == TraceEventType.SPAN_HIGHLIGHTED:
            for span in event.spans:
                snippet = self._truncate(span.text)
                conf = f"{span.confidence:.0%}" if span.confidence < 1.0 else ""
                print(f"[{timestamp}]   🔍 [{span.highlight_type}] {conf}")
                if self.show_snippets and snippet:
                    print(f"            └─ \"{snippet}\"")
        
        elif event.event_type == TraceEventType.ASSOCIATION_CREATED:
            assoc = event.association
            if assoc:
                src = self._truncate(assoc.source.text, 40)
                tgt = self._truncate(assoc.target.text, 40)
                print(f"[{timestamp}]   🔗 {assoc.association_type} ({assoc.confidence:.0%})")
                print(f"            ├─ \"{src}\"")
                print(f"            └─ \"{tgt}\"")
                if assoc.reason:
                    print(f"            ({assoc.reason})")
        
        elif event.event_type == TraceEventType.ENTITY_CREATED:
            name = event.metadata.get("name", event.entity_id)
            count = event.metadata.get("record_count", "?")
            print(f"[{timestamp}]   ✦ Entity created: {name} ({count} records)")
        
        elif event.event_type == TraceEventType.ENTITY_DERIVED:
            name = event.metadata.get("name", event.entity_id)
            sources = event.metadata.get("sources", [])
            print(f"[{timestamp}]   ⤵ Entity derived: {name} ← {len(sources)} sources")
    
    def _truncate(self, text: str, max_len: int = None) -> str:
        max_len = max_len or self.max_snippet_len
        if not text:
            return ""
        text = text.replace("\n", " ").strip()
        if len(text) > max_len:
            return text[:max_len-3] + "..."
        return text


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE
# ═══════════════════════════════════════════════════════════════════════════════

def create_live_tracer(observer=None, console: bool = False) -> LiveDocumentTracer:
    """
    Create a live document tracer.
    
    Args:
        observer: DatasetObserver to hook into
        console: If True, attach console renderer
    
    Returns:
        Configured LiveDocumentTracer
    """
    tracer = LiveDocumentTracer(observer)
    
    if console:
        renderer = ConsoleTraceRenderer()
        tracer.on_event(renderer.render)
    
    return tracer
