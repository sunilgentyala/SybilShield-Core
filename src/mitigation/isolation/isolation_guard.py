"""
Isolation mitigation: peer list sanitization and Eclipse prevention.

Enforces connection diversity constraints that prevent Sybil nodes from
monopolizing all inbound and outbound slots of a target peer.
"""

from __future__ import annotations

import ipaddress
from collections import defaultdict
from typing import Optional

MAX_CONNECTIONS_PER_SUBNET_16: int = 2
MAX_CONNECTIONS_PER_SUBNET_24: int = 1
MIN_SUBNET_DIVERSITY: float = 0.60


class IsolationGuard:
    """Enforces peer connection diversity to prevent Eclipse attacks.

    Maintains a live connection table and rejects connection requests
    that would violate subnet diversity or per-subnet connection limits.
    """

    def __init__(
        self,
        max_subnet16: int = MAX_CONNECTIONS_PER_SUBNET_16,
        max_subnet24: int = MAX_CONNECTIONS_PER_SUBNET_24,
        min_diversity: float = MIN_SUBNET_DIVERSITY,
    ) -> None:
        self._max_subnet16 = max_subnet16
        self._max_subnet24 = max_subnet24
        self._min_diversity = min_diversity
        self._connections: dict[str, str] = {}       # peer_id -> ip_address
        self._subnet16_counts: dict[str, int] = defaultdict(int)
        self._subnet24_counts: dict[str, int] = defaultdict(int)

    def _subnet16(self, ip: str) -> str:
        try:
            net = ipaddress.ip_network(ip + "/16", strict=False)
            return str(net.network_address)
        except ValueError:
            return "unknown"

    def _subnet24(self, ip: str) -> str:
        try:
            net = ipaddress.ip_network(ip + "/24", strict=False)
            return str(net.network_address)
        except ValueError:
            return "unknown"

    def accept_connection(self, peer_id: str, ip_address: str) -> tuple[bool, str]:
        """Evaluate whether a new connection from peer_id/ip should be accepted.

        Returns:
            (accepted: bool, reason: str)
        """
        s16 = self._subnet16(ip_address)
        s24 = self._subnet24(ip_address)

        if self._subnet16_counts[s16] >= self._max_subnet16:
            return False, f"Subnet /16 {s16} at capacity ({self._max_subnet16})"

        if self._subnet24_counts[s24] >= self._max_subnet24:
            return False, f"Subnet /24 {s24} at capacity ({self._max_subnet24})"

        # Provisionally accept and check resulting diversity
        self._connections[peer_id] = ip_address
        self._subnet16_counts[s16] += 1
        self._subnet24_counts[s24] += 1

        diversity = self._current_diversity()
        if diversity < self._min_diversity and len(self._connections) > 8:
            # Roll back
            del self._connections[peer_id]
            self._subnet16_counts[s16] -= 1
            self._subnet24_counts[s24] -= 1
            return False, f"Connection would reduce subnet diversity to {diversity:.2f}"

        return True, "Accepted"

    def remove_connection(self, peer_id: str) -> None:
        ip = self._connections.pop(peer_id, None)
        if ip:
            self._subnet16_counts[self._subnet16(ip)] -= 1
            self._subnet24_counts[self._subnet24(ip)] -= 1

    def _current_diversity(self) -> float:
        if not self._connections:
            return 1.0
        unique_subnets = len({self._subnet16(ip) for ip in self._connections.values()})
        return unique_subnets / len(self._connections)

    def connection_count(self) -> int:
        return len(self._connections)

    def flagged_peers(self) -> list[str]:
        """Return peers whose subnet appears more than max_subnet16 times."""
        counts: dict[str, list[str]] = defaultdict(list)
        for pid, ip in self._connections.items():
            counts[self._subnet16(ip)].append(pid)
        return [pid for peers in counts.values() if len(peers) > self._max_subnet16 for pid in peers]
