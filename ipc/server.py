"""IPC Server daemon listening for Antigravity lifecycle events."""

import logging
import os
import socket
import threading
from typing import Callable, List, Optional

from ipc.protocol import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_UDP_HOST,
    DEFAULT_UDP_PORT,
    EventPacket,
)

logger = logging.getLogger("AntigravityPets.IPCServer")


class IPCServer:
    """Threaded IPC server listening for UDP and Unix domain datagrams."""

    def __init__(
        self,
        udp_host: str = DEFAULT_UDP_HOST,
        udp_port: int = DEFAULT_UDP_PORT,
        uds_path: Optional[str] = DEFAULT_SOCKET_PATH,
    ) -> None:
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.uds_path = uds_path
        self._running = False
        self._threads: List[threading.Thread] = []
        self._udp_sock: Optional[socket.socket] = None
        self._uds_sock: Optional[socket.socket] = None
        self._callbacks: List[Callable[[EventPacket], None]] = []

    def register_callback(self, callback: Callable[[EventPacket], None]) -> None:
        """Register a callback to be invoked on every received EventPacket."""
        self._callbacks.append(callback)

    def _dispatch(self, packet: EventPacket) -> None:
        """Invoke all registered callbacks with the event packet."""
        for cb in self._callbacks:
            try:
                cb(packet)
            except Exception as e:
                logger.error("Error in event callback: %s", e)

    def _udp_loop(self) -> None:
        """Loop receiving incoming UDP datagrams."""
        while self._running and self._udp_sock:
            try:
                data, _ = self._udp_sock.recvfrom(65535)
                if not data:
                    continue
                packet = EventPacket.from_bytes(data)
                self._dispatch(packet)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                logger.debug("Failed parsing incoming UDP packet: %s", e)

    def _uds_loop(self) -> None:
        """Loop receiving incoming Unix domain socket datagrams."""
        while self._running and self._uds_sock:
            try:
                data, _ = self._uds_sock.recvfrom(65535)
                if not data:
                    continue
                packet = EventPacket.from_bytes(data)
                self._dispatch(packet)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                logger.debug("Failed parsing incoming UDS packet: %s", e)

    def start(self) -> None:
        """Start listening threads for UDP (and optionally UDS)."""
        if self._running:
            return
        self._running = True

        # Bind UDP
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.udp_host, self.udp_port))
            sock.settimeout(0.5)
            self._udp_sock = sock

            t_udp = threading.Thread(target=self._udp_loop, name="IPCServer-UDP", daemon=True)
            t_udp.start()
            self._threads.append(t_udp)
            logger.info("Listening on UDP %s:%d", self.udp_host, self.udp_port)
        except Exception as e:
            logger.warning("Could not bind UDP socket on %s:%d: %s", self.udp_host, self.udp_port, e)

        # Bind UDS (if path provided)
        if self.uds_path:
            try:
                if os.path.exists(self.uds_path):
                    try:
                        os.unlink(self.uds_path)
                    except OSError:
                        pass
                uds_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                uds_sock.bind(self.uds_path)
                uds_sock.settimeout(0.5)
                self._uds_sock = uds_sock

                t_uds = threading.Thread(target=self._uds_loop, name="IPCServer-UDS", daemon=True)
                t_uds.start()
                self._threads.append(t_uds)
                logger.info("Listening on UDS %s", self.uds_path)
            except Exception as e:
                logger.debug("UDS listener setup skipped: %s", e)

    def stop(self) -> None:
        """Stop listening threads and close sockets."""
        self._running = False
        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
            self._udp_sock = None

        if self._uds_sock:
            try:
                self._uds_sock.close()
            except Exception:
                pass
            self._uds_sock = None
            if self.uds_path and os.path.exists(self.uds_path):
                try:
                    os.unlink(self.uds_path)
                except OSError:
                    pass

        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
