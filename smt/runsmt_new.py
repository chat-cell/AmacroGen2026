#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in amacro_router/."""

from amacro_router.data.types import (
    Pin,
    Node,
    GridSpec,
    NetSpec,
    ConstraintSpec,
    CaseSpec,
    SymmetrySpec,
    Resource,
    RoutingGraph,
    RouterOptions,
    BuildModuleTiming,
    PassRecord,
    RouteSolution,
    ValidationReport,
    RouteResult,
    PackageWriteResult,
    ModelArtifacts,
)
from amacro_router.data.inputs import (
    _data_lines,
    _parse_grid,
    _parse_nets,
    _parse_constraints,
    load_case,
)
from amacro_router.data.graph import (
    mirror_pin,
    mirror_resource,
    build_routing_graph,
)
from amacro_router.data.symmetry import (
    _mirrored_pin_counter,
    infer_symmetry,
)
from amacro_router.encoding.helpers import (
    _symbol,
    _bool_sum,
    _incident_resources,
    _lmax,
)
from amacro_router.encoding.model import (
    build_model,
)
from amacro_router.routing.validation import (
    _connected_pin_check,
    _non_pin_leaves,
    validate_solution,
    _empty_validation,
)
from amacro_router.routing.solver import (
    _status_text,
    _extract_solution,
    _solve_pass,
    route_case,
    check_floating_resource_admissibility,
)
from amacro_router.results.plotting import (
    rendering_metadata,
    render_solution,
)
from amacro_router.results.writer import (
    write_result_package,
)
from amacro_router.cli.route import (
    _argument_parser,
    main,
)

__all__ = [
    "Pin",
    "Node",
    "GridSpec",
    "NetSpec",
    "ConstraintSpec",
    "CaseSpec",
    "SymmetrySpec",
    "Resource",
    "RoutingGraph",
    "RouterOptions",
    "BuildModuleTiming",
    "PassRecord",
    "RouteSolution",
    "ValidationReport",
    "RouteResult",
    "PackageWriteResult",
    "ModelArtifacts",
    "_data_lines",
    "_parse_grid",
    "_parse_nets",
    "_parse_constraints",
    "load_case",
    "mirror_pin",
    "mirror_resource",
    "build_routing_graph",
    "_mirrored_pin_counter",
    "infer_symmetry",
    "_symbol",
    "_bool_sum",
    "_incident_resources",
    "_lmax",
    "build_model",
    "_connected_pin_check",
    "_non_pin_leaves",
    "validate_solution",
    "_empty_validation",
    "_status_text",
    "_extract_solution",
    "_solve_pass",
    "route_case",
    "check_floating_resource_admissibility",
    "rendering_metadata",
    "render_solution",
    "write_result_package",
    "_argument_parser",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
