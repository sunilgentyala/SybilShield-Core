"""
Graph topology analysis: clustering coefficient, SybilRank-style trust propagation,
and peer connection diversity scoring.

Sybil subgraphs exhibit characteristically high intra-cluster edge density
and low inter-cluster betweenness, detectable via standard graph metrics.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


class PeerGraph:
    """Lightweight directed graph representation of the P2P peer topology.

    Nodes are peer IDs; edges represent active connections. The graph is
    updated incrementally as connections open and close.
    """

    def __init__(self) -> None:
        self._adj: dict[str, set[str]] = defaultdict(set)
        self._reverse_adj: dict[str, set[str]] = defaultdict(set)

    def add_edge(self, src: str, dst: str) -> None:
        self._adj[src].add(dst)
        self._reverse_adj[dst].add(src)

    def remove_edge(self, src: str, dst: str) -> None:
        self._adj[src].discard(dst)
        self._reverse_adj[dst].discard(src)

    def neighbors(self, peer_id: str) -> set[str]:
        return self._adj.get(peer_id, set())

    def in_degree(self, peer_id: str) -> int:
        return len(self._reverse_adj.get(peer_id, set()))

    def out_degree(self, peer_id: str) -> int:
        return len(self._adj.get(peer_id, set()))

    def local_clustering_coefficient(self, peer_id: str) -> float:
        """Compute the local clustering coefficient for a node.

        High LCC within a subgraph indicates tightly connected clusters,
        a hallmark of Sybil identity groups sharing infrastructure.
        """
        neighbors = self._adj.get(peer_id, set())
        k = len(neighbors)
        if k < 2:
            return 0.0
        edges_among_neighbors = sum(
            1 for u in neighbors for v in neighbors if v in self._adj.get(u, set())
        )
        return edges_among_neighbors / (k * (k - 1))

    def sybilrank_scores(self, seed_nodes: set[str], iterations: int = 20) -> dict[str, float]:
        """Approximate SybilRank trust propagation from a set of trusted seed nodes.

        Trust flows from seeds outward. Nodes receiving trust primarily from
        high-LCC neighborhoods are penalized via a clustering discount.

        Args:
            seed_nodes: Verified honest peers used as trust anchors.
            iterations: Number of random-walk iterations.

        Returns:
            Dict mapping peer_id to a trust propagation score in [0, 1].
        """
        all_nodes = set(self._adj.keys()) | set(self._reverse_adj.keys())
        trust: dict[str, float] = {n: (1.0 if n in seed_nodes else 0.0) for n in all_nodes}

        for _ in range(iterations):
            new_trust: dict[str, float] = defaultdict(float)
            for node, score in trust.items():
                neighbors = self._adj.get(node, set())
                if not neighbors:
                    continue
                share = score / len(neighbors)
                for nb in neighbors:
                    lcc = self.local_clustering_coefficient(nb)
                    discount = 1.0 - (0.5 * lcc)  # Penalize high-cluster neighbors
                    new_trust[nb] += share * discount
            # Normalize
            total = sum(new_trust.values()) or 1.0
            trust = {n: v / total for n, v in new_trust.items()}

        return trust

    def subnet_diversity_score(self, peer_id: str, peer_subnets: dict[str, str]) -> float:
        """Return the fraction of neighbors from distinct /16 subnets.

        A node whose neighbors all share the same subnet prefix is likely
        operating Sybil identities from a single infrastructure provider.
        """
        neighbors = self._adj.get(peer_id, set())
        if not neighbors:
            return 1.0
        subnets = {peer_subnets.get(nb, "unknown") for nb in neighbors}
        return len(subnets) / len(neighbors)
