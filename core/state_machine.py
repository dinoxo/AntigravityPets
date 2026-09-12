"""Pet State Machine mapping Antigravity lifecycle events to animation rows."""

from enum import Enum
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from ipc.protocol import EventPacket

logger = logging.getLogger("AntigravityPets.StateMachine")


class PetState(str, Enum):
    """Core pet states corresponding to Codex spritesheet rows."""

    IDLE = "idle"  # Row 0: Default idling / breathing
    MOVE_LEFT = "move_left"  # Row 1: Dragged or moving left
    MOVE_RIGHT = "move_right"  # Row 2: Dragged or moving right
    JUMP = "jump"  # Row 3: Celebratory jump upon task success
    WAVE = "wave"  # Row 4: Farewell or greeting wave
    FAILED = "failed"  # Row 5: Tool failure, error, or test failed
    WAITING = "waiting"  # Row 6: Pausing, waiting for user response
    WORKING = "working"  # Row 7: Executing tool or model thinking
    REVIEW = "review"  # Row 8: Inspecting changes / verification
    COFFEE = "coffee"  # Row 9: Taking coffee


# Codex standard row indices
STATE_TO_ROW: Dict[PetState, int] = {
    PetState.IDLE: 0,
    PetState.MOVE_LEFT: 1,
    PetState.MOVE_RIGHT: 2,
    PetState.JUMP: 3,
    PetState.WAVE: 4,
    PetState.FAILED: 5,
    PetState.WAITING: 6,
    PetState.WORKING: 7,
    PetState.REVIEW: 8,
    PetState.COFFEE: 9,
}

ROW_TO_STATE: Dict[int, PetState] = {row: state for state, row in STATE_TO_ROW.items()}

# Default durations (in seconds) for transient states before reverting to IDLE
DEFAULT_TRANSIENT_DURATIONS: Dict[PetState, float] = {
    PetState.JUMP: 2.5,
    PetState.WAVE: 2.5,
    PetState.FAILED: 3.0,
    PetState.COFFEE: 3.5,
}


class PetStateMachine:
    """Manages pet animation states and processes agent lifecycle events."""

    def __init__(
        self,
        initial_state: PetState = PetState.IDLE,
        transient_durations: Optional[Dict[PetState, float]] = None,
    ) -> None:
        self._current_state: PetState = initial_state
        self._previous_state: PetState = initial_state
        self._lock = threading.Lock()
        self._transient_durations = transient_durations or dict(DEFAULT_TRANSIENT_DURATIONS)
        self._state_change_callbacks: List[Callable[[PetState, PetState], None]] = []
        self._timer: Optional[threading.Timer] = None
        self._current_tool: Optional[str] = None
        self._last_error: Optional[str] = None
        self._current_title: Optional[str] = None
        self._current_detail: Optional[str] = None

    @property
    def current_state(self) -> PetState:
        with self._lock:
            return self._current_state

    @property
    def current_row(self) -> int:
        return STATE_TO_ROW[self.current_state]

    @property
    def current_tool(self) -> Optional[str]:
        with self._lock:
            return self._current_tool

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    @property
    def current_title(self) -> Optional[str]:
        with self._lock:
            return self._current_title

    @property
    def current_detail(self) -> Optional[str]:
        with self._lock:
            return self._current_detail

    def register_state_change_callback(
        self, callback: Callable[[PetState, PetState], None]
    ) -> None:
        """Register a listener for state changes: callback(new_state, old_state)."""
        self._state_change_callbacks.append(callback)

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def set_state(self, new_state: PetState, schedule_revert: bool = True) -> None:
        """Explicitly transition to a new pet state."""
        old_state = self._current_state
        if old_state == new_state and self._timer is None:
            return

        self._cancel_timer()

        with self._lock:
            self._previous_state = self._current_state
            self._current_state = new_state

        logger.debug("State changed: %s -> %s", old_state.value, new_state.value)

        # Notify callbacks
        for cb in self._state_change_callbacks:
            try:
                cb(new_state, old_state)
            except Exception as e:
                logger.error("Error in state change callback: %s", e)

        # Check if new state is transient and schedule revert
        if schedule_revert and new_state in self._transient_durations:
            duration = self._transient_durations[new_state]
            self._timer = threading.Timer(duration, self._on_transient_timeout, args=[new_state])
            self._timer.daemon = True
            self._timer.start()

    def _on_transient_timeout(self, state_when_scheduled: PetState) -> None:
        """Callback when a transient state timer expires."""
        with self._lock:
            if self._current_state == state_when_scheduled:
                revert_to = PetState.IDLE
                self._current_title = None
                self._current_detail = None
            else:
                return
        self.set_state(revert_to, schedule_revert=False)

    def handle_drag(self, dx: float, dy: float) -> None:
        """Handle window drag vector."""
        if dx < -2:
            self.set_state(PetState.MOVE_LEFT, schedule_revert=False)
        elif dx > 2:
            self.set_state(PetState.MOVE_RIGHT, schedule_revert=False)

    def handle_drag_end(self) -> None:
        """Revert to idle or previous state when dragging concludes."""
        with self._lock:
            if self._current_state in (PetState.MOVE_LEFT, PetState.MOVE_RIGHT):
                target = self._previous_state if self._previous_state not in (
                    PetState.MOVE_LEFT,
                    PetState.MOVE_RIGHT,
                ) else PetState.IDLE
            else:
                return
        self.set_state(target, schedule_revert=False)

    def process_event(self, packet: EventPacket) -> PetState:
        """Process an Antigravity EventPacket and update state accordingly.

        Transition Rules:
        - PreInvocation -> WORKING
        - PreToolUse -> WORKING
        - PostToolUse:
            - If packet.error is present -> FAILED (transient)
            - If tool inspection / diff -> REVIEW
            - Otherwise -> REVIEW or WORKING
        - PostInvocation -> WAITING
        - Stop:
            - If packet.error -> FAILED
            - Otherwise -> JUMP (celebration transient) -> IDLE
        """
        event = packet.event

        with self._lock:
            self._current_tool = packet.tool
            if packet.error:
                self._last_error = packet.error
            if packet.title is not None:
                self._current_title = packet.title
            if packet.detail is not None:
                # Do not clobber rich tool details (commands, filenames) with generic completion text
                is_generic = packet.detail.endswith("completed") or packet.detail == "Processing step..."
                if not (event == "PostToolUse" and is_generic and self._current_detail):
                    self._current_detail = packet.detail

        if event in ("PreInvocation", "PreToolUse"):
            self.set_state(PetState.WORKING, schedule_revert=False)

        elif event == "PostToolUse":
            if packet.error:
                self.set_state(PetState.FAILED, schedule_revert=True)
            else:
                # Successful tool completion transitions to review
                self.set_state(PetState.REVIEW, schedule_revert=False)

        elif event == "PostInvocation":
            # Waiting for user input
            self.set_state(PetState.WAITING, schedule_revert=False)

        elif event == "Stop":
            if packet.error:
                self.set_state(PetState.FAILED, schedule_revert=True)
            else:
                # Celebratory jump on clean stop
                self.set_state(PetState.JUMP, schedule_revert=True)

        return self.current_state
