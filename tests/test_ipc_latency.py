"""IPC latency benchmark test for Antigravity Pets hook dispatch."""

import json
import statistics
import time
import unittest

from dispatcher.dispatch_hook import fast_send
from ipc.protocol import EventPacket


class TestIPCLatency(unittest.TestCase):
    """Benchmark the synchronous dispatch latency of hook events."""

    def test_synthetic_1000_events_latency(self) -> None:
        """Run 1,000 synthetic hook events and assert SLA constraints.

        Constraints:
        - Median execution time < 5.0 ms
        - Maximum execution time < 15.0 ms
        """
        num_events = 1000
        latencies_ms = []

        events = ["PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"]
        tools = ["run_command", "write_to_file", "view_file", None]

        for i in range(num_events):
            event_type = events[i % len(events)]
            tool = tools[i % len(tools)]
            error = "test error" if (event_type == "PostToolUse" and i % 7 == 0) else None

            packet = EventPacket(
                event=event_type,
                timestamp=time.time(),
                tool=tool,
                error=error,
            )
            payload = packet.to_bytes()

            t0 = time.perf_counter()
            fast_send(payload)
            t1 = time.perf_counter()

            latencies_ms.append((t1 - t0) * 1000.0)

        latencies_ms.sort()
        median_lat = statistics.median(latencies_ms)
        mean_lat = statistics.mean(latencies_ms)
        p95_lat = latencies_ms[int(num_events * 0.95)]
        p99_lat = latencies_ms[int(num_events * 0.99)]
        max_lat = max(latencies_ms)
        min_lat = min(latencies_ms)

        print("\n--- IPC Latency Benchmark (1,000 events) ---")
        print(f"Min:    {min_lat:.4f} ms")
        print(f"Mean:   {mean_lat:.4f} ms")
        print(f"Median: {median_lat:.4f} ms")
        print(f"P95:    {p95_lat:.4f} ms")
        print(f"P99:    {p99_lat:.4f} ms")
        print(f"Max:    {max_lat:.4f} ms")
        print("--------------------------------------------")

        self.assertLess(
            median_lat,
            5.0,
            f"Median latency ({median_lat:.4f} ms) exceeded 5.0 ms SLA target",
        )
        self.assertLess(
            max_lat,
            15.0,
            f"Maximum latency ({max_lat:.4f} ms) exceeded 15.0 ms SLA ceiling",
        )


if __name__ == "__main__":
    unittest.main()
