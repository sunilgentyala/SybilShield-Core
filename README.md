# SybilShield-Core

**A modular, multi-layer anti-Sybil framework for permissionless peer-to-peer blockchain networks.**

[![Paper](https://img.shields.io/badge/IEEE_Xplore-Published-blue)](https://ieeexplore.ieee.org/document/11604799) [![Site](https://img.shields.io/badge/site-github.io-4fd1c5)](https://sunilgentyala.github.io/SybilShield-Core/)

SybilShield-Core implements a Composite Trust Scoring (CTS) engine that fuses behavioral telemetry, social-graph topology analysis, and economic commitment signals to detect and isolate Sybil entities without relying on Proof-of-Work expenditure or centralized identity authorities.

Project site: **[sunilgentyala.github.io/SybilShield-Core](https://sunilgentyala.github.io/SybilShield-Core/)**

---

## Why SybilShield-Core

Sybil attacks are the structural weak point of every permissionless network: an adversary who can mint pseudonymous identities for near-zero cost can distort consensus, partition honest peers, and poison decentralized data pipelines, without ever breaking a single cryptographic primitive. That makes Sybil resistance a societal cybersecurity problem, not just a blockchain one, since the same identity-spoofing pattern underwrites attacks on federated learning, oracle feeds, and any decentralized system that assumes "one peer, one vote."

- **Closes a gap neither Proof-of-Work nor identity authorities solve.** PoW prices out small adversaries but not well-resourced ones; centralized identity checks reintroduce the single point of failure permissionless systems exist to avoid. The Composite Trust Score (CTS) detects Sybil behavior from observable evidence instead, with no protocol-level identity friction and no trusted third party.
- **Beats a graph-only baseline, measured.** On a real, runnable simulation (`scripts/run_simulation.py`, n=300 honest nodes, 20 trials/config), the composite CTS pipeline reaches 100% TPR / 0.00% FPR against an actively attacking Sybil population across 10-30% adversary density, versus 65.9-100% TPR / 0.0-11.0% FPR for a simplified graph-propagation-only baseline on the identical topology. See [`simulation/results/sybil_detection_results.txt`](simulation/results/sybil_detection_results.txt) for the full numbers, methodology, and honest limitations (including why a half-dormant Sybil population is detected at only ~48-51%).
- **FL poisoning defense is wired but not yet benchmarked.** The `oracle_deviation` penalty event exists and is exercised by the same simulation, but no FL aggregation module or model-accuracy/backdoor-resistance benchmark exists in this repo yet. An earlier claim of cutting poisoned-model backdoor accuracy from 84.7% to 11.3% was not backed by any runnable code and has been removed rather than replaced with another unverified number.
- **Mitigation is tiered; automatic reversal is a known gap.** Mitigation escalates (monitoring to quorum-weight reduction to quarantine), but as measured in this benchmark, the reference `CTSEngine`'s quarantine flag is currently a one-way latch — it does not automatically reinstate a peer even after the score recovers above the reinstatement threshold in `configs/monitoring.yaml`. This is disclosed, not fixed silently.
- **Open and reproducible.** MIT-licensed reference implementation, a real simulation harness, and unit tests are public, so the detection-rate and overhead numbers above can be independently re-run and verified rather than taken on faith.

---

## Architecture Overview

The framework is organized around three separable engine layers, each independently testable and replaceable:

**Layer 1 - Identity & Scoring (`src/core/`)**
Assigns each peer a dynamic trust score derived from stake age, behavioral consistency, and graph-theoretic centrality metrics. Scoring is deterministic and auditable.

**Layer 2 - Monitoring (`src/monitoring/`)**
Collects real-time telemetry: block relay timing, mempool propagation patterns, peer connection churn, and voting deviations. Feeds the scoring engine continuously.

**Layer 3 - Mitigation (`src/mitigation/`)**
Acts on scoring thresholds: quarantine (isolation), stake penalty, and quorum weight reduction. No single mitigation primitive is applied in isolation; the engine selects a combination based on attack classification.

**Design Pattern: Layered Pipeline with Event Bus**
The core mitigation engine follows a Pipes-and-Filters pattern over an internal event bus. Each monitoring probe publishes typed events; downstream filters apply progressively stricter detection heuristics. Detection logic and enforcement logic are kept decoupled, so either layer can be upgraded or replaced without touching the other.

---

## Directory Structure

```
SybilShield-Core/
├── src/
│   ├── core/
│   │   ├── identity/         # (stub) Peer identity management, key binding, commitment schemes
│   │   ├── scoring/          # Composite Trust Score engine, decay functions -- IMPLEMENTED
│   │   └── consensus/        # (stub) Consensus weight assignment, quorum arbitration
│   ├── monitoring/
│   │   ├── behavior/         # Block relay timing, mempool flood detection -- IMPLEMENTED
│   │   ├── graph/            # Peer topology snapshots, clustering/SybilRank probes -- IMPLEMENTED
│   │   └── telemetry/        # (stub) Metrics collection, event bus publisher
│   └── mitigation/
│       ├── quorum/           # (stub) Dynamic quorum weight reduction for flagged nodes
│       ├── penalty/          # (stub) Stake slashing and connection throttling
│       └── isolation/        # Eclipse prevention, peer list sanitization -- IMPLEMENTED
├── simulation/
│   ├── network/              # Synthetic P2P topology generation (Barabasi-Albert, networkx)
│   ├── adversary/            # Sybil attack event generator (single-shot, no network model)
│   ├── scenarios/            # Sybil injection + the real detection pipeline that wires
│   │                         #   src/core, src/monitoring, src/mitigation together
│   └── results/              # Measured output of scripts/run_simulation.py
├── tests/
│   ├── unit/                 # Component-level tests
│   ├── integration/          # (empty -- no cross-layer pipeline tests yet)
│   └── simulation/           # Smoke tests for the detection pipeline
├── configs/                  # Default monitoring/scoring configuration YAML
├── scripts/
│   ├── run_simulation.py     # Real detection-pipeline simulation runner (see Quick Start)
│   └── generate_ieee_docx.py # IEEE DOCX generator (delegates to paper/build_docx.py)
└── paper/                    # DOCX build script for the IEEE manuscript (not the manuscript itself)
```

Directories marked `(stub)` above contain only an `__init__.py` -- no functional code exists there
yet. `analysis/` and `artifacts/` directories referenced in earlier versions of this README did not
exist in the repository and have been removed from this listing rather than left as aspirational
structure.

---

## Quick Start

```bash
git clone https://github.com/sunilgentyala/SybilShield-Core.git
cd SybilShield-Core
pip install -e ".[dev]"

# Run the real Sybil-detection simulation (wires src/core/scoring/cts_engine.py,
# src/mitigation/isolation/isolation_guard.py, src/monitoring/behavior/relay_monitor.py,
# and src/monitoring/graph/peer_graph.py together against a generated network).
# Small/fast smoke run:
python scripts/run_simulation.py --nodes 60 --trials 3 --scenario eclipse --sybil-ratios 0.20

# Full benchmark scale used to produce simulation/results/sybil_detection_results.txt
# (~10-13 minutes on a modern laptop):
python scripts/run_simulation.py --nodes 300 --trials 20 \
    --sybil-ratios 0.10,0.20,0.30 --scenario all --intensities 1.0,0.5

# Run unit + simulation tests
pytest tests/unit/ tests/simulation/ -v
```

Full measured results, methodology, tool versions, and honest scope limitations are in
[`simulation/results/sybil_detection_results.txt`](simulation/results/sybil_detection_results.txt).

---

## Measured Results

The numbers below are from `scripts/run_simulation.py` actually run against this repo's own
`CTSEngine`, `BehaviorMonitor`, `PeerGraph`, and `IsolationGuard` classes -- not placeholder or
projected figures. Scale: n=300 honest nodes (Barabasi-Albert topology), 20 trials per
configuration, 25 simulated behavioral rounds per trial, 3 Sybil densities (10/20/30% of the
total network) x 2 adversary-activity levels x 4 attack scenarios = 480 trials total
(~620s wall-clock on this session's WSL2/x86-64 environment).

| Metric | Composite CTS (this repo) | Graph-only baseline |
|---|---|---|
| TPR, active adversary, all densities | **100.0%** | 65.9-100.0% (density-dependent) |
| FPR, active adversary, all densities | **0.00%** | 0.0-11.0% (density-dependent) |
| TPR, half-dormant Sybil population | ~48-51% | 65.9-100.0% |
| Median detection latency (rounds) | 0-6 (attack-type dependent) | n/a |
| IsolationGuard eclipse-edge rejection | 27.5% (110/400) | n/a |
| Per-connection compute overhead | 76.14 &micro;s (vs. 0.068 &micro;s no-op) | n/a |

**This is smaller in scale than the 2,000-node / 10,000-block figures asserted in earlier
versions of this README and site**, which predated any runnable simulation. See
[`simulation/results/sybil_detection_results.txt`](simulation/results/sybil_detection_results.txt)
for the full per-scenario breakdown and, importantly, the honest limitations section covering:
why the graph-only baseline's numbers move mechanically with density (a fixed 20th-percentile
flagging quota, not a deeper property of graph-based detection), why a dormant Sybil population
is barely more detectable than chance (the graph signal alone contributes at most &plusmn;10% to
a peer's score), and a discovered gap where `CTSEngine`'s quarantine flag never automatically
resets even though the paper describes mitigation as reversible.

No federated-learning poisoning-defense benchmark (model accuracy / backdoor resistance) exists
in this repo. The `oracle_deviation` penalty event is exercised by the simulation, but there is
no FL aggregation module to benchmark against real model accuracy figures. An earlier "84.7% to
11.3% backdoor accuracy" claim was not backed by any runnable code and has been removed rather
than replaced with an equally unverified number.

---

## Related Paper

**SybilShield-Core: A Composite Trust Scoring Framework for Sybil Attack Mitigation in Permissionless Blockchain Networks**

Sunil Gentyala (IEEE Senior Member, HCLTECH America Inc., Dallas TX) |
K Sanjeevaiah (Malla Reddy Engineering College for Women, Hyderabad, India) |
Suresh Kumar Darisi (Rocket Software Inc., Dallas TX)

**Published in [IEEE Xplore](https://ieeexplore.ieee.org/document/11604799)** — IEEE ICICDS 2026 (Paper ID ICICDS-690). The manuscript is not publicly redistributable per IEEE copyright policy; see the IEEE Xplore record for the official abstract and citation.



---

## License

MIT
