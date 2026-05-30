"""
Behavior monitoring: block relay timing analysis and mempool flood detection.

Publishes scored behavioral events to the CTS engine event bus.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable


# Thresholds tunable via configs/monitoring.yaml
RELAY_TIMEOUT_SECONDS: float = 30.0
FLOOD_RATE_THRESHOLD: int = 50       # transactions per 10-second window
FLOOD_WINDOW_SECONDS: float = 10.0


@dataclass
class RelayEvent:
    peer_id: str
    block_hash: str
    received_at: float
    expected_by: float


class BehaviorMonitor:
    """Monitors per-peer protocol behavior and emits behavioral events.

    Connects to the CTS engine via a callback, keeping the monitoring
    layer decoupled from scoring logic.
    """

    def __init__(self, event_callback: Callable[[str, str], None]) -> None:
        self._callback = event_callback
        self._relay_windows: dict[str, deque] = defaultdict(deque)
        self._tx_windows: dict[str, deque] = defaultdict(deque)

    def record_relay(self, peer_id: str, block_hash: str, relay_delay_seconds: float) -> None:
        """Record a block relay event and flag timeouts."""
        if relay_delay_seconds > RELAY_TIMEOUT_SECONDS:
            self._callback(peer_id, "relay_timeout")
        else:
            self._callback(peer_id, "timely_relay")

    def record_transaction_broadcast(self, peer_id: str) -> None:
        """Detect mempool flooding via sliding window rate check."""
        now = time.time()
        window = self._tx_windows[peer_id]
        window.append(now)
        # Evict events outside the window
        while window and window[0] < now - FLOOD_WINDOW_SECONDS:
            window.popleft()
        if len(window) > FLOOD_RATE_THRESHOLD:
            self._callback(peer_id, "mempool_flood")

    def record_equivocation(self, peer_id: str) -> None:
        """Flag a peer that signed two conflicting blocks at the same height."""
        self._callback(peer_id, "equivocation")

    def record_eclipse_attempt(self, peer_id: str) -> None:
        """Flag a peer attempting to fill all connection slots of a target."""
        self._callback(peer_id, "eclipse_attempt")
