"""Smoke tests for the real Sybil-detection simulation pipeline.

These are fast, small-scale sanity checks (not the full benchmark run --
see scripts/run_simulation.py and
simulation/results/sybil_detection_results.txt for the actual measured
results at benchmark scale).
"""

from __future__ import annotations

import pytest

from simulation.network.topology import build_honest_topology
from simulation.scenarios.sybil_injection import inject_sybils
from simulation.scenarios.detection_pipeline import run_trial


class TestTopology:
    def test_builds_requested_honest_node_count(self):
        topo = build_honest_topology(n_honest=40, m=4, seed=1)
        assert len(topo.node_ids) == 40
        assert topo.graph.number_of_nodes() == 40

    def test_every_node_has_a_subnet(self):
        topo = build_honest_topology(n_honest=40, m=4, seed=1)
        assert set(topo.subnets.keys()) == set(topo.node_ids)


class TestSybilInjection:
    def test_sybil_fraction_matches_requested_ratio(self):
        topo = build_honest_topology(n_honest=100, m=4, seed=1)
        net = inject_sybils(topo, sybil_ratio=0.20, seed=1)
        actual_ratio = len(net.sybil_ids) / len(net.all_ids)
        assert abs(actual_ratio - 0.20) < 0.02

    def test_sybils_use_few_shared_subnets(self):
        topo = build_honest_topology(n_honest=100, m=4, seed=1)
        net = inject_sybils(topo, sybil_ratio=0.20, seed=1, sybil_subnet_count=4)
        sybil_subnets = {net.subnets[s] for s in net.sybil_ids}
        assert len(sybil_subnets) <= 4

    def test_attack_edges_are_sparse(self):
        topo = build_honest_topology(n_honest=100, m=4, seed=1)
        net = inject_sybils(topo, sybil_ratio=0.20, seed=1)
        assert 0 < len(net.attack_edges) < len(net.sybil_ids)


class TestDetectionPipeline:
    @pytest.mark.parametrize(
        "attack_type", ["eclipse", "consensus_mask", "mempool_flood", "dfl_poison"]
    )
    def test_pipeline_runs_and_returns_valid_rates(self, attack_type):
        result = run_trial(
            n_honest=60, sybil_ratio=0.20, attack_type=attack_type, seed=3, rounds=10
        )
        assert 0.0 <= result.tpr <= 1.0
        assert 0.0 <= result.fpr <= 1.0
        assert 0.0 <= result.baseline_tpr <= 1.0
        assert 0.0 <= result.baseline_fpr <= 1.0
        assert result.n_sybil > 0

    def test_fully_active_adversary_beats_dormant_adversary_on_tpr(self):
        active = run_trial(
            n_honest=100, sybil_ratio=0.20, attack_type="consensus_mask",
            seed=5, rounds=15, intensity=1.0,
        )
        dormant = run_trial(
            n_honest=100, sybil_ratio=0.20, attack_type="consensus_mask",
            seed=5, rounds=15, intensity=0.0,
        )
        # A fully dormant Sybil population (never attacks) should be
        # detected no better than the fully active population.
        assert active.tpr >= dormant.tpr

    def test_composite_detector_has_low_false_positive_rate(self):
        result = run_trial(
            n_honest=100, sybil_ratio=0.20, attack_type="consensus_mask", seed=9, rounds=20
        )
        # Honest peers should rarely be quarantined under normal jitter noise.
        assert result.fpr < 0.10

    def test_unknown_attack_type_raises(self):
        with pytest.raises(ValueError):
            run_trial(n_honest=20, sybil_ratio=0.20, attack_type="nonexistent", seed=1, rounds=5)
