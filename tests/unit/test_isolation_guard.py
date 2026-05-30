"""Tests for the IsolationGuard Eclipse prevention module."""

from __future__ import annotations

import pytest

from src.mitigation.isolation.isolation_guard import IsolationGuard


class TestIsolationGuard:
    def test_accepts_connection_from_diverse_subnets(self):
        guard = IsolationGuard()
        accepted, _ = guard.accept_connection("peer_001", "10.0.1.5")
        assert accepted is True

    def test_rejects_third_connection_from_same_subnet16(self):
        guard = IsolationGuard(max_subnet16=2)
        guard.accept_connection("peer_001", "10.0.1.5")
        guard.accept_connection("peer_002", "10.0.2.5")
        accepted, reason = guard.accept_connection("peer_003", "10.0.3.5")
        assert accepted is False
        assert "/16" in reason

    def test_rejects_second_connection_from_same_subnet24(self):
        guard = IsolationGuard(max_subnet24=1)
        guard.accept_connection("peer_001", "10.0.1.5")
        accepted, reason = guard.accept_connection("peer_002", "10.0.1.6")
        assert accepted is False
        assert "/24" in reason

    def test_connection_count_tracks_correctly(self):
        guard = IsolationGuard()
        guard.accept_connection("peer_001", "10.0.1.5")
        guard.accept_connection("peer_002", "192.168.1.5")
        assert guard.connection_count() == 2

    def test_remove_connection_frees_subnet_slot(self):
        guard = IsolationGuard(max_subnet16=1)
        guard.accept_connection("peer_001", "10.0.1.5")
        guard.remove_connection("peer_001")
        accepted, _ = guard.accept_connection("peer_002", "10.0.2.5")
        assert accepted is True

    def test_flagged_peers_identifies_subnet_violators(self):
        guard = IsolationGuard(max_subnet16=1)
        # Manually bypass the check to seed two connections from same /16
        guard._connections["a"] = "10.0.1.5"
        guard._connections["b"] = "10.0.2.5"
        guard._subnet16_counts["10.0.0.0"] = 2
        flagged = guard.flagged_peers()
        assert len(flagged) == 2
