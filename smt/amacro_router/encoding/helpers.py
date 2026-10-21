"""Small expressions and bounds shared by encoding and validation."""
from __future__ import annotations

from typing import Iterable
import re
import z3

from amacro_router.data.types import (
    NetSpec,
    Node,
    Resource,
    RoutingGraph,
)


# Convert a name to an SMT variable-name fragment.
def _symbol(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))


# Sum Boolean values as integers for flow and cardinality constraints.
def _bool_sum(values: Iterable[z3.BoolRef]) -> z3.ArithRef:
    return z3.Sum([z3.If(value, 1, 0) for value in values])


# Return all physical resources incident to a node.
def _incident_resources(graph: RoutingGraph, node: Node) -> tuple[Resource, ...]:
    return tuple(resource for _, resource in graph.adjacency[node])


# Bound resource count using pin HPWL, pin count and configured slack.
def _lmax(net: NetSpec, slack: int) -> int:
    xs = [pin[0] for pin in net.pins]
    ys = [pin[1] for pin in net.pins]
    hpwl = max(xs) - min(xs) + max(ys) - min(ys)
    return hpwl + 2 * max(0, len(net.pins) - 2) + slack
