"""Shared case, model, solution and execution record types."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Optional
import z3



Pin = tuple[int, int]


Node = tuple[int, int, int]


# Routing grid dimensions: rows and columns.
@dataclass(frozen=True)
class GridSpec:
    rows: int
    cols: int


# Net name and pin coordinates; the first pin is the flow source.
@dataclass(frozen=True)
class NetSpec:
    name: str
    pins: tuple[Pin, ...]


# Explicit symmetry relationships, length slack and resource conflicts.
@dataclass(frozen=True)
class ConstraintSpec:
    self_nets: frozenset[str] = frozenset()
    pairs: tuple[tuple[str, str], ...] = ()
    ordinary: frozenset[str] = frozenset()
    length_slack: int = 8
    conflict_sets: tuple[tuple["Resource", ...], ...] = ()


# Complete case input shared by model construction and validation.
@dataclass(frozen=True)
class CaseSpec:
    name: str
    path: Path
    grid: GridSpec
    nets: dict[str, NetSpec]
    constraints: ConstraintSpec = field(default_factory=ConstraintSpec)


# Classified self-symmetric nets, mirrored pairs and ordinary nets.
@dataclass(frozen=True)
class SymmetrySpec:
    self_nets: tuple[str, ...]
    pairs: tuple[tuple[str, str], ...]
    ordinary: tuple[str, ...]


# Unique location of a horizontal segment, vertical segment or via.
@dataclass(frozen=True, order=True)
class Resource:
    kind: str
    layer: int
    x: int
    y: int


# Resources and adjacency on nodes identified by (layer, x, y).
@dataclass(frozen=True)
class RoutingGraph:
    grid: GridSpec
    nodes: tuple[Node, ...]
    resources: tuple[Resource, ...]
    endpoints: dict[Resource, tuple[Node, Node]]
    resource_by_endpoints: dict[frozenset[Node], Resource]
    adjacency: dict[Node, tuple[tuple[Node, Resource], ...]]


# Solver switches and per-pass time budgets in milliseconds.
@dataclass(frozen=True)
class RouterOptions:
    symmetry: bool = True
    fallback: bool = True
    length_bound: bool = True
    resource_upper_binding: bool = True
    no_dangling_branches: bool = True
    length_slack: Optional[int] = None
    strict_timeout_ms: int = 300_000
    fallback_timeout_ms: int = 300_000


# Accumulated construction time and assertion count for a constraint module.
@dataclass(frozen=True)
class BuildModuleTiming:
    seconds: float
    assertions_added: int


# Status, timing, model size and UNKNOWN reason for one solver pass.
@dataclass(frozen=True)
class PassRecord:
    status: str
    build_seconds: float
    solve_seconds: float
    extract_seconds: float
    build_modules: dict[str, BuildModuleTiming]
    reason_unknown: str
    variable_count: int
    assertion_count: int


# Resources, commodity flows and pin accesses extracted from a SAT model.
@dataclass(frozen=True)
class RouteSolution:
    resources: dict[str, tuple[Resource, ...]]
    flows: dict[str, tuple[tuple[int, Node, Node], ...]]
    accesses: dict[str, tuple[int, ...]]


# Abstract-grid checks; these do not establish commercial-PDK signoff.
@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    all_pins_connected: bool
    no_shared_resources: bool
    abstract_drc_satisfied: bool
    no_zero_flow_resources: bool
    flow_resource_consistent: bool
    flow_conservation_satisfied: bool
    no_dangling_branches: bool
    non_pin_leaves_by_net: dict[str, tuple[Node, ...]]
    symmetry_satisfied: bool
    length_bound_satisfied: bool
    pin_access_satisfied: bool
    cycle_rank_by_net: dict[str, int]
    errors: tuple[str, ...]


# Both solver passes, the final solution and its validation report.
@dataclass(frozen=True)
class RouteResult:
    status: str
    pass1: PassRecord
    pass2: Optional[PassRecord]
    used_fallback: bool
    solution: Optional[RouteSolution]
    validation: ValidationReport
    validation_seconds: float
    graph: RoutingGraph
    symmetry: SymmetrySpec


# Output directory and image generation timing.
@dataclass(frozen=True)
class PackageWriteResult:
    run_dir: Path
    render_seconds: float


# Solver and variable mappings used for extraction and model checks.
@dataclass
class ModelArtifacts:
    solver: z3.Solver
    graph: RoutingGraph
    symmetry: SymmetrySpec
    use: dict[tuple[str, Resource], z3.BoolRef]
    flow: dict[tuple[str, int, Node, Node], z3.BoolRef]
    access: dict[tuple[str, int, int], z3.BoolRef]
    variable_count: int
    build_modules: dict[str, BuildModuleTiming]
