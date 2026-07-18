"""
Synthetic P2P network topology generation.

Builds an honest-peer connection graph using a Barabasi-Albert
preferential-attachment model (networkx), which produces a degree
distribution broadly consistent with measured Bitcoin-style gossip
network topologies, and assigns each honest peer an IP address drawn
from a diverse pool of /16 subnets.

This module intentionally does not model real network latency, NAT
traversal, or churn; it produces a static connection graph and subnet
assignment used as the substrate for the Sybil-injection and detection
pipeline in simulation/scenarios/.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import networkx as nx


@dataclass
class NetworkTopology:
    """A generated P2P topology: an undirected graph plus subnet assignment."""

    graph: "nx.Graph"
    node_ids: list[str]
    subnets: dict[str, str] = field(default_factory=dict)  # node_id -> "/16" prefix string

    def edges(self) -> list[tuple[str, str]]:
        return list(self.graph.edges())


def build_honest_topology(
    n_honest: int,
    m: int = 4,
    seed: int = 42,
    n_subnets: int = 120,
) -> NetworkTopology:
    """Build a Barabasi-Albert honest peer graph with diverse subnet assignment.

    Args:
        n_honest: Number of honest peers.
        m: Number of edges each new node attaches with (BA parameter).
        seed: RNG seed for reproducibility.
        n_subnets: Size of the /16 subnet pool honest peers are drawn from
            (a large pool models genuine infrastructure diversity).

    Returns:
        NetworkTopology with node ids "honest_0000".."honest_{n-1}".
    """
    if n_honest < m + 1:
        # networkx requires n > m for barabasi_albert_graph
        m = max(1, n_honest - 1)

    ba_graph = nx.barabasi_albert_graph(n=n_honest, m=m, seed=seed)
    node_ids = [f"honest_{i:05d}" for i in range(n_honest)]
    relabel = {i: node_ids[i] for i in range(n_honest)}
    graph = nx.relabel_nodes(ba_graph, relabel)

    rng = random.Random(seed)
    subnet_pool = [f"172.{16 + i}.0" for i in range(n_subnets)]
    subnets = {}
    for node in node_ids:
        base = rng.choice(subnet_pool)
        subnets[node] = base

    return NetworkTopology(graph=graph, node_ids=node_ids, subnets=subnets)


def node_ip(subnet_base: str, rng: random.Random) -> str:
    """Generate a concrete IP address within a /16 subnet base string."""
    return f"{subnet_base}.{rng.randint(1, 254)}"
