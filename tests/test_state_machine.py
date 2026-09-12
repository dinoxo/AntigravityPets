"""Unit tests for PetStateMachine and Codex animation mappings."""

import time
import unittest

from core.state_machine import (
    PetState,
    PetStateMachine,
    ROW_TO_STATE,
    STATE_TO_ROW,
)
from ipc.protocol import EventPacket


class TestStateMachine(unittest.TestCase):
    """Test state transitions, row mappings, and transient timers."""

    def setUp(self) -> None:
        self.sm = PetStateMachine(initial_state=PetState.IDLE)

    def test_codex_row_mappings(self) -> None:
        """Verify state-to-row mapping matches Codex specifications."""
        expected_rows = {
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
        for state, row in expected_rows.items():
            self.assertEqual(STATE_TO_ROW[state], row)
            self.assertEqual(ROW_TO_STATE[row], state)

    def test_pre_invocation_transitions_to_working(self) -> None:
        packet = EventPacket(event="PreInvocation", timestamp=time.time())
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.WORKING)
        self.assertEqual(self.sm.current_row, 7)

    def test_pre_tool_use_transitions_to_working(self) -> None:
        packet = EventPacket(
            event="PreToolUse",
            timestamp=time.time(),
            tool="run_command",
        )
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.WORKING)
        self.assertEqual(self.sm.current_tool, "run_command")
        self.assertEqual(self.sm.current_row, 7)

    def test_post_tool_use_success_transitions_to_review(self) -> None:
        packet = EventPacket(
            event="PostToolUse",
            timestamp=time.time(),
            tool="run_command",
            error=None,
        )
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.REVIEW)
        self.assertEqual(self.sm.current_row, 8)

    def test_post_tool_use_error_transitions_to_failed(self) -> None:
        packet = EventPacket(
            event="PostToolUse",
            timestamp=time.time(),
            tool="run_command",
            error="Exit code 1: test assertion failed",
        )
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.FAILED)
        self.assertEqual(self.sm.last_error, "Exit code 1: test assertion failed")
        self.assertEqual(self.sm.current_row, 5)

    def test_post_invocation_transitions_to_waiting(self) -> None:
        packet = EventPacket(event="PostInvocation", timestamp=time.time())
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.WAITING)
        self.assertEqual(self.sm.current_row, 6)

    def test_stop_clean_transitions_to_jump(self) -> None:
        packet = EventPacket(event="Stop", timestamp=time.time(), error=None)
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.JUMP)
        self.assertEqual(self.sm.current_row, 3)

    def test_stop_error_transitions_to_failed(self) -> None:
        packet = EventPacket(
            event="Stop",
            timestamp=time.time(),
            error="Agent crashed",
        )
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_state, PetState.FAILED)
        self.assertEqual(self.sm.current_row, 5)

    def test_drag_handling(self) -> None:
        # Move left
        self.sm.handle_drag(-5.0, 0.0)
        self.assertEqual(self.sm.current_state, PetState.MOVE_LEFT)
        self.assertEqual(self.sm.current_row, 1)

        # Move right
        self.sm.handle_drag(8.0, 0.0)
        self.assertEqual(self.sm.current_state, PetState.MOVE_RIGHT)
        self.assertEqual(self.sm.current_row, 2)

        # Release drag
        self.sm.handle_drag_end()
        self.assertEqual(self.sm.current_state, PetState.IDLE)

    def test_state_change_callback(self) -> None:
        history = []

        def callback(new_s, old_s):
            history.append((new_s, old_s))

        self.sm.register_state_change_callback(callback)
        self.sm.set_state(PetState.WORKING, schedule_revert=False)
        self.sm.set_state(PetState.REVIEW, schedule_revert=False)

        self.assertEqual(
            history,
            [
                (PetState.WORKING, PetState.IDLE),
                (PetState.REVIEW, PetState.WORKING),
            ],
        )

    def test_transient_state_reversion(self) -> None:
        # Create machine with tiny transient duration for testing
        fast_sm = PetStateMachine(
            transient_durations={PetState.JUMP: 0.05}
        )
        fast_sm.set_state(PetState.JUMP, schedule_revert=True)
        self.assertEqual(fast_sm.current_state, PetState.JUMP)

        # Wait for timeout to trigger
        time.sleep(0.1)
        self.assertEqual(fast_sm.current_state, PetState.IDLE)

    def test_event_packet_title_and_detail(self) -> None:
        packet = EventPacket(
            event="PreToolUse",
            timestamp=time.time(),
            tool="run_command",
            title="Running Command",
            detail="npm test",
        )
        self.sm.process_event(packet)
        self.assertEqual(self.sm.current_title, "Running Command")
        self.assertEqual(self.sm.current_detail, "npm test")


if __name__ == "__main__":
    unittest.main()
