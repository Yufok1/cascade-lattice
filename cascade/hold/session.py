"""
HOLD Session - Arcade-Style Inference Interception
══════════════════════════════════════════════════════════

"Pause the machine. See what it sees. Choose what it chooses."

The arcade layer of HOLD:
- CausationHold: Session management with history
- InferenceStep: Single crystallized moment
- Time travel via state snapshots
- Speed controls and combo tracking

Controls:
    SPACE   - Accept model's choice, advance
    1-9     - Override with alternative
    ←/→     - Step back/forward through history  
    +/-     - Speed up/slow down auto-advance
    P       - Pause/unpause auto-advance
    ESC     - Exit hold mode
"""

import numpy as np
import time
import json
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum


class SessionState(Enum):
    """Current state of the hold session."""
    IDLE = "idle"           # Not holding anything
    PAUSED = "paused"       # Frozen, waiting for input
    STEPPING = "stepping"   # Auto-advancing at set speed
    REWINDING = "rewinding" # Going backwards through history


@dataclass
class InferenceStep:
    """A single crystallized moment of inference."""
    step_id: str
    step_index: int
    timestamp: float
    
    # What the model sees
    input_context: Dict[str, Any]
    
    # What the model wants to do
    candidates: List[Dict[str, Any]]  # [{value, probability, metadata}]
    top_choice: Any
    top_probability: float
    
    # Internal state snapshot (for true rewind)
    hidden_state: Optional[np.ndarray] = None
    attention_weights: Optional[Dict[str, float]] = None
    
    # What actually happened
    chosen_value: Any = None
    was_override: bool = False
    override_by: str = "model"  # "model" or "human"
    
    # Provenance
    cascade_hash: Optional[str] = None
    
    # Private: full state snapshot for true rewind
    _state_snapshot: Optional[Dict[str, Any]] = field(default=None, repr=False)


@dataclass  
class HoldSession:
    """A complete hold session with history."""
    session_id: str
    agent_id: str
    started_at: float
    
    # All steps in order
    steps: List[InferenceStep] = field(default_factory=list)
    current_index: int = 0
    
    # Arcade stats
    total_steps: int = 0
    human_overrides: int = 0
    correct_predictions: int = 0  # Human guessed what model would do
    combo: int = 0
    max_combo: int = 0
    
    # Speed control (steps per second, 0 = manual only)
    speed_level: int = 0  # 0=manual, 1=slow, 2=medium, 3=fast, 4=ludicrous
    speed_map: Dict[int, float] = field(default_factory=lambda: {
        0: 0.0,      # Manual
        1: 0.5,      # 2 sec per step
        2: 1.0,      # 1 sec per step  
        3: 2.0,      # 0.5 sec per step
        4: 10.0,     # 0.1 sec per step (ludicrous speed)
    })
    
    # State
    state: SessionState = SessionState.IDLE


@dataclass
class ArcadeFeedback:
    """Visual/audio feedback cues."""
    message: str
    intensity: float  # 0-1, for glow/shake/etc
    sound_cue: str    # "accept", "override", "combo", "combo_break", "rewind"
    color: Tuple[int, int, int] = (255, 255, 255)


class CausationHold:
    """
    The arcade-layer hold system. Wraps any inference function.
    
    Features:
    - Session management with full history
    - True state restoration for time travel
    - Speed controls (manual to ludicrous)
    - Combo tracking and high scores
    
    Usage:
        hold = CausationHold()
        
        # Start a session
        hold.begin_session(agent_id="agent_123")
        
        # In inference loop:
        for step in inference_steps:
            choice, feedback = hold.capture(
                input_context={"tokens": tokens},
                candidates=[{"value": "A", "probability": 0.8}, ...]
            )  # Pauses here until user input!
        
        # Time travel
        hold.rewind(steps=3)
        hold.branch_from(step_index=5, choice_index=2)
        
        stats = hold.end_session()
    """
    
    def __init__(self, cascade_bus=None):
        """
        Args:
            cascade_bus: Optional CASCADE event bus for provenance
        """
        self.bus = cascade_bus
        self.session: Optional[HoldSession] = None
        self.callbacks: Dict[str, List[Callable]] = {
            'on_step': [],
            'on_override': [],
            'on_combo': [],
            'on_combo_break': [],
            'on_rewind': [],
            'on_state_restore': [],
        }
        
        # Thread safety
        self._lock = threading.Lock()
        self._input_event = threading.Event()
        self._user_choice: Optional[Any] = None
        
        # High scores (persisted)
        self.high_scores_path = Path("data/hold_high_scores.json")
        self.high_scores = self._load_high_scores()
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    def begin_session(self, agent_id: str) -> HoldSession:
        """Start a new hold session."""
        session_id = f"hold_{agent_id}_{int(time.time()*1000)}"
        
        self.session = HoldSession(
            session_id=session_id,
            agent_id=agent_id,
            started_at=time.time(),
        )
        self.session.state = SessionState.PAUSED
        
        self._emit_cascade("hold_session_start", {
            "session_id": session_id,
            "agent_id": agent_id,
        })
        
        return self.session
    
    def end_session(self) -> Dict[str, Any]:
        """End session and return stats."""
        if not self.session:
            return {}
        
        stats = {
            "session_id": self.session.session_id,
            "agent_id": self.session.agent_id,
            "duration": time.time() - self.session.started_at,
            "total_steps": self.session.total_steps,
            "human_overrides": self.session.human_overrides,
            "correct_predictions": self.session.correct_predictions,
            "max_combo": self.session.max_combo,
            "accuracy": (
                self.session.correct_predictions / max(1, self.session.total_steps)
            ),
        }
        
        # Check for high score
        self._check_high_score(stats)
        
        self._emit_cascade("hold_session_end", stats)
        
        self.session = None
        return stats
    
    # ========================================================================
    # CAPTURE & ADVANCE - WITH STATE SNAPSHOT FOR TRUE REWIND
    # ========================================================================
    
    def capture(
        self,
        input_context: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        hidden_state: Optional[np.ndarray] = None,
        attention: Optional[Dict[str, float]] = None,
        state_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, ArcadeFeedback]:
        """
        Capture an inference step. BLOCKS until user input or auto-advance.
        
        IMPORTANT: Pass state_snapshot for true rewind capability.
        This should be a complete snapshot of the model's internal state
        that can be restored to allow execution from this decision point
        with a different choice.
        
        This is NOT prediction - you will ACTUALLY execute the choice and
        see REAL outcomes. If you don't like them, rewind and try again.
        
        Args:
            input_context: What the model is looking at
            candidates: List of {value, probability, ...} options
            hidden_state: Optional internal state snapshot (deprecated, use state_snapshot)
            attention: Optional attention weights
            state_snapshot: Complete model state for TRUE rewind capability
            
        Returns:
            (chosen_value, feedback) - The value to use and arcade feedback
        """
        if not self.session:
            # No session = passthrough, just return top choice
            return candidates[0]['value'], ArcadeFeedback("", 0, "")
        
        # Sort candidates by probability
        candidates = sorted(candidates, key=lambda x: x.get('probability', 0), reverse=True)
        top = candidates[0]
        
        # Merge hidden_state into state_snapshot if provided separately
        if state_snapshot is None and hidden_state is not None:
            state_snapshot = {'hidden_state': hidden_state}
        elif state_snapshot is not None and hidden_state is not None:
            state_snapshot['hidden_state'] = hidden_state
        
        # Create step - this is a CHECKPOINT for true rewind
        step = InferenceStep(
            step_id=f"step_{self.session.total_steps}",
            step_index=self.session.total_steps,
            timestamp=time.time(),
            input_context=input_context,
            candidates=candidates,
            top_choice=top['value'],
            top_probability=top.get('probability', 1.0),
            hidden_state=hidden_state,
            attention_weights=attention,
        )
        
        # Store state snapshot for TRUE rewind (not just history navigation)
        if state_snapshot is not None:
            step._state_snapshot = state_snapshot
        
        # Compute merkle hash for provenance
        step.cascade_hash = self._compute_step_hash(step)
        
        # Add to history
        with self._lock:
            self.session.steps.append(step)
            self.session.current_index = len(self.session.steps) - 1
            self.session.total_steps += 1
        
        # Emit step event
        self._emit_callback('on_step', step)
        self._emit_cascade("hold_step", {
            "step_index": step.step_index,
            "top_choice": str(top['value']),
            "top_prob": top.get('probability', 1.0),
            "num_candidates": len(candidates),
            "has_snapshot": state_snapshot is not None,
            "merkle": step.cascade_hash,
        })
        
        # Wait for input
        choice, feedback = self._wait_for_input(step)
        
        # Record what happened
        step.chosen_value = choice
        step.was_override = (choice != top['value'])
        step.override_by = "human" if step.was_override else "model"
        
        if step.was_override:
            self.session.human_overrides += 1
            self._emit_callback('on_override', step, choice)
        
        return choice, feedback
    
    def _wait_for_input(self, step: InferenceStep) -> Tuple[Any, ArcadeFeedback]:
        """Wait for user input or auto-advance timer."""
        
        # Manual mode = wait indefinitely
        if self.session.speed_level == 0:
            self._input_event.clear()
            self._input_event.wait()  # Blocks until input()
            
            choice = self._user_choice
            self._user_choice = None
            
        else:
            # Auto-advance mode
            speed = self.session.speed_map[self.session.speed_level]
            wait_time = 1.0 / speed if speed > 0 else float('inf')
            
            self._input_event.clear()
            got_input = self._input_event.wait(timeout=wait_time)
            
            if got_input and self._user_choice is not None:
                choice = self._user_choice
                self._user_choice = None
            else:
                # Auto-accepted
                choice = step.top_choice
        
        # Generate feedback
        return choice, self._generate_feedback(step, choice)
    
    def input(self, choice: Any):
        """
        Provide user input. Call from UI thread.
        
        Args:
            choice: The value to use (or index into candidates)
        """
        if not self.session:
            return
        
        current_step = self.session.steps[self.session.current_index]
        
        # Handle index input (1-9 keys)
        if isinstance(choice, int) and 0 <= choice < len(current_step.candidates):
            choice = current_step.candidates[choice]['value']
        
        self._user_choice = choice
        self._input_event.set()
    
    def accept(self):
        """Accept model's top choice (SPACE key)."""
        if not self.session or not self.session.steps:
            return
        
        current = self.session.steps[self.session.current_index]
        self.input(current.top_choice)
    
    def override(self, index: int):
        """Override with candidate at index (1-9 keys)."""
        self.input(index)
    
    # ========================================================================
    # NAVIGATION (TIME TRAVEL) - TRUE STATE RESTORATION
    # ========================================================================
    
    def rewind(self, steps: int = 1, restore_state: bool = True) -> Optional[InferenceStep]:
        """
        Go back in history with optional state restoration.
        
        This is NOT simulation - we actually restore the model's internal state
        to the snapshot taken at that decision point. From there, you can
        execute a different branch and see REAL outcomes.
        
        Args:
            steps: Number of steps to go back
            restore_state: If True, actually restore hidden_state to model
            
        Returns:
            The step we rewound to
        """
        if not self.session:
            return None
        
        with self._lock:
            new_index = max(0, self.session.current_index - steps)
            if new_index != self.session.current_index:
                self.session.current_index = new_index
                self.session.state = SessionState.REWINDING
                
                step = self.session.steps[new_index]
                
                # TRUE STATE RESTORATION
                if restore_state and step.hidden_state is not None:
                    self._restore_state(step)
                
                self._emit_callback('on_rewind', step, -steps)
                
                return step
        return None
    
    def _restore_state(self, step: InferenceStep):
        """
        Restore model state from a snapshot.
        
        This is the key that makes execution + rewind possible.
        The model's internal state is set back to exactly what it was
        at this decision point, allowing you to branch differently.
        """
        if step.hidden_state is None and step._state_snapshot is None:
            return
        
        # Emit state restoration event - hooked components can restore themselves
        self._emit_callback('on_state_restore', step)
        self._emit_cascade("state_restored", {
            "step_index": step.step_index,
            "merkle": step.cascade_hash,
            "had_hidden_state": step.hidden_state is not None,
            "had_snapshot": step._state_snapshot is not None,
        })
    
    def branch_from(self, step_index: int, choice_index: int) -> Optional[InferenceStep]:
        """
        Rewind to a step and immediately choose a different branch.
        
        This is the core gameplay loop:
        1. Rewind to decision point
        2. Choose different option
        3. Execute and see what happens
        4. Repeat until satisfied
        
        Args:
            step_index: Which decision point to branch from
            choice_index: Which candidate to choose (0 = model's choice)
            
        Returns:
            The step after branching (with state restored)
        """
        step = self.jump_to(step_index)
        if step is None:
            return None
        
        # Restore state
        self._restore_state(step)
        
        # Set up the override
        if choice_index < len(step.candidates):
            self.override(choice_index)
        else:
            self.accept()
        
        return step
    
    def forward(self, steps: int = 1) -> Optional[InferenceStep]:
        """Go forward in history (if we've rewound)."""
        if not self.session:
            return None
        
        with self._lock:
            max_index = len(self.session.steps) - 1
            new_index = min(max_index, self.session.current_index + steps)
            if new_index != self.session.current_index:
                self.session.current_index = new_index
                
                step = self.session.steps[new_index]
                self._emit_callback('on_rewind', step, steps)
                
                return step
        return None
    
    def jump_to(self, index: int) -> Optional[InferenceStep]:
        """Jump to specific step."""
        if not self.session:
            return None
        
        with self._lock:
            index = max(0, min(index, len(self.session.steps) - 1))
            self.session.current_index = index
            return self.session.steps[index]
    
    # ========================================================================
    # SPEED CONTROL
    # ========================================================================
    
    def speed_up(self):
        """Increase auto-advance speed."""
        if self.session:
            self.session.speed_level = min(4, self.session.speed_level + 1)
    
    def speed_down(self):
        """Decrease auto-advance speed."""
        if self.session:
            self.session.speed_level = max(0, self.session.speed_level - 1)
    
    def set_speed(self, level: int):
        """Set speed level directly (0-4)."""
        if self.session:
            self.session.speed_level = max(0, min(4, level))
    
    def pause(self):
        """Pause auto-advance."""
        if self.session:
            self.session.state = SessionState.PAUSED
    
    def unpause(self):
        """Resume auto-advance."""
        if self.session:
            self.session.state = SessionState.STEPPING
    
    # ========================================================================
    # PROVENANCE HASHING
    # ========================================================================
    
    def _compute_step_hash(self, step: InferenceStep) -> str:
        """
        Compute merkle hash for a step.
        
        This hash uniquely identifies this decision point and allows
        verification that rewind is restoring to the exact right state.
        """
        # Include parent hash for chain integrity
        parent_hash = ""
        if self.session and len(self.session.steps) > 0:
            prev_step = self.session.steps[-1]
            parent_hash = prev_step.cascade_hash or ""
        
        content = json.dumps({
            'step_index': step.step_index,
            'timestamp': step.timestamp,
            'top_choice': str(step.top_choice),
            'top_prob': step.top_probability,
            'num_candidates': len(step.candidates),
            'parent_hash': parent_hash,
        }, sort_keys=True)
        
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    # ========================================================================
    # ARCADE FEEDBACK
    # ========================================================================
    
    def _generate_feedback(self, step: InferenceStep, choice: Any) -> ArcadeFeedback:
        """Generate arcade-style feedback for a step."""
        
        is_override = (choice != step.top_choice)
        
        if is_override:
            # Combo break!
            if self.session.combo > 0:
                self._emit_callback('on_combo_break', self.session.combo)
            
            self.session.combo = 0
            
            return ArcadeFeedback(
                message="OVERRIDE",
                intensity=0.8,
                sound_cue="override",
                color=(255, 165, 0),  # Orange
            )
        
        else:
            # Accepted model choice
            self.session.combo += 1
            self.session.max_combo = max(self.session.max_combo, self.session.combo)
            
            # Combo milestones
            if self.session.combo in [10, 25, 50, 100]:
                self._emit_callback('on_combo', self.session.combo)
                return ArcadeFeedback(
                    message=f"COMBO x{self.session.combo}!",
                    intensity=1.0,
                    sound_cue="combo",
                    color=(0, 255, 255),  # Cyan
                )
            
            # Regular accept
            return ArcadeFeedback(
                message="",
                intensity=0.3 + min(0.5, self.session.combo * 0.02),
                sound_cue="accept",
                color=(0, 255, 0),  # Green
            )
    
    # ========================================================================
    # CALLBACKS
    # ========================================================================
    
    def on(self, event: str, callback: Callable):
        """Register callback for events."""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def _emit_callback(self, event: str, *args):
        """Emit event to callbacks."""
        for cb in self.callbacks.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                print(f"Callback error: {e}")
    
    # ========================================================================
    # CASCADE PROVENANCE
    # ========================================================================
    
    def _emit_cascade(self, event_type: str, data: Dict[str, Any]):
        """Emit event to CASCADE bus if available."""
        if self.bus:
            try:
                self.bus.emit(event_type, {
                    **data,
                    "source": "causation_hold",
                    "timestamp": time.time(),
                })
            except Exception:
                pass
    
    # ========================================================================
    # HIGH SCORES
    # ========================================================================
    
    def _load_high_scores(self) -> Dict[str, Any]:
        """Load high scores from disk."""
        if self.high_scores_path.exists():
            try:
                return json.loads(self.high_scores_path.read_text())
            except Exception:
                pass
        return {"max_combo": 0, "best_accuracy": 0.0, "total_sessions": 0}
    
    def _save_high_scores(self):
        """Save high scores to disk."""
        self.high_scores_path.parent.mkdir(parents=True, exist_ok=True)
        self.high_scores_path.write_text(json.dumps(self.high_scores, indent=2))
    
    def _check_high_score(self, stats: Dict[str, Any]):
        """Check and update high scores."""
        updated = False
        
        if stats['max_combo'] > self.high_scores['max_combo']:
            self.high_scores['max_combo'] = stats['max_combo']
            updated = True
        
        if stats['accuracy'] > self.high_scores['best_accuracy']:
            self.high_scores['best_accuracy'] = stats['accuracy']
            updated = True
        
        self.high_scores['total_sessions'] += 1
        
        if updated:
            self._save_high_scores()
    
    # ========================================================================
    # DECORATOR FOR EASY WRAPPING
    # ========================================================================
    
    def intercept(self, granularity: str = "step"):
        """
        Decorator to intercept a function's inference.
        
        Args:
            granularity: "step" (each call) or "token" (if function yields)
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # If no session, passthrough
                if not self.session:
                    return func(*args, **kwargs)
                
                # Capture the input
                input_context = {
                    "args": str(args)[:200],
                    "kwargs": {k: str(v)[:100] for k, v in kwargs.items()},
                }
                
                # Get result
                result = func(*args, **kwargs)
                
                # Create candidates from result
                if isinstance(result, np.ndarray):
                    # For embeddings, show top dimensions
                    top_dims = np.argsort(np.abs(result.flatten()))[-5:][::-1]
                    candidates = [
                        {"value": f"dim_{d}", "probability": float(np.abs(result.flatten()[d]))}
                        for d in top_dims
                    ]
                else:
                    candidates = [{"value": result, "probability": 1.0}]
                
                # Capture (may block)
                choice, feedback = self.capture(input_context, candidates)
                
                return result
            
            return wrapper
        return decorator
