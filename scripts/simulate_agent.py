#!/usr/bin/env python3
"""Interactive simulation of Antigravity agent lifecycle events.

Used to test and visually verify Antigravity Pets reacting in real-time
to invocations, tool calls, errors, review steps, and task stops.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISPATCHER_PATH = PROJECT_ROOT / "dispatcher" / "dispatch_hook.py"

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def dispatch(event: str, payload_dict: dict) -> None:
    """Invoke the actual dispatch_hook.py script with stdin payload."""
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    p = subprocess.Popen(
        [sys.executable, str(DISPATCHER_PATH), "--event", event],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(input=payload_bytes)
    output_str = stdout.decode().strip()
    return output_str


def run_simulation(step_delay: float = 1.8) -> None:
    print(f"\n{BOLD}======================================================{RESET}")
    print(f"{BOLD}  Antigravity Pets: Agent Lifecycle Simulation       {RESET}")
    print(f"{BOLD}======================================================{RESET}\n")
    print(f"Make sure {CYAN}bin/antigravity-pets-native{RESET} or {CYAN}desktop_py/app.py{RESET} is running.")
    print("Observing pet visual state transitions...\n")

    # Step 1: PreInvocation (Agent wakes up & starts thinking)
    print(f"{CYAN}[Step 1/7] Event: PreInvocation{RESET}")
    print("  -> Agent is thinking and processing prompt.")
    print(f"  -> Target Pet State: {MAGENTA}WORKING (Row 7){RESET}")
    dispatch("PreInvocation", {"invocationNum": 1, "initialNumSteps": 0})
    time.sleep(step_delay)

    # Step 2: PreToolUse (Agent calls run_command)
    print(f"\n{CYAN}[Step 2/7] Event: PreToolUse (tool: run_command){RESET}")
    print("  -> Agent begins executing shell command.")
    print(f"  -> Target Pet State: {MAGENTA}WORKING (Row 7){RESET}")
    dispatch(
        "PreToolUse",
        {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "npm test"},
            },
            "stepIdx": 1,
        },
    )
    time.sleep(step_delay)

    # Step 3: PostToolUse (Command succeeded)
    print(f"\n{CYAN}[Step 3/7] Event: PostToolUse (success){RESET}")
    print("  -> Tool finished cleanly. Agent is reviewing output.")
    print(f"  -> Target Pet State: {GREEN}REVIEW (Row 8){RESET}")
    dispatch(
        "PostToolUse",
        {
            "stepIdx": 1,
            "error": None,
        },
    )
    time.sleep(step_delay)

    # Step 4: PreToolUse (Agent runs another tool)
    print(f"\n{CYAN}[Step 4/7] Event: PreToolUse (tool: write_to_file){RESET}")
    print("  -> Agent is modifying a file.")
    print(f"  -> Target Pet State: {MAGENTA}WORKING (Row 7){RESET}")
    dispatch(
        "PreToolUse",
        {
            "toolCall": {
                "name": "write_to_file",
                "args": {"TargetFile": "/tmp/test.py"},
            },
            "stepIdx": 2,
        },
    )
    time.sleep(step_delay)

    # Step 5: PostToolUse (Tool encountered error)
    print(f"\n{CYAN}[Step 5/7] Event: PostToolUse (with error){RESET}")
    print("  -> Tool failed with error: 'Exit code 1: Assertion failed'.")
    print(f"  -> Target Pet State: {RED}FAILED (Row 5, transient shake/dizzy){RESET}")
    dispatch(
        "PostToolUse",
        {
            "stepIdx": 2,
            "error": "Exit code 1: Assertion failed",
        },
    )
    time.sleep(step_delay + 0.5)

    # Step 6: PostInvocation (Agent pauses, waiting for user response)
    print(f"\n{CYAN}[Step 6/7] Event: PostInvocation{RESET}")
    print("  -> Execution step complete, agent waiting for user input.")
    print(f"  -> Target Pet State: {YELLOW}WAITING (Row 6){RESET}")
    dispatch("PostInvocation", {"invocationNum": 1})
    time.sleep(step_delay)

    # Step 7: Stop (Agent completes task successfully)
    print(f"\n{CYAN}[Step 7/7] Event: Stop (clean task completion){RESET}")
    print("  -> Task completed cleanly.")
    print(f"  -> Target Pet State: {YELLOW}JUMP (Row 3, celebratory jump -> auto reverts to IDLE Row 0){RESET}")
    dispatch(
        "Stop",
        {
            "executionNum": 1,
            "terminationReason": "model_stop",
            "error": None,
            "fullyIdle": True,
        },
    )
    time.sleep(3.0)

    print(f"\n{GREEN}{BOLD}Simulation finished successfully! Pet returned to IDLE (Row 0).{RESET}\n")


if __name__ == "__main__":
    delay = 1.5
    if len(sys.argv) > 1:
        try:
            delay = float(sys.argv[1])
        except ValueError:
            pass
    run_simulation(step_delay=delay)
