"""
End-to-end Sybil detection pipeline: wires the existing CTSEngine,
PeerGraph, IsolationGuard, and BehaviorMonitor components (src/) together
with the synthetic topology and Sybil injection generators (simulation/)
to produce real, measured detection statistics.

This module does not reimplement any detection logic -- it drives the
project's actual scoring/monitoring/mitigation code against a generated
network and records what that code actually decides.

Honest limitations of this harness, disclosed here rather than in
marketing copy:

  * "Rounds" are abstract behavioral ticks, not real Bitcoin block
    intervals. No real block propagation, consensus, or churn is
    simulated.
  * CTSEngine.PeerRecord.quarantined is a one-way flag in the current
    reference implementation: once True it is never reset, even if the
    score later recovers above the reinstatement threshold. This harness
    reports that as measured, not as a design assumption of this script.
  * stake_age_blocks is stored on PeerRecord but is not read anywhere in
    CTSEngine's scoring path; economic signal is only incorporated
    through the existing REWARD_WEIGHTS["stake_age_bonus"] event, which
    this harness invokes explicitly for peers with nonzero stake age.
  * The "computational overhead" metric measures wall-clock time to run
    IsolationGuard.accept_connection() plus the CTS/graph update path on
    this machine. It is a proxy for engine compute cost, not a
    network-level consensus latency benchmark (no consensus loop exists
    in this repository to measure).
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from src.core.scoring.cts_engine import CTSEngine
from src.mitigation.isolation.isolation_guard import IsolationGuard
from src.monitoring.behavior.relay_monitor import BehaviorMonitor, RELAY_TIMEOUT_SECONDS
from src.monitoring.graph.peer_graph import PeerGraph

from simulation.network.topology import build_honest_topology, node_ip
from simulation.scenarios.sybil_injection import inject_sybils, InjectedNetwork

QUARANTINE_THRESHOLD = 0.20  # mirrors CTSEngine's internal constant (src/core/scoring/cts_engine.py)

# Baseline (graph-only) detector: flag the bottom N-th percentile of nodes by
# normalized SybilRank trust mass. Chosen once, up front, without oracle
# knowledge of the true Sybil fraction in any given trial -- a defender in
# practice would pick a fixed conservative cutoff like this rather than
# knowing the true adversary density in advance. A naive fixed threshold at
# the distribution MEAN (normalized trust < 1.0) was tried first and produced
# a 58-65% false-positive rate on honest peers, because trust-propagation
# mass is heavily right-skewed (a few high-degree seed-adjacent nodes pull
# the mean well above the median) -- most honest peripheral peers sit below
# the mean simply from hop distance, not from Sybil-like behavior. The
# percentile cutoff below is a fairer, still-simple, graph-only baseline.
BASELINE_FLAG_PERCENTILE = 20


@dataclass
class TrialResult:
    n_honest: int
    n_sybil: int
    sybil_ratio_actual: float
    attack_type: str
    seed: int
    rounds: int

    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    baseline_tp: int = 0
    baseline_fp: int = 0
    baseline_fn: int = 0
    baseline_tn: int = 0

    detection_latency_rounds: list[int] = field(default_factory=list)

    isolation_rejected: int = 0
    isolation_total: int = 0

    pipeline_overhead_seconds: list[float] = field(default_factory=list)
    baseline_overhead_seconds: list[float] = field(default_factory=list)

    @property
    def tpr(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def fpr(self) -> float:
        denom = self.fp + self.tn
        return self.fp / denom if denom else 0.0

    @property
    def baseline_tpr(self) -> float:
        denom = self.baseline_tp + self.baseline_fn
        return self.baseline_tp / denom if denom else 0.0

    @property
    def baseline_fpr(self) -> float:
        denom = self.baseline_fp + self.baseline_tn
        return self.baseline_fp / denom if denom else 0.0


def _sybilrank_normalized(net: InjectedNetwork, pg: PeerGraph, seed_count: int) -> dict[str, float]:
    """Run PeerGraph.sybilrank_scores from a set of honest seed nodes and
    normalize each peer's trust mass relative to the uniform-distribution
    baseline (1/N), so a value of 1.0 means "average trust", <1.0 means
    below-average (Sybil-suggestive), and values are clipped to [0, 2]
    before being rescaled to [0, 1] for downstream scoring.
    """
    # PeerGraph exposes only in_degree()/out_degree(); use those to pick seeds.
    honest_by_degree = sorted(
        net.honest_ids, key=lambda n: pg.out_degree(n) + pg.in_degree(n), reverse=True
    )
    seeds = set(honest_by_degree[: max(1, seed_count)])

    raw = pg.sybilrank_scores(seed_nodes=seeds, iterations=20)
    n = len(net.all_ids)
    uniform = 1.0 / n if n else 1.0

    normalized: dict[str, float] = {}
    for node in net.all_ids:
        rel = raw.get(node, 0.0) / uniform if uniform else 0.0
        rel = max(0.0, min(2.0, rel))
        normalized[node] = rel / 2.0  # rescale [0,2] -> [0,1]
    return normalized


def run_trial(
    n_honest: int,
    sybil_ratio: float,
    attack_type: str,
    seed: int = 42,
    rounds: int = 25,
    ba_m: int = 4,
    graph_seed_count: int = 6,
    intensity: float = 1.0,
) -> TrialResult:
    """Run one full detection-pipeline trial and return measured metrics.

    Args:
        intensity: Fraction of injected Sybil identities that actively
            execute the attack behavior at all. The remaining
            (1 - intensity) fraction are "dormant" Sybils: identities
            that were injected (and are ground-truth Sybil for scoring
            purposes) but behave indistinguishably from an honest peer
            for the entire trial. intensity=1.0 (default) means every
            Sybil actively attacks -- an aggressive, fully-active
            adversary. Lower values model a mixed/sleeper population and
            are expected to reduce measured TPR, since a purely
            behavioral+graph signal cannot detect an identity that never
            behaves maliciously and has no distinguishing graph position.
    """
    rng = random.Random(seed)

    topology = build_honest_topology(n_honest=n_honest, m=ba_m, seed=seed)
    net = inject_sybils(topology, sybil_ratio=sybil_ratio, seed=seed)
    active_sybils = {node for node in net.sybil_ids if rng.random() < intensity}

    result = TrialResult(
        n_honest=len(net.honest_ids),
        n_sybil=len(net.sybil_ids),
        sybil_ratio_actual=len(net.sybil_ids) / len(net.all_ids),
        attack_type=attack_type,
        seed=seed,
        rounds=rounds,
    )

    # ---- Build the peer graph (undirected connections -> edges both ways) ---
    pg = PeerGraph()
    for a, b in net.graph.edges():
        pg.add_edge(a, b)
        pg.add_edge(b, a)

    # ---- CTS engine + behavior monitor wired together (real callback) -------
    cts = CTSEngine()
    monitor = BehaviorMonitor(event_callback=cts.update_behavior)

    for node in net.honest_ids:
        # Established honest peers show a spread of stake ages; a modest
        # fraction are freshly joined (needed for a realistic FPR test --
        # not every honest peer is a long-lived staker).
        stake_age = 0 if rng.random() < 0.12 else rng.randint(50, 2000)
        cts.register(node, initial_stake_age=stake_age)
    for node in net.sybil_ids:
        # Zero-cost identity creation is the definitional Sybil property.
        cts.register(node, initial_stake_age=0)

    # ---- Behavioral simulation, round by round -------------------------------
    quarantined_round: dict[str, int] = {}

    for round_idx in range(rounds):
        for node in net.honest_ids:
            # Occasional relay jitter over the timeout threshold (realistic
            # noise on an honest peer, not an attack) -- routed through the
            # actual BehaviorMonitor.record_relay() threshold check.
            if rng.random() < 0.04:
                delay = rng.uniform(RELAY_TIMEOUT_SECONDS + 1, RELAY_TIMEOUT_SECONDS + 30)
            else:
                delay = max(0.0, rng.gauss(6.0, 3.0))
            monitor.record_relay(node, block_hash=f"blk_{round_idx}", relay_delay_seconds=delay)

        for node in net.sybil_ids:
            if node not in active_sybils:
                # Dormant Sybil: behaves exactly like an honest peer.
                if rng.random() < 0.04:
                    delay = rng.uniform(RELAY_TIMEOUT_SECONDS + 1, RELAY_TIMEOUT_SECONDS + 30)
                else:
                    delay = max(0.0, rng.gauss(6.0, 3.0))
                monitor.record_relay(node, block_hash=f"blk_{round_idx}", relay_delay_seconds=delay)
                continue

            if attack_type == "consensus_mask":
                delay = rng.uniform(RELAY_TIMEOUT_SECONDS + 5, RELAY_TIMEOUT_SECONDS + 60)
                monitor.record_relay(node, block_hash=f"blk_{round_idx}", relay_delay_seconds=delay)
            elif attack_type == "eclipse":
                if round_idx == 0:
                    monitor.record_eclipse_attempt(node)
            elif attack_type == "mempool_flood":
                for _ in range(60):  # burst, exceeds FLOOD_RATE_THRESHOLD within FLOOD_WINDOW_SECONDS
                    monitor.record_transaction_broadcast(node)
            elif attack_type == "dfl_poison":
                cts.update_behavior(node, "oracle_deviation")
            else:
                raise ValueError(f"Unknown attack_type: {attack_type}")

        for node in net.sybil_ids:
            record = cts.get_record(node)
            if record is not None and record.quarantined and node not in quarantined_round:
                quarantined_round[node] = round_idx

    # ---- Economic signal: existing stake_age_bonus reward event -------------
    for node in net.honest_ids:
        record = cts.get_record(node)
        if record is None or record.stake_age_blocks <= 0:
            continue
        bonus_events = min(6, int(math.log2(1 + record.stake_age_blocks / 50.0)))
        for _ in range(bonus_events):
            cts.update_behavior(node, "stake_age_bonus")

    # ---- Graph signal: one topology snapshot, applied via update_centrality -
    sybilrank_norm = _sybilrank_normalized(net, pg, graph_seed_count)
    lcc_by_node: dict[str, float] = {}
    diversity_by_node: dict[str, float] = {}
    for node in net.all_ids:
        lcc = pg.local_clustering_coefficient(node)
        diversity = pg.subnet_diversity_score(node, net.subnets)
        lcc_by_node[node] = lcc
        diversity_by_node[node] = diversity

        graph_score = 0.5 * sybilrank_norm.get(node, 0.5) + 0.3 * diversity + 0.2 * (1.0 - lcc)
        centrality_signal = max(-1.0, min(1.0, (graph_score - 0.5) * 2.0))
        cts.update_centrality(node, centrality_signal)

    for node in net.sybil_ids:
        record = cts.get_record(node)
        if record is not None and record.quarantined and node not in quarantined_round:
            quarantined_round[node] = rounds  # crossed only after the graph snapshot

    # ---- IsolationGuard: real connection-acceptance evaluation --------------
    guard = IsolationGuard()
    sample_honest = net.honest_ids[: min(200, len(net.honest_ids))]
    for node in sample_honest:
        ip = node_ip(net.subnets[node], rng)
        t0 = time.perf_counter()
        guard.accept_connection(node, ip)
        result.pipeline_overhead_seconds.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        _ = True  # no-op baseline: unconditional accept
        result.baseline_overhead_seconds.append(time.perf_counter() - t0)

    if attack_type == "eclipse":
        for s_id, h_id in net.attack_edges:
            ip = node_ip(net.subnets[s_id], rng)
            t0 = time.perf_counter()
            accepted, _reason = guard.accept_connection(s_id, ip)
            result.pipeline_overhead_seconds.append(time.perf_counter() - t0)
            result.isolation_total += 1
            if not accepted:
                result.isolation_rejected += 1

    # ---- Final classification: composite CTS vs. graph-only baseline --------
    sorted_vals = sorted(sybilrank_norm.get(n, 0.5) for n in net.all_ids)
    pct_idx = max(0, int(len(sorted_vals) * BASELINE_FLAG_PERCENTILE / 100.0) - 1)
    baseline_cutoff = sorted_vals[pct_idx] if sorted_vals else 0.0

    for node in net.honest_ids:
        record = cts.get_record(node)
        predicted_sybil = bool(record and record.quarantined)
        if predicted_sybil:
            result.fp += 1
        else:
            result.tn += 1

        baseline_flag = sybilrank_norm.get(node, 0.5) <= baseline_cutoff
        if baseline_flag:
            result.baseline_fp += 1
        else:
            result.baseline_tn += 1

    for node in net.sybil_ids:
        record = cts.get_record(node)
        predicted_sybil = bool(record and record.quarantined)
        if predicted_sybil:
            result.tp += 1
            result.detection_latency_rounds.append(quarantined_round.get(node, rounds))
        else:
            result.fn += 1

        baseline_flag = sybilrank_norm.get(node, 0.5) <= baseline_cutoff
        if baseline_flag:
            result.baseline_tp += 1
        else:
            result.baseline_fn += 1

    return result
