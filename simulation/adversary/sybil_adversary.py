"""
Adversary simulation: parameterized Sybil attack scenario implementations.

Provides SybilAdversary, which orchestrates coordinated attacks on a
synthetic network for evaluation of CTS detection performance.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AttackScenario:
    name: str
    sybil_count: int
    target_node_id: str
    attack_type: str  # "eclipse" | "consensus_mask" | "mempool_flood" | "dfl_poison"
    duration_seconds: float = 300.0
    intensity: float = 1.0  # 0.0 - 1.0 scaling factor


class SybilAdversary:
    """Simulates a coordinated Sybil adversary across multiple attack scenarios.

    Generates realistic sequences of malicious protocol events for injection
    into the network simulator, allowing evaluation of detection latency,
    false positive rates, and isolation effectiveness.
    """

    def __init__(
        self,
        scenario: AttackScenario,
        event_sink: Callable[[str, str, dict], None],
        rng_seed: int = 42,
    ) -> None:
        self._scenario = scenario
        self._sink = event_sink
        self._rng = random.Random(rng_seed)
        self._sybil_ids = [f"sybil_{i:04d}" for i in range(scenario.sybil_count)]

    def run(self) -> list[dict[str, Any]]:
        """Execute the configured attack scenario and return an event log."""
        dispatch = {
            "eclipse": self._run_eclipse,
            "consensus_mask": self._run_consensus_mask,
            "mempool_flood": self._run_mempool_flood,
            "dfl_poison": self._run_dfl_poison,
        }
        handler = dispatch.get(self._scenario.attack_type)
        if handler is None:
            raise ValueError(f"Unknown attack type: {self._scenario.attack_type}")
        return handler()

    def _run_eclipse(self) -> list[dict]:
        events = []
        target = self._scenario.target_node_id
        for sybil_id in self._sybil_ids:
            ip = self._random_ip(subnet="10.0.0")
            event = {
                "type": "connection_attempt",
                "src": sybil_id,
                "dst": target,
                "ip": ip,
                "timestamp": time.time(),
            }
            self._sink(sybil_id, "eclipse_attempt", event)
            events.append(event)
        return events

    def _run_consensus_mask(self) -> list[dict]:
        events = []
        target = self._scenario.target_node_id
        block_hash = "0x" + "a" * 64
        for sybil_id in self._sybil_ids:
            event = {
                "type": "block_withhold",
                "src": sybil_id,
                "block_hash": block_hash,
                "target": target,
                "timestamp": time.time(),
            }
            self._sink(sybil_id, "relay_timeout", event)
            events.append(event)
        return events

    def _run_mempool_flood(self) -> list[dict]:
        events = []
        tx_count = int(1000 * self._scenario.intensity)
        for i in range(tx_count):
            sybil_id = self._rng.choice(self._sybil_ids)
            event = {
                "type": "tx_broadcast",
                "src": sybil_id,
                "tx_id": f"tx_{i:06d}",
                "timestamp": time.time(),
            }
            self._sink(sybil_id, "mempool_flood", event)
            events.append(event)
        return events

    def _run_dfl_poison(self) -> list[dict]:
        events = []
        for sybil_id in self._sybil_ids:
            poisoned_gradient = [self._rng.gauss(5.0, 0.1) for _ in range(64)]
            event = {
                "type": "dfl_update",
                "src": sybil_id,
                "gradient_norm": sum(abs(g) for g in poisoned_gradient),
                "timestamp": time.time(),
            }
            self._sink(sybil_id, "oracle_deviation", event)
            events.append(event)
        return events

    def _random_ip(self, subnet: str = "192.168") -> str:
        return f"{subnet}.{self._rng.randint(0, 255)}.{self._rng.randint(1, 254)}"
