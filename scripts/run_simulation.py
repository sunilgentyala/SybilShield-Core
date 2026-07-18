"""
SybilShield-Core: real Sybil-detection simulation runner.

Drives the actual project code (src/core/scoring/cts_engine.py,
src/mitigation/isolation/isolation_guard.py,
src/monitoring/behavior/relay_monitor.py, src/monitoring/graph/peer_graph.py)
against synthetically generated networks (simulation/network/topology.py,
simulation/scenarios/sybil_injection.py, simulation/scenarios/detection_pipeline.py)
and reports measured detection statistics.

This replaces the previous README/site claims, which were not backed by
any runnable code, with numbers produced by actually running this script.

Usage (from repo root):
    python scripts/run_simulation.py
    python scripts/run_simulation.py --nodes 300 --trials 20 \
        --sybil-ratios 0.10,0.20,0.30 --scenario all --intensities 1.0,0.5

Output: prints a summary table to stdout and writes a full methodology +
results report to simulation/results/sybil_detection_results.txt.
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import networkx  # noqa: E402

from simulation.scenarios.detection_pipeline import run_trial  # noqa: E402

ATTACK_TYPES = ["eclipse", "consensus_mask", "mempool_flood", "dfl_poison"]


def aggregate(results: list) -> dict:
    tprs = [r.tpr for r in results]
    fprs = [r.fpr for r in results]
    base_tprs = [r.baseline_tpr for r in results]
    base_fprs = [r.baseline_fpr for r in results]
    latencies = [lat for r in results for lat in r.detection_latency_rounds]
    pipeline_overhead = [t for r in results for t in r.pipeline_overhead_seconds]
    baseline_overhead = [t for r in results for t in r.baseline_overhead_seconds]
    iso_rejected = sum(r.isolation_rejected for r in results)
    iso_total = sum(r.isolation_total for r in results)

    return {
        "n_trials": len(results),
        "tpr_mean": statistics.mean(tprs) if tprs else 0.0,
        "tpr_stdev": statistics.stdev(tprs) if len(tprs) > 1 else 0.0,
        "fpr_mean": statistics.mean(fprs) if fprs else 0.0,
        "fpr_stdev": statistics.stdev(fprs) if len(fprs) > 1 else 0.0,
        "baseline_tpr_mean": statistics.mean(base_tprs) if base_tprs else 0.0,
        "baseline_fpr_mean": statistics.mean(base_fprs) if base_fprs else 0.0,
        "latency_median": statistics.median(latencies) if latencies else None,
        "latency_mean": statistics.mean(latencies) if latencies else None,
        "n_latency_samples": len(latencies),
        "pipeline_overhead_us_mean": statistics.mean(pipeline_overhead) * 1e6 if pipeline_overhead else 0.0,
        "baseline_overhead_us_mean": statistics.mean(baseline_overhead) * 1e6 if baseline_overhead else 0.0,
        "isolation_rejected": iso_rejected,
        "isolation_total": iso_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the real SybilShield-Core detection pipeline against synthetic networks."
    )
    parser.add_argument("--nodes", type=int, default=300, help="Honest node count (default: 300)")
    parser.add_argument(
        "--sybil-ratios", type=str, default="0.10,0.20,0.30",
        help="Comma-separated adversary fractions of the TOTAL post-injection network"
    )
    parser.add_argument(
        "--intensities", type=str, default="1.0,0.5",
        help="Comma-separated fraction of Sybils that actively attack (1.0=all active, "
             "<1.0=mixed active/dormant population)"
    )
    parser.add_argument(
        "--scenario", type=str, default="all",
        choices=ATTACK_TYPES + ["all"], help="Attack scenario to run"
    )
    parser.add_argument("--trials", type=int, default=20, help="Trials per configuration (default: 20)")
    parser.add_argument("--rounds", type=int, default=25, help="Behavioral rounds per trial (default: 25)")
    parser.add_argument(
        "--output", type=str,
        default=str(REPO_ROOT / "simulation" / "results" / "sybil_detection_results.txt"),
        help="Path to write the results report"
    )
    args = parser.parse_args()

    sybil_ratios = [float(x) for x in args.sybil_ratios.split(",")]
    intensities = [float(x) for x in args.intensities.split(",")]
    scenarios = ATTACK_TYPES if args.scenario == "all" else [args.scenario]

    lines: list[str] = []

    def emit(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    emit("SybilShield-Core Benchmark: Real Sybil Detection Pipeline")
    emit("=" * 70)
    emit(f"Date        : {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    emit(f"Platform    : {platform.platform()}")
    emit(f"Python      : {platform.python_version()}")
    emit(f"networkx    : {networkx.__version__}")
    emit("Script      : scripts/run_simulation.py")
    emit(f"Honest nodes: {args.nodes}  |  Trials/config: {args.trials}  |  Rounds/trial: {args.rounds}")
    emit("")
    emit(
        "Purpose: replace README/site/paper Evaluation claims (which were not backed by "
        "any runnable code prior to this benchmark) with numbers produced by actually "
        "driving src/core/scoring/cts_engine.py, src/mitigation/isolation/isolation_guard.py, "
        "src/monitoring/behavior/relay_monitor.py, and src/monitoring/graph/peer_graph.py "
        "against synthetically generated networks (simulation/network/topology.py, "
        "simulation/scenarios/sybil_injection.py, simulation/scenarios/detection_pipeline.py)."
    )
    emit("")

    t_start = time.time()
    all_results = {}

    for scenario in scenarios:
        for ratio in sybil_ratios:
            for intensity in intensities:
                key = (scenario, ratio, intensity)
                trial_results = []
                for trial in range(args.trials):
                    seed = hash((scenario, ratio, intensity, trial)) % (2**31)
                    r = run_trial(
                        n_honest=args.nodes,
                        sybil_ratio=ratio,
                        attack_type=scenario,
                        seed=seed,
                        rounds=args.rounds,
                        intensity=intensity,
                    )
                    trial_results.append(r)
                all_results[key] = aggregate(trial_results)
                agg = all_results[key]
                emit(
                    f"[{scenario:15s}] ratio={ratio:.2f} intensity={intensity:.1f}  "
                    f"TPR={agg['tpr_mean']*100:5.1f}%  FPR={agg['fpr_mean']*100:5.2f}%  "
                    f"baseline TPR={agg['baseline_tpr_mean']*100:5.1f}% "
                    f"baseline FPR={agg['baseline_fpr_mean']*100:5.2f}%  "
                    f"latency(med)={agg['latency_median']}"
                )

    elapsed = time.time() - t_start
    emit("")
    emit(f"Total wall-clock time for all trials: {elapsed:.1f}s")
    emit("")

    # ---- Detailed report -----------------------------------------------------
    emit("=" * 70)
    emit("DETAILED RESULTS (mean over trials; stdev in parentheses)")
    emit("=" * 70)
    for scenario in scenarios:
        emit(f"\n-- {scenario} --")
        emit(f"{'ratio':>6} {'intens':>6} {'TPR':>16} {'FPR':>16} {'base TPR':>10} {'base FPR':>10} {'lat(med/mean rounds)':>22}")
        for ratio in sybil_ratios:
            for intensity in intensities:
                agg = all_results[(scenario, ratio, intensity)]
                tpr_s = f"{agg['tpr_mean']*100:.1f}% ({agg['tpr_stdev']*100:.1f})"
                fpr_s = f"{agg['fpr_mean']*100:.2f}% ({agg['fpr_stdev']*100:.2f})"
                lat_s = f"{agg['latency_median']}/{agg['latency_mean']:.1f}" if agg['latency_mean'] is not None else "n/a"
                emit(
                    f"{ratio:>6.2f} {intensity:>6.1f} {tpr_s:>16} {fpr_s:>16} "
                    f"{agg['baseline_tpr_mean']*100:>9.1f}% {agg['baseline_fpr_mean']*100:>9.1f}% {lat_s:>22}"
                )

    # ---- IsolationGuard + overhead summary ------------------------------------
    emit("")
    emit("=" * 70)
    emit("ISOLATION GUARD (eclipse scenario, real accept_connection() calls)")
    emit("=" * 70)
    iso_rejected_total = sum(a["isolation_rejected"] for k, a in all_results.items() if k[0] == "eclipse")
    iso_total_total = sum(a["isolation_total"] for k, a in all_results.items() if k[0] == "eclipse")
    if iso_total_total:
        emit(
            f"Sybil attack-edge connection attempts rejected by IsolationGuard: "
            f"{iso_rejected_total}/{iso_total_total} ({iso_rejected_total/iso_total_total*100:.1f}%)"
        )
    else:
        emit("No eclipse-scenario trials run.")

    emit("")
    emit("=" * 70)
    emit("COMPUTATIONAL OVERHEAD (wall-clock, this machine -- NOT a network")
    emit("consensus latency benchmark; no consensus loop exists in this repo)")
    emit("=" * 70)
    overhead_samples_pipeline = []
    overhead_samples_baseline = []
    for k, a in all_results.items():
        if a["pipeline_overhead_us_mean"]:
            overhead_samples_pipeline.append(a["pipeline_overhead_us_mean"])
            overhead_samples_baseline.append(a["baseline_overhead_us_mean"])
    if overhead_samples_pipeline:
        mean_pipeline = statistics.mean(overhead_samples_pipeline)
        mean_baseline = statistics.mean(overhead_samples_baseline)
        emit(f"IsolationGuard.accept_connection() mean: {mean_pipeline:.2f} microseconds/call")
        emit(f"No-op baseline (unconditional accept) mean: {mean_baseline:.3f} microseconds/call")
        emit(
            f"Delta: +{mean_pipeline - mean_baseline:.2f} microseconds/call attributable to the "
            f"subnet-diversity + per-subnet-limit evaluation in IsolationGuard."
        )

    emit("")
    emit("=" * 70)
    emit("METHODOLOGY")
    emit("=" * 70)
    emit(
        f"""
Network generation (simulation/network/topology.py):
  Honest topology: Barabasi-Albert preferential attachment, n = {args.nodes} honest
  nodes, m = 4 edges per new node (networkx.barabasi_albert_graph). Honest
  peers are assigned IPs from a pool of 120 distinct /16 subnets.

Sybil injection (simulation/scenarios/sybil_injection.py):
  Sybil count derived so Sybils form the requested fraction of the TOTAL
  post-injection network (e.g. ratio=0.30 means Sybils are 30% of all
  nodes, not 30% of the honest count). Sybil identities are drawn from
  only 4 shared /16 subnets (cheap shared hosting -- the realistic
  economic signature of a Sybil farm), densely interconnected internally
  (mean internal degree ~6, Erdos-Renyi), and attach to the honest region
  through a small number of "attack edges" (~4 per 100 Sybils), following
  the attack-edge assumption used in the SybilGuard/SybilLimit line of
  work (Yu et al. 2008; this harness does not reimplement their random
  walk protocol -- see baseline note below).

Detection pipeline (simulation/scenarios/detection_pipeline.py):
  Wires the actual CTSEngine, BehaviorMonitor, PeerGraph, and
  IsolationGuard classes together (no detection logic reimplemented).
  Each trial runs {args.rounds} behavioral rounds. Per round, honest peers
  emit a relay event via BehaviorMonitor.record_relay() with a delay drawn
  from a jitter model (4% chance of exceeding the real 30s
  RELAY_TIMEOUT_SECONDS constant, else Normal(6s, 3s)). Active Sybils emit
  attack-specific events through the real monitor/engine methods:
    - eclipse:         BehaviorMonitor.record_eclipse_attempt() once
    - consensus_mask:  BehaviorMonitor.record_relay() with delay > timeout, every round
    - mempool_flood:   BehaviorMonitor.record_transaction_broadcast() bursts of 60/round
    - dfl_poison:      CTSEngine.update_behavior(..., "oracle_deviation") every round
  A configurable fraction of Sybils ("intensity") are "dormant" -- ground-truth
  Sybil but behaviorally indistinguishable from honest peers for the whole
  trial, modeling a mixed active/sleeper adversary population.

  After the behavioral rounds, ONE graph-topology snapshot is taken (as
  configs/monitoring.yaml's snapshot_interval_blocks implies periodic,
  not continuous, graph recomputation) using the real PeerGraph methods:
  local_clustering_coefficient(), sybilrank_scores() (seeded from the 6
  honest peers with highest in+out degree), and subnet_diversity_score().
  These are combined into a graph_score and applied via the real
  CTSEngine.update_centrality() API.

  A modest economic signal is applied via the existing (and otherwise
  unused in the reference code) REWARD_WEIGHTS["stake_age_bonus"] event,
  scaled to log2(stake_age_blocks).

  A peer is classified Sybil-predicted if CTSEngine's own PeerRecord.quarantined
  flag is True at the end of the trial (score crossed the real 0.20
  QUARANTINE threshold in cts_engine.py at any point -- this flag is a
  ONE-WAY latch in the current reference implementation; see limitations).

Baseline (graph-only) comparison:
  A simplified graph-propagation-only detector: flag the bottom 20th
  percentile of nodes (by network) ranked by normalized SybilRank trust
  mass computed via the SAME PeerGraph.sybilrank_scores() call used by the
  composite detector. This is NOT a reimplementation of the SybilGuard or
  SybilLimit random-walk protocols -- it exists to show what a
  graph-signal-only detector achieves on the identical generated topology,
  for honest contextual comparison, not a faithful reproduction of either
  paper's exact algorithm.
"""
    )

    emit("=" * 70)
    emit("SCOPE AND HONEST LIMITATIONS")
    emit("=" * 70)
    emit(
        """
  - Scale: hundreds of nodes (not the 2,000-node / 10,000-block scale
    originally asserted on the site/README before this benchmark).
    "Rounds" are abstract behavioral ticks, not real Bitcoin block
    intervals; no block propagation, consensus, mempool, or peer churn is
    actually simulated.
  - CTSEngine.PeerRecord.quarantined never resets to False once set, even
    if the score later recovers above the 0.35 reinstatement threshold
    referenced in configs/monitoring.yaml. The paper's discussion section
    describes mitigation as "reversible by design"; the reference
    scoring engine as it exists in this repository does not currently
    implement that reversal. This benchmark reports quarantine status as
    measured, not as this harness's assumption.
  - PeerRecord.stake_age_blocks is stored but never read by CTSEngine's
    own scoring path; this harness's economic signal is applied only
    through the existing stake_age_bonus reward event, not through a
    stake_age-aware formula that doesn't exist in the reference code.
  - "Computational overhead" measures IsolationGuard.accept_connection()
    wall-clock cost on this machine, not real network consensus latency
    -- there is no consensus loop, network I/O, or multi-node simulation
    in this repository to measure that against.
  - Attack behavior is scripted per-scenario (one attack_type per trial),
    not adaptive/multi-vector; a real adversary mixing attack types or
    adapting to observed quarantine events is out of scope here.
  - The intensity=1.0 (fully active adversary) condition produces very
    clean separation (TPR at or near 100%, FPR near 0%) because the
    scripted attack behaviors trip PENALTY_WEIGHTS entries that are
    already calibrated aggressively in the existing cts_engine.py
    (e.g. eclipse_attempt = 0.40, more than double the quarantine
    threshold in a single event) -- this is a direct, measured
    consequence of weights already present in the reference
    implementation, not tuning performed for this benchmark. The
    intensity=0.5 condition (roughly half of Sybils dormant) is reported
    alongside it specifically so the results are not read as "detection
    is always ~100%" -- dormant Sybils that never behave maliciously and
    hold no distinguishing graph position are, correctly, often not
    detected by a behavioral+graph signal.
  - No adversarial evasion against the CTS/graph scoring itself (e.g. an
    attacker deliberately diversifying Sybil subnets or timing behavior
    to mimic the honest jitter distribution) is modeled.
  - Dormant Sybils (intensity<1.0, non-attacking share) are detected at a
    rate close to (1 - dormant_fraction), i.e. close to 0% additional
    detection from the graph signal alone. CTSEngine.update_centrality()
    contributes at most +/-0.10 to a peer's score (a fixed 10% weight
    hardcoded in cts_engine.py), which cannot by itself move a
    dormant Sybil's score from the neutral starting point (0.5) down to
    the 0.20 quarantine threshold (a 0.30 gap). In this harness, dormant
    Sybils are essentially caught only if they also happen to receive a
    behavioral penalty; a purely graph-based dormant-Sybil signal is not,
    on this evidence, strong enough on its own to trigger quarantine.
  - The graph-only BASELINE's TPR/FPR are mechanically constrained by the
    fixed 20th-percentile flagging quota chosen for it, interacting with
    each trial's actual Sybil prevalence: at ratio=0.10 (Sybils are 10%
    of the network but the quota flags 20%), the baseline's FPR of ~11%
    is arithmetically close to (20%-10%)/90% -- it must flag honest
    nodes to fill its quota. At ratio=0.30 (Sybils exceed the 20% quota),
    baseline TPR caps near 20/30 = 66.7% because the quota cannot flag
    more than 20% of all nodes regardless of how many are actually
    Sybil. These are properties of the fixed-percentile baseline
    methodology, not a claim that graph-only detection "gets harder" at
    higher density in some deeper sense -- a percentile recalibrated per
    density would score differently. This is disclosed rather than
    tuned away because a real defender does not know the true Sybil
    density in advance either.
"""
    )

    emit("=" * 70)
    emit("REPRODUCTION")
    emit("=" * 70)
    emit(
        "  python scripts/run_simulation.py --nodes 300 --trials 20 "
        "--sybil-ratios 0.10,0.20,0.30 --scenario all --intensities 1.0,0.5\n"
        "  Requires: networkx (see requirements.txt). No GPU, no external services."
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nFull report written to: {output_path}")


if __name__ == "__main__":
    main()
