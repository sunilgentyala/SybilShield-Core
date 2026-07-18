"""
Sybil adversary injection into a synthetic honest topology.

Attaches a block of Sybil identities to an honest NetworkTopology
(simulation/network/topology.py) following the standard "attack edge"
model used in the Sybil-detection literature (Yu et al., SybilGuard,
2008; Danezis & Mittal, SybilInfer, 2009): the Sybil region is densely
interconnected internally (shared botnet / hosting infrastructure) and
attaches to the honest region through a small number of "attack edges"
-- honest peers that the adversary has socially engineered or bribed
into connecting to Sybil identities.

This is a simplified stand-in for the full SybilGuard/SybilLimit random
walk protocol, used here only to construct a topology for evaluating
SybilShield-Core's own detection pipeline and, separately, a
graph-propagation-only baseline (see scripts/run_simulation.py). It is
NOT a reimplementation of the SybilGuard/SybilLimit algorithms.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import networkx as nx

from simulation.network.topology import NetworkTopology


@dataclass
class InjectedNetwork:
    """Combined honest + Sybil topology plus ground-truth labels."""

    graph: "nx.Graph"
    honest_ids: list[str]
    sybil_ids: list[str]
    subnets: dict[str, str]
    attack_edges: list[tuple[str, str]]

    @property
    def all_ids(self) -> list[str]:
        return self.honest_ids + self.sybil_ids

    def is_sybil(self, node_id: str) -> bool:
        return node_id in set(self.sybil_ids)


def inject_sybils(
    topology: NetworkTopology,
    sybil_ratio: float,
    seed: int = 42,
    sybil_subnet_count: int = 4,
    sybil_internal_degree: int = 6,
    attack_edges_per_100_sybils: float = 4.0,
) -> InjectedNetwork:
    """Inject a Sybil region into an honest topology.

    Args:
        topology: Honest network topology to attach Sybils to.
        sybil_ratio: Sybil nodes as a fraction of the TOTAL post-injection
            network (e.g. 0.30 means Sybils are 30% of all nodes).
        seed: RNG seed.
        sybil_subnet_count: Number of distinct /16 subnets the Sybil
            identities are drawn from (small, modeling cheap shared
            hosting -- the realistic economic signature of a Sybil farm).
        sybil_internal_degree: Target internal degree among Sybil nodes
            (random-graph edges within the Sybil region).
        attack_edges_per_100_sybils: Number of edges connecting the Sybil
            region to random honest nodes, per 100 Sybil identities. Kept
            small, consistent with the attack-edge assumption in the
            SybilGuard/SybilLimit line of work.

    Returns:
        InjectedNetwork with the combined graph and ground-truth labels.
    """
    rng = random.Random(seed)
    n_honest = len(topology.node_ids)

    if not (0.0 <= sybil_ratio < 1.0):
        raise ValueError("sybil_ratio must be in [0, 1)")

    n_sybil = int(round(n_honest * sybil_ratio / (1.0 - sybil_ratio)))
    n_sybil = max(1, n_sybil)
    sybil_ids = [f"sybil_{i:05d}" for i in range(n_sybil)]

    graph = topology.graph.copy()
    graph.add_nodes_from(sybil_ids)

    # Sybil identities share a small pool of subnets (cheap shared infra).
    subnet_pool = [f"10.{13 + i}.0" for i in range(max(1, sybil_subnet_count))]
    subnets = dict(topology.subnets)
    for sid in sybil_ids:
        subnets[sid] = rng.choice(subnet_pool)

    # Dense internal Sybil connectivity (Erdos-Renyi with target mean degree).
    if n_sybil > 1:
        p = min(1.0, sybil_internal_degree / max(1, n_sybil - 1))
        sybil_subgraph = nx.gnp_random_graph(n_sybil, p, seed=seed)
        relabel = {i: sybil_ids[i] for i in range(n_sybil)}
        sybil_subgraph = nx.relabel_nodes(sybil_subgraph, relabel)
        graph.add_edges_from(sybil_subgraph.edges())

    # A small number of attack edges from Sybil nodes to random honest nodes.
    n_attack_edges = max(2, int(round(n_sybil * attack_edges_per_100_sybils / 100.0)))
    attack_edges: list[tuple[str, str]] = []
    for _ in range(n_attack_edges):
        s = rng.choice(sybil_ids)
        h = rng.choice(topology.node_ids)
        graph.add_edge(s, h)
        attack_edges.append((s, h))

    return InjectedNetwork(
        graph=graph,
        honest_ids=list(topology.node_ids),
        sybil_ids=sybil_ids,
        subnets=subnets,
        attack_edges=attack_edges,
    )
