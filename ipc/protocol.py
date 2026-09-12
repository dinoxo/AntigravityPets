"""IPC Protocol definitions and packet validation for Antigravity Pets."""

from dataclasses import asdict, dataclass
import json
import time
from typing import Any, Dict, Optional, Set

DEFAULT_UDP_HOST: str = "127.0.0.1"
DEFAULT_UDP_PORT: int = 41738
DEFAULT_SOCKET_PATH: str = "/tmp/antigravity_pets.sock"

VALID_EVENTS: Set[str] = {
    "PreToolUse",
    "PostToolUse",
    "PreInvocation",
    "PostInvocation",
    "Stop",
}


@dataclass
class EventPacket:
    """Standardized event packet exchanged between dispatcher and desktop client."""

    event: str
    timestamp: float
    tool: Optional[str] = None
    error: Optional[str] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    is_secret: bool = False

    def to_json(self) -> str:
        """Serialize event packet to JSON string."""
        return json.dumps(
            {
                "event": self.event,
                "timestamp": self.timestamp,
                "tool": self.tool,
                "error": self.error,
                "title": self.title,
                "detail": self.detail,
                "is_secret": self.is_secret,
            }
        )

    def to_bytes(self) -> bytes:
        """Encode event packet as UTF-8 JSON bytes."""
        return self.to_json().encode("utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventPacket":
        """Construct an EventPacket from a dictionary with validation."""
        event = data.get("event")
        if not event or event not in VALID_EVENTS:
            raise ValueError(f"Invalid or missing event type: {event}")

        timestamp = data.get("timestamp")
        if timestamp is None:
            timestamp = time.time()
        else:
            try:
                timestamp = float(timestamp)
            except (ValueError, TypeError):
                timestamp = time.time()

        tool = data.get("tool")
        if tool is not None:
            tool = str(tool)

        error = data.get("error")
        if error is not None:
            error = str(error)

        title = data.get("title")
        if title is not None:
            title = str(title)

        detail = data.get("detail")
        if detail is not None:
            detail = str(detail)

        is_secret = bool(data.get("is_secret", False))

        return cls(
            event=event,
            timestamp=timestamp,
            tool=tool,
            error=error,
            title=title,
            detail=detail,
            is_secret=is_secret,
        )

    @classmethod
    def from_json(cls, raw: str) -> "EventPacket":
        """Parse JSON string into an EventPacket."""
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object")
        return cls.from_dict(data)

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> "EventPacket":
        """Parse raw bytes into an EventPacket."""
        return cls.from_json(raw_bytes.decode("utf-8"))
