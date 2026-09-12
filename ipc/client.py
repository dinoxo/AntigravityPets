"""Fast fire-and-forget IPC client for Antigravity Pets hook dispatcher."""

import os
import socket
from typing import Optional, Union

from ipc.protocol import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_UDP_HOST,
    DEFAULT_UDP_PORT,
    EventPacket,
)


class IPCClient:
    """Non-blocking fire-and-forget IPC client.

    Designed specifically for sub-5ms hook dispatch requirements.
    Silently drops packets when the desktop overlay is inactive.
    """

    def __init__(
        self,
        udp_host: str = DEFAULT_UDP_HOST,
        udp_port: int = DEFAULT_UDP_PORT,
        uds_path: Optional[str] = DEFAULT_SOCKET_PATH,
    ) -> None:
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.uds_path = uds_path

    def send(self, packet: Union[EventPacket, dict, str, bytes]) -> bool:
        """Send an event packet to the companion daemon.

        Attempts UDP first, and if UDS path exists and is a socket, also attempts UDS.
        Catches all errors to ensure zero latency impact on agent loop.

        Returns:
            bool: True if sent successfully via at least one transport, False otherwise.
        """
        if isinstance(packet, EventPacket):
            payload = packet.to_bytes()
        elif isinstance(packet, dict):
            payload = EventPacket.from_dict(packet).to_bytes()
        elif isinstance(packet, str):
            payload = packet.encode("utf-8")
        elif isinstance(packet, bytes):
            payload = packet
        else:
            return False

        delivered = False

        # 1. UDP Datagram (Primary transport)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.sendto(payload, (self.udp_host, self.udp_port))
            sock.close()
            delivered = True
        except Exception:
            # UDP failure or offline client must never block or throw
            pass

        # 2. Unix Domain Socket (Fallback/Secondary transport for local Unix)
        if self.uds_path and os.path.exists(self.uds_path):
            try:
                uds_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                uds_sock.setblocking(False)
                uds_sock.sendto(payload, self.uds_path)
                uds_sock.close()
                delivered = True
            except Exception:
                pass

        return delivered


# Module-level convenience singleton
_default_client = IPCClient()


def send_event(
    event: str,
    tool: Optional[str] = None,
    error: Optional[str] = None,
    timestamp: Optional[float] = None,
) -> bool:
    """Convenience helper to construct and send an EventPacket immediately."""
    import time

    packet = EventPacket(
        event=event,
        timestamp=timestamp if timestamp is not None else time.time(),
        tool=tool,
        error=error,
    )
    return _default_client.send(packet)
