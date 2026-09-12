"""Unit tests for Antigravity Pets new features suite."""

import time
import unittest

from core.features import (
    ActionHistory,
    ActionRecord,
    ArchitectureWisdom,
    GitMonitor,
    PhysicsEngine,
    PomodoroManager,
    WatchdogTimer,
)
from core.state_machine import PetState, PetStateMachine
from ipc.protocol import EventPacket


class TestActionHistory(unittest.TestCase):
    """Test the ring buffer action history."""

    def test_add_and_get_recent(self) -> None:
        hist = ActionHistory(max_entries=5)
        hist.add("PreToolUse", "run_command", "Running", "npm test")
        hist.add("PostToolUse", "run_command", "Reviewing", "npm test completed")
        hist.add("PreInvocation", None, "Thinking", "planning", is_secret=True)

        recent = hist.get_recent(2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0].title, "Thinking")
        self.assertTrue(recent[0].is_secret)
        self.assertEqual(recent[1].title, "Reviewing")

    def test_max_entries_overflow(self) -> None:
        hist = ActionHistory(max_entries=3)
        for i in range(10):
            hist.add("PreToolUse", "run_command", f"Step {i}", f"cmd {i}")
        recent = hist.get_recent(5)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0].title, "Step 9")


class TestWatchdogTimer(unittest.TestCase):
    """Test watchdog task hang detection."""

    def test_timeout_fires(self) -> None:
        timed_out = []

        def on_timeout(task: str, elapsed: float) -> None:
            timed_out.append((task, elapsed))

        wd = WatchdogTimer(timeout_seconds=0.05, on_timeout=on_timeout)
        wd.task_started("Heavy Build")
        time.sleep(0.08)

        self.assertEqual(len(timed_out), 1)
        self.assertEqual(timed_out[0][0], "Heavy Build")
        self.assertGreater(timed_out[0][1], 0.04)

    def test_completion_cancels_timeout(self) -> None:
        timed_out = []

        def on_timeout(task: str, elapsed: float) -> None:
            timed_out.append(task)

        wd = WatchdogTimer(timeout_seconds=0.08, on_timeout=on_timeout)
        wd.task_started("Quick Command")
        time.sleep(0.02)
        wd.task_completed()
        time.sleep(0.08)

        self.assertEqual(len(timed_out), 0)


class TestPomodoroManager(unittest.TestCase):
    """Test work/break cycle and formatting."""

    def test_timer_initial_and_tick(self) -> None:
        mgr = PomodoroManager()
        self.assertEqual(mgr.formatted_time, "25:00")
        mgr.start()
        self.assertTrue(mgr.is_running)

        # Fast forward seconds
        mgr.seconds_left = 2
        mgr.tick_second()
        self.assertEqual(mgr.seconds_left, 1)

        tip = mgr.tick_second()
        self.assertTrue(mgr.is_break)
        self.assertIsNotNone(tip)
        self.assertEqual(mgr.seconds_left, PomodoroManager.BREAK_DURATION)
        self.assertEqual(mgr.completed_cycles, 1)


class TestPhysicsEngine(unittest.TestCase):
    """Test gravitational drop and bounce physics."""

    def test_drop_and_settle(self) -> None:
        engine = PhysicsEngine(gravity=5.0, elasticity=0.2)
        engine.start_drop(initial_velocity=0.0)

        y = 100
        floor_y = 500

        # Simulate frames
        settled = False
        for _ in range(100):
            y, settled = engine.update_position(y, floor_y)
            if settled:
                break

        self.assertTrue(settled)
        self.assertEqual(y, floor_y)


class TestArchitectureWisdom(unittest.TestCase):
    """Test senior architect pearls collection."""

    def test_get_random_pill(self) -> None:
        pill = ArchitectureWisdom.get_random_pill()
        self.assertIsInstance(pill, str)
        self.assertGreater(len(pill), 10)


class TestDetectiveAndSecretStates(unittest.TestCase):
    """Test Detective Mode and secret detection in PetStateMachine."""

    def test_detective_mode_on_consecutive_errors(self) -> None:
        sm = PetStateMachine()
        self.assertEqual(sm.consecutive_errors, 0)

        # Error 1
        pkt1 = EventPacket(event="PostToolUse", timestamp=time.time(), error="fail 1")
        sm.process_event(pkt1)
        self.assertEqual(sm.consecutive_errors, 1)
        self.assertEqual(sm.current_state, PetState.FAILED)

        # Error 2
        pkt2 = EventPacket(event="PostToolUse", timestamp=time.time(), error="fail 2")
        sm.process_event(pkt2)
        self.assertEqual(sm.consecutive_errors, 2)
        self.assertEqual(sm.current_state, PetState.FAILED)

        # Error 3 -> Triggers Detective Mode
        pkt3 = EventPacket(event="PostToolUse", timestamp=time.time(), error="fail 3")
        sm.process_event(pkt3)
        self.assertEqual(sm.consecutive_errors, 3)
        self.assertEqual(sm.current_state, PetState.REVIEW)
        self.assertIn("Detective", sm.current_title or "")

        # Clean success resets error streak
        pkt_ok = EventPacket(event="PostToolUse", timestamp=time.time(), error=None)
        sm.process_event(pkt_ok)
        self.assertEqual(sm.consecutive_errors, 0)

    def test_secret_packet_tracking(self) -> None:
        sm = PetStateMachine()
        pkt = EventPacket(
            event="PreToolUse",
            timestamp=time.time(),
            tool="write_to_file",
            title="Modo Sigilo",
            detail="Editando .env",
            is_secret=True,
        )
        sm.process_event(pkt)
        self.assertTrue(sm.is_secret)


if __name__ == "__main__":
    unittest.main()
