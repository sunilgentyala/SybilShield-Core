"""Tests for the Composite Trust Score engine."""

from __future__ import annotations

import time

import pytest

from src.core.scoring.cts_engine import CTSEngine, PeerRecord, PENALTY_WEIGHTS, REWARD_WEIGHTS


class TestPeerRecord:
    def test_initial_score_is_neutral(self):
        record = PeerRecord(peer_id="peer_001")
        assert record.score == 0.5

    def test_decay_pulls_high_score_toward_neutral(self):
        record = PeerRecord(peer_id="peer_002", score=0.9)
        future = time.time() + 86400  # one decay half-life
        record.apply_decay(now=future)
        assert 0.5 < record.score < 0.9

    def test_decay_pulls_low_score_toward_neutral(self):
        record = PeerRecord(peer_id="peer_003", score=0.1)
        future = time.time() + 86400
        record.apply_decay(now=future)
        assert 0.1 < record.score < 0.5

    def test_neutral_score_unchanged_by_decay(self):
        record = PeerRecord(peer_id="peer_004", score=0.5)
        future = time.time() + 172800
        record.apply_decay(now=future)
        assert abs(record.score - 0.5) < 1e-6


class TestCTSEngine:
    def test_registers_peer_with_neutral_score(self):
        engine = CTSEngine()
        record = engine.register("peer_001")
        assert record.score == 0.5

    def test_penalty_reduces_score(self):
        engine = CTSEngine()
        engine.register("peer_001")
        score = engine.update_behavior("peer_001", "relay_timeout")
        assert score < 0.5

    def test_reward_increases_score(self):
        engine = CTSEngine()
        engine.register("peer_001")
        score = engine.update_behavior("peer_001", "timely_relay")
        assert score > 0.5

    def test_equivocation_causes_large_penalty(self):
        engine = CTSEngine()
        engine.register("peer_001")
        score = engine.update_behavior("peer_001", "equivocation")
        relay_engine = CTSEngine()
        relay_engine.register("peer_002")
        relay_score = relay_engine.update_behavior("peer_002", "relay_timeout")
        assert score < relay_score

    def test_score_clamped_at_minimum(self):
        engine = CTSEngine()
        engine.register("peer_001")
        for _ in range(20):
            engine.update_behavior("peer_001", "eclipse_attempt")
        assert engine.get_score("peer_001") >= 0.0

    def test_score_clamped_at_maximum(self):
        engine = CTSEngine()
        engine.register("peer_001")
        for _ in range(200):
            engine.update_behavior("peer_001", "timely_relay")
        assert engine.get_score("peer_001") <= 1.0

    def test_quarantine_triggered_below_threshold(self):
        engine = CTSEngine()
        engine.register("peer_001")
        for _ in range(10):
            engine.update_behavior("peer_001", "eclipse_attempt")
        record = engine.get_record("peer_001")
        assert record is not None
        assert record.quarantined is True

    def test_quarantined_peer_has_zero_quorum_weight(self):
        engine = CTSEngine()
        engine.register("peer_001")
        for _ in range(10):
            engine.update_behavior("peer_001", "eclipse_attempt")
        assert engine.quorum_weight("peer_001") == 0.0

    def test_unregistered_peer_returns_neutral_score(self):
        engine = CTSEngine()
        assert engine.get_score("unknown_peer") == 0.5

    def test_high_score_peer_has_high_quorum_weight(self):
        engine = CTSEngine()
        engine.register("peer_001")
        for _ in range(50):
            engine.update_behavior("peer_001", "timely_relay")
        weight = engine.quorum_weight("peer_001")
        assert weight > 0.8

    def test_centrality_update_raises_score(self):
        engine = CTSEngine()
        engine.register("peer_001")
        initial = engine.get_score("peer_001")
        engine.update_centrality("peer_001", centrality=0.8)
        assert engine.get_score("peer_001") > initial

    def test_all_scores_returns_all_registered_peers(self):
        engine = CTSEngine()
        engine.register("a")
        engine.register("b")
        engine.register("c")
        scores = engine.all_scores()
        assert set(scores.keys()) == {"a", "b", "c"}
