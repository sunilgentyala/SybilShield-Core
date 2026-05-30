# SybilShield-Core: Formal Threat Model

Version: 1.0
Framework: STRIDE + DREAD composite scoring
Scope: Permissionless P2P blockchain networks (Bitcoin-like and Ethereum-like architectures)

---

## 1. Threat Actor Definition

**Primary Adversary:** A rational, resource-constrained attacker controlling k Sybil identities (k >> 1) on a network of n honest nodes, where the attacker's cost function C(k) grows sub-linearly relative to attack utility U(k). The attacker's goal is to maximize influence over one or more of: consensus outcome, data state, or network availability.

**Adversary Capabilities:**
- Full control of all k Sybil node key pairs and IP addresses
- Ability to selectively relay or withhold blocks and transactions
- Ability to craft syntactically valid but strategically timed protocol messages
- No ability to break cryptographic primitives (ECC, SHA-256/Keccak-256)
- No majority of honest stake or hashrate (sub-threshold attacker)

---

## 2. Attack Vector 1: Consensus Hijacking / 51% Masking

### Mechanics

In Nakamoto-style Proof-of-Work consensus, finality is probabilistic. A block at depth d has reversion probability approximately 2^(-d) for an honest-majority network. Sybil nodes do not need to exceed 50% of hashrate network-wide; they need only to exceed 50% of the effective vote weight as seen by a subset of honest nodes.

The attack proceeds in three phases:

**Phase 1 - Infiltration.** The attacker registers k identities with minimal staking cost (in PoS variants) or zero cost (in pure P2P systems). Each identity occupies peer connection slots of honest nodes. With k identities, the attacker can saturate the peer lists of a target node T if k >= max_connections(T).

**Phase 2 - Vote Dilution.** In committee-based BFT consensus (Tendermint, HotStuff variants), voting weight is often distributed across registered validators. If the attacker controls k_v of n_v validators such that k_v / n_v > 1/3, Byzantine fault tolerance is violated and consensus can be stalled or equivocated.

**Phase 3 - Masking.** The attacker uses Sybil nodes to selectively suppress propagation of competing blocks. By refusing to relay a valid block B_honest from miner M_honest to target nodes, the attacker creates a localized view where B_honest does not exist. Target nodes then accept the attacker's alternative chain, experiencing a localized 51% condition without the attacker controlling global hashrate.

**Formal Condition:**
Let R(B) be the relay acceptance probability for block B. If Sybil nodes occupy all k peer slots of T, then R(B_honest) approaches 0 for node T regardless of global network topology.

### STRIDE Classification: Spoofing, Tampering, Elevation of Privilege
### DREAD Score: Damage=9, Reproducibility=7, Exploitability=8, Affected Users=9, Discoverability=6 | Total: 7.8/10

---

## 3. Attack Vector 2: Network Partitioning and Eclipse Attacks

### Mechanics

An Eclipse attack is a targeted instance of Sybil-assisted network partitioning. The attacker's objective is to monopolize all inbound and outbound peer connections of a single target node T, severing T from all honest peers.

**Connection Slot Exhaustion.** Bitcoin Core (and similar implementations) maintains a maximum of 8 outbound and 117 inbound connections by default. The attacker creates k >= 125 Sybil identities distributed across multiple /16 IP subnets (to bypass IP-diversity filters) and systematically fills T's connection table entries by cycling through repeated connection attempts. Addresses are injected into T's `addr` database via legitimate-appearing `ADDR` gossip messages relayed through already-connected Sybil nodes.

**Peer Table Poisoning.** The Bitcoin Core `addrman` structure organizes known peer addresses into "tried" and "new" tables partitioned by /16 subnet. An attacker with control over multiple subnets can fill both tables with Sybil addresses over time, ensuring that after the next node restart or connection churn event, T reconnects exclusively to Sybil peers.

**Consequences of Successful Eclipse:**
- T receives only attacker-crafted chain views; double-spend attacks against T become trivially feasible
- T's blocks are never propagated to the honest network; T's mining revenue is eliminated
- T can be fed a stale chain tip, causing T to build on an orphaned branch
- All transaction confirmations received by T are adversary-controlled

**Latency Fingerprinting.** Sybil nodes operating from coordinated infrastructure exhibit systematically lower inter-message latency variance than geographically distributed honest nodes. This disparity constitutes a detectable passive signal available to the monitoring layer without requiring any active probing.

### STRIDE Classification: Spoofing, Denial of Service, Information Disclosure
### DREAD Score: Damage=10, Reproducibility=6, Exploitability=7, Affected Users=7, Discoverability=5 | Total: 7.0/10

---

## 4. Attack Vector 3: Data Poisoning in DFL and Oracle Feeds

### Mechanics

Decentralized Federated Learning (DFL) aggregates model updates from distributed participants. Oracle networks aggregate off-chain data from multiple feed providers. Both architectures inherit Sybil vulnerability at the aggregation layer.

**DFL Model Poisoning.** In a DFL round with n participants, the aggregation function (typically FedAvg: w_global = sum(n_i * w_i) / N) weights updates by local dataset size n_i. A Sybil attacker controlling k identities, each reporting a fabricated n_i, can shift w_global arbitrarily. Byzantine-resilient aggregation rules (Krum, coordinate-wise median, Bulyan) provide partial mitigation but are defeated when the attacker fraction exceeds their designed tolerance, typically f < n/3 or f < n/4.

The attacker crafts "inner product manipulation" updates: gradients that appear benign under cosine similarity checks but shift the global model toward a targeted backdoor behavior after aggregation.

**Oracle Feed Manipulation.** A decentralized oracle (Chainlink-style) aggregates price or event data from k_o independent reporters, taking a weighted median. If the attacker controls k_s reporters such that k_s / k_o > 0.5 (or exceeds the deviation threshold), the reported value deviates from ground truth by an attacker-controlled delta. In financial derivatives contracts, a delta of 0.3% over a $100M notional position yields $300K adversarial profit per oracle update cycle.

**Sybil-Amplified Gradient Inversion.** Beyond poisoning, Sybil nodes in DFL can reconstruct training data from gradient updates shared by honest nodes, violating data privacy guarantees even when differential privacy noise is applied below a threshold epsilon.

### STRIDE Classification: Tampering, Information Disclosure, Elevation of Privilege
### DREAD Score: Damage=9, Reproducibility=8, Exploitability=7, Affected Users=8, Discoverability=4 | Total: 7.2/10

---

## 5. Attack Vector 4: Resource Exhaustion

### Mechanics

**Mempool Flooding.** Each node maintains a mempool bounded by memory (default: 300 MB in Bitcoin Core). Sybil nodes broadcast a continuous stream of syntactically valid, low-fee transactions. Because these transactions pass signature validation, they consume mempool memory until legitimate transactions are evicted. The cost to the attacker per evicted legitimate transaction approaches the minimum relay fee, currently on the order of satoshis per byte.

**Bandwidth Degradation.** Sybil nodes issue `GETDATA` requests for blocks and transactions at rates exceeding the honest node's serving capacity. By cycling requests across k Sybil identities, the attacker can sustain a rate that saturates upstream bandwidth, increasing block propagation latency for all honest peers connected to the target. Increased propagation latency directly elevates orphan rates, reducing effective network security.

**Computational Exhaustion via Signature Spam.** In PoS systems where validator selection requires signature verification of staking credentials, Sybil nodes can submit malformed or strategically crafted credential bundles that require maximal verification computation before rejection. Each rejected credential consumes CPU cycles at the target validator.

**Cascading Orphan Amplification.** Elevated latency caused by bandwidth exhaustion increases the probability that two honest miners find valid blocks nearly simultaneously, producing competing chains. The orphan rate increase reduces effective hashrate security proportionally.

### STRIDE Classification: Denial of Service
### DREAD Score: Damage=7, Reproducibility=9, Exploitability=8, Affected Users=9, Discoverability=8 | Total: 8.2/10

---

## 6. Composite Risk Matrix

| Attack Vector              | DREAD | Likelihood | Priority |
|----------------------------|-------|------------|----------|
| Resource Exhaustion        | 8.2   | High       | P1       |
| Consensus Hijacking        | 7.8   | Medium     | P1       |
| Data Poisoning (DFL)       | 7.2   | Medium     | P2       |
| Eclipse / Partitioning     | 7.0   | Medium     | P2       |

---

## 7. Mitigation Mapping

| Attack Vector          | Primary Mitigation                     | Module                          |
|------------------------|----------------------------------------|---------------------------------|
| Consensus Hijacking    | CTS quorum weight reduction            | src/mitigation/quorum/          |
| Eclipse Attack         | Peer list diversity enforcement        | src/mitigation/isolation/       |
| DFL Poisoning          | Byzantine-robust aggregation + CTS     | analysis/ml_classifier/         |
| Resource Exhaustion    | Rate limiting + stake-weighted access  | src/mitigation/penalty/         |
