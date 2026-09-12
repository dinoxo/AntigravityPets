#!/usr/bin/env python3
"""High-performance Antigravity lifecycle hook dispatcher.

Synchronously invoked by Antigravity's hook runner (<20ms SLA).
Parses hook event context from stdin, emits fire-and-forget UDP/UDS datagram,
and prints the required JSON response to stdout.
"""

import argparse
import json
import os
import socket
import sys
import time
from typing import Any, Dict, Optional, Tuple

DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 41738
DEFAULT_SOCKET_PATH = "/tmp/antigravity_pets.sock"


def fast_send(payload_bytes: bytes) -> None:
    """Non-blocking fire-and-forget datagram dispatch.

    Attempts UDP first. If socket cannot be reached or client is offline,
    fails silently with zero latency penalty.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.sendto(payload_bytes, (DEFAULT_UDP_HOST, DEFAULT_UDP_PORT))
        sock.close()
    except Exception:
        pass

    # Optional local UDS dispatch if present
    if os.path.exists(DEFAULT_SOCKET_PATH):
        try:
            uds_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            uds_sock.setblocking(False)
            uds_sock.sendto(payload_bytes, DEFAULT_SOCKET_PATH)
            uds_sock.close()
        except Exception:
            pass


def extract_action_summary(
    event_type: str,
    data: Dict[str, Any],
    tool_name: Optional[str],
    error_msg: Optional[str],
) -> Tuple[str, str]:
    """Derive clean human-readable title and detail for the desktop HUD."""
    if event_type == "PreInvocation":
        return "Thinking...", "Analyzing context & planning"

    if event_type == "PostInvocation":
        return "Waiting", "Awaiting user response"

    if event_type == "PreToolUse":
        tool_call = data.get("toolCall", {}) if isinstance(data, dict) else {}
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
        name = tool_name or "Tool"

        if name == "run_command":
            cmd = args.get("CommandLine", "")
            if len(cmd) > 35:
                cmd = cmd[:32] + "..."
            return "Running Command", cmd or "Executing shell command"

        if name in ("write_to_file", "replace_file_content"):
            target = args.get("TargetFile", "")
            fname = os.path.basename(target) if target else "file"
            action = "Writing" if name == "write_to_file" else "Editing"
            return f"{action} File", fname

        if name == "view_file":
            path = args.get("AbsolutePath", "")
            fname = os.path.basename(path) if path else "file"
            return "Reading File", fname

        if name == "grep_search":
            q = args.get("Query", "")
            return "Searching Code", f'"{q[:28]}"' if q else "Grep search"

        if name == "find_by_name":
            p = args.get("Pattern", "")
            return "Finding Files", p or "File pattern search"

        if name == "search_web":
            q = args.get("query", "")
            return "Searching Web", f'"{q[:28]}"' if q else "Web search"

        if name == "read_url_content":
            u = args.get("Url", "")
            return "Fetching URL", u[:35] if u else "HTTP request"

        if name == "ask_question":
            return "Asking Question", "Waiting for your answer"

        return f"Executing {name}", "Processing step..."

    if event_type == "PostToolUse":
        if error_msg:
            err = error_msg.splitlines()[0] if error_msg else "Error"
            return "Tool Failed", err[:35]
        return "Reviewing", f"{tool_name or 'Step'} completed"

    if event_type == "Stop":
        if error_msg:
            return "Stopped with Error", error_msg[:35]
        return "Task Completed", "All goals finished!"

    return event_type, ""


def main() -> None:
    event_type = "PreToolUse"
    try:
        parser = argparse.ArgumentParser(description="Antigravity Pets Hook Dispatcher")
        parser.add_argument("--event", type=str, required=True, help="Lifecycle event name")
        args, _ = parser.parse_known_args()
        event_type = args.event

        timestamp = time.time()
        tool_name = None
        error_msg = None
        payload_data: Dict[str, Any] = {}

        # Read stdin payload if available
        if not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input.strip():
                payload_data = json.loads(raw_input)
                # PreToolUse
                if "toolCall" in payload_data and isinstance(payload_data["toolCall"], dict):
                    tool_name = payload_data["toolCall"].get("name")
                # PostToolUse or Stop error
                if payload_data.get("error"):
                    error_msg = str(payload_data.get("error"))
                # If error is empty string or None, normalize to None
                if error_msg == "":
                    error_msg = None

        title, detail = extract_action_summary(event_type, payload_data, tool_name, error_msg)

        # Build and dispatch packet
        packet = {
            "event": event_type,
            "timestamp": timestamp,
            "tool": tool_name,
            "error": error_msg,
            "title": title,
            "detail": detail,
        }
        payload_bytes = json.dumps(packet).encode("utf-8")
        fast_send(payload_bytes)

    except Exception:
        pass

    # Antigravity contract response - guaranteed output
    try:
        if event_type == "PreToolUse":
            sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        else:
            sys.stdout.write("{}\n")
        sys.stdout.flush()
    except Exception:
        pass


if __name__ == "__main__":
    main()
