# SybilShield-Core

**A modular, multi-layer anti-Sybil framework for permissionless peer-to-peer blockchain networks.**

[![Paper](https://img.shields.io/badge/IEEE-ICICDS%202026-blue)](https://icicds.com/2026/) [![Site](https://img.shields.io/badge/site-github.io-4fd1c5)](https://sunilgentyala.github.io/SybilShield-Core/)

SybilShield-Core implements a Composite Trust Scoring (CTS) engine that fuses behavioral telemetry, social-graph topology analysis, and economic commitment signals to detect and isolate Sybil entities without relying on Proof-of-Work expenditure or centralized identity authorities.

Project site: **[sunilgentyala.github.io/SybilShield-Core](https://sunilgentyala.github.io/SybilShield-Core/)**

---

## Why SybilShield-Core

Sybil attacks are the structural weak point of every permissionless network: an adversary who can mint pseudonymous identities for near-zero cost can distort consensus, partition honest peers, and poison decentralized data pipelines, without ever breaking a single cryptographic primitive. That makes Sybil resistance a societal cybersecurity problem, not just a blockchain one, since the same identity-spoofing pattern underwrites attacks on federated learning, oracle feeds, and any decentralized system that assumes "one peer, one vote."

- **Closes a gap neither Proof-of-Work nor identity authorities solve.** PoW prices out small adversaries but not well-resourced ones; centralized identity checks reintroduce the single point of failure permissionless systems exist to avoid. The Composite Trust Score (CTS) detects Sybil behavior from observable evidence instead, with no protocol-level identity friction and no trusted third party.
- **Detects what single-signal defenses miss.** Fusing behavioral telemetry, peer-graph topology, and economic commitment lifts detection above 94% at up to 40% adversary density while holding false positives below 2.1%, materially better than graph-only (SybilGuard/SybilLimit) or stake-only baselines evaluated in the same simulations.
- **Protects the systems people already depend on.** The same CTS signal extends into decentralized federated learning aggregation, cutting poisoned-model backdoor accuracy from 84.7% to 11.3% at a 30% adversary fraction, directly relevant to any organization running federated or oracle-fed ML on shared infrastructure.
- **Reversible by design.** Mitigation is tiered (monitoring to quorum-weight reduction to quarantine) and recoverable as evidence changes, avoiding the permanent-ban incentive that lets attackers weaponize false reports against honest peers.
- **Open and reproducible.** MIT-licensed reference implementation, simulation harness, and unit tests are public, so the detection-rate and overhead claims can be independently verified rather than taken on faith.

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
│   │   ├── identity/         # Peer identity management, key binding, commitment schemes
│   │   ├── scoring/          # Composite Trust Score engine, decay functions
│   │   └── consensus/        # Consensus weight assignment, quorum arbitration
│   ├── monitoring/
│   │   ├── behavior/         # Block relay timing, mempool flood detection
│   │   ├── graph/            # Peer topology snapshots, clustering coefficient probes
│   │   └── telemetry/        # Metrics collection, event bus publisher
│   └── mitigation/
│       ├── quorum/           # Dynamic quorum weight reduction for flagged nodes
│       ├── penalty/          # Stake slashing and connection throttling
│       └── isolation/        # Eclipse prevention, peer list sanitization
├── simulation/
│   ├── network/              # Synthetic P2P network topology generators
│   ├── adversary/            # Sybil attack scenario implementations
│   └── scenarios/            # Parameterized test scenarios (scale, intensity)
├── analysis/
│   ├── graph_engine/         # NetworkX / igraph wrappers, SybilRank integration
│   ├── ml_classifier/        # Behavioral anomaly classifier (GNN / isolation forest)
│   └── oracle/               # Oracle feed integrity monitoring
├── tests/
│   ├── unit/                 # Component-level tests
│   ├── integration/          # Cross-layer pipeline tests
│   └── simulation/           # Full-network adversarial simulation harness
├── docs/
│   ├── threat_model/         # Formal threat model (STRIDE + DREAD scoring)
│   ├── architecture/         # Architecture decision records
│   └── api/                  # Module API reference
├── configs/                  # Default and environment-specific configuration YAML
├── scripts/                  # Simulation runners, data export, graph visualization
└── artifacts/
    ├── benchmarks/           # Latency, throughput, detection rate results
    ├── figures/              # Generated plots and topology diagrams
    └── logs/                 # Simulation run logs
```

---

## Quick Start

```bash
git clone https://github.com/sunilgentyala/SybilShield-Core.git
cd SybilShield-Core
pip install -e ".[dev]"

# Run a Sybil simulation (50-node network, 30% adversary ratio)
python scripts/run_simulation.py --nodes 50 --sybil-ratio 0.30 --scenario eclipse

# Run unit tests
pytest tests/unit/ -v
```

---

## Related Paper

**SybilShield-Core: A Composite Trust Scoring Framework for Sybil Attack Mitigation in Permissionless Blockchain Networks**

Sunil Gentyala (IEEE Senior Member, HCLTECH America Inc., Dallas TX) |
K Sanjeevaiah (Malla Reddy Engineering College for Women, Hyderabad, India) |
Suresh Kumar Darisi (Rocket Software Inc., Dallas TX)

**Accepted at [IEEE ICICDS 2026](https://icicds.com/2026/)** (Paper ID ICICDS-690). The manuscript is not publicly available prior to publication to comply with IEEE copyright policy. A DOI and citation will be added here once the proceedings are indexed by IEEE Xplore.



---

## License

MIT
