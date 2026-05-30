"""
SybilShield-Core: Composite Trust Score (CTS) Engine

Assigns each peer a dynamic, multi-dimensional trust score derived from:
  - Stake age and economic commitment
  - Behavioral consistency (block relay timing, vote deviation)
  - Graph-theoretic centrality within the peer topology
  - Historical penalty record

Score decays over inactivity windows and recovers through sustained
compliant behavior, preventing static whitelisting.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

SCORE_MAX: float = 1.0
SCORE_MIN: float = 0.0
DECAY_HALF_LIFE_SECONDS: float = 86400.0  # 24 hours
PENALTY_WEIGHTS: dict[str, float] = {
    "relay_timeout": 0.05,
    "equivocation": 0.30,
    "mempool_flood": 0.15,
    "eclipse_attempt": 0.40,
    "oracle_deviation": 0.20,
}
REWARD_WEIGHTS: dict[str, float] = {
    "timely_relay": 0.01,
    "valid_vote": 0.01,
    "stake_age_bonus": 0.005,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PeerRecord:
    """Runtime trust record for a single peer identity."""

    peer_id: str
    score: float = 0.5
    stake_age_blocks: int = 0
    last_seen: float = field(default_factory=time.time)
    penalties: list[tuple[str, float]] = field(default_factory=list)
    graph_centrality: float = 0.0
    quarantined: bool = False

    def apply_decay(self, now: Optional[float] = None) -> None:
        """Exponential decay toward 0.5 (neutral) over inactivity windows."""
        now = now or time.time()
        elapsed = now - self.last_seen
        half_lives = elapsed / DECAY_HALF_LIFE_SECONDS
        # Pull score toward neutral (0.5) via exponential decay
        self.score = 0.5 + (self.score - 0.5) * math.exp(-0.693 * half_lives)
        self.last_seen = now


# ---------------------------------------------------------------------------
# Composite Trust Score engine
# ---------------------------------------------------------------------------


class CTSEngine:
    """Composite Trust Score engine.

    Maintains a registry of PeerRecord instances and provides:
      - update_behavior(): incorporate a behavioral event
      - get_score(): retrieve the current decayed score
      - quorum_weight(): map score to consensus voting weight
    """

    def __init__(self) -> None:
        self._peers: dict[str, PeerRecord] = {}

    def register(self, peer_id: str, initial_stake_age: int = 0) -> PeerRecord:
        record = PeerRecord(peer_id=peer_id, stake_age_blocks=initial_stake_age)
        self._peers[peer_id] = record
        return record

    def get_record(self, peer_id: str) -> Optional[PeerRecord]:
        return self._peers.get(peer_id)

    def update_behavior(self, peer_id: str, event_type: str, now: Optional[float] = None) -> float:
        """Apply a behavioral event (penalty or reward) and return the updated score.

        Args:
            peer_id: The peer whose record is being updated.
            event_type: Key into PENALTY_WEIGHTS or REWARD_WEIGHTS.
            now: Timestamp override for testing.

        Returns:
            Updated trust score after applying decay and event delta.
        """
        record = self._peers.get(peer_id)
        if record is None:
            record = self.register(peer_id)

        record.apply_decay(now)

        if event_type in PENALTY_WEIGHTS:
            delta = -PENALTY_WEIGHTS[event_type]
            record.penalties.append((event_type, record.score))
        elif event_type in REWARD_WEIGHTS:
            delta = REWARD_WEIGHTS[event_type]
        else:
            delta = 0.0

        record.score = max(SCORE_MIN, min(SCORE_MAX, record.score + delta))

        if record.score < 0.20:
            record.quarantined = True

        return record.score

    def get_score(self, peer_id: str) -> float:
        record = self._peers.get(peer_id)
        if record is None:
            return 0.5
        record.apply_decay()
        return record.score

    def quorum_weight(self, peer_id: str) -> float:
        """Map trust score to a consensus quorum weight in [0.0, 1.0].

        Nodes below the quarantine threshold receive zero quorum weight.
        Score-to-weight mapping uses a sigmoid to avoid sharp transitions.
        """
        score = self.get_score(peer_id)
        record = self._peers.get(peer_id)
        if record and record.quarantined:
            return 0.0
        # Sigmoid centered at score=0.5
        return 1.0 / (1.0 + math.exp(-10.0 * (score - 0.5)))

    def update_centrality(self, peer_id: str, centrality: float) -> None:
        """Incorporate graph centrality into the trust score as an additive term."""
        record = self._peers.get(peer_id)
        if record is None:
            return
        # Centrality contribution is weighted at 10% of total score
        centrality_contribution = 0.10 * centrality
        record.score = max(SCORE_MIN, min(SCORE_MAX, record.score + centrality_contribution))

    def all_scores(self) -> dict[str, float]:
        return {pid: self.get_score(pid) for pid in self._peers}
