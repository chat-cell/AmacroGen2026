"""Run solver passes, extract models and apply the fallback policy."""
from __future__ import annotations

from typing import Optional
import time
import z3

from amacro_router.data.types import (
    CaseSpec,
    ModelArtifacts,
    Node,
    PassRecord,
    Resource,
    RouteResult,
    RouteSolution,
    RouterOptions,
    RoutingGraph,
    SymmetrySpec,
)
from amacro_router.encoding.model import (
    build_model,
)
from amacro_router.routing.validation import (
    _empty_validation,
    validate_solution,
)


# Preserve all three Z3 outcomes; record UNKNOWN reasons separately.
def _status_text(result: z3.CheckSatResult) -> str:
    if result == z3.sat:
        return "sat"
    if result == z3.unsat:
        return "unsat"
    return "unknown"


# Extract resources, flows and accesses whose model values are true.
def _extract_solution(
    case: CaseSpec,
    artifacts: ModelArtifacts,
    model: z3.ModelRef,
) -> RouteSolution:
    resources: dict[str, tuple[Resource, ...]] = {}
    flows: dict[str, tuple[tuple[int, Node, Node], ...]] = {}
    accesses: dict[str, tuple[int, ...]] = {}
    for net_name in sorted(case.nets):
        resources[net_name] = tuple(
            resource
            for resource in artifacts.graph.resources
            if z3.is_true(model.eval(artifacts.use[(net_name, resource)], model_completion=True))
        )
        flows[net_name] = tuple(
            (commodity, u, v)
            for (name, commodity, u, v), variable in artifacts.flow.items()
            if name == net_name
            and z3.is_true(model.eval(variable, model_completion=True))
        )
        accesses[net_name] = tuple(
            pin_index
            for (name, pin_index, pattern), variable in artifacts.access.items()
            if name == net_name
            and pattern == 0
            and z3.is_true(model.eval(variable, model_completion=True))
        )
    return RouteSolution(resources=resources, flows=flows, accesses=accesses)


# Build, solve and extract a model while timing each stage separately.
def _solve_pass(
    case: CaseSpec,
    options: RouterOptions,
    *,
    require_symmetry: bool,
    timeout_ms: int,
) -> tuple[PassRecord, Optional[RouteSolution], RoutingGraph, SymmetrySpec]:
    build_start = time.perf_counter()
    artifacts = build_model(
        case,
        options,
        require_symmetry=require_symmetry,
        timeout_ms=timeout_ms,
    )
    build_seconds = time.perf_counter() - build_start
    solve_start = time.perf_counter()
    result = artifacts.solver.check()
    solve_seconds = time.perf_counter() - solve_start
    status = _status_text(result)
    # UNKNOWN need not mean timeout; retain the reason for reporting.
    reason_unknown = artifacts.solver.reason_unknown() if status == "unknown" else ""
    extract_start = time.perf_counter()
    solution = (
        _extract_solution(case, artifacts, artifacts.solver.model())
        if status == "sat"
        else None
    )
    extract_seconds = time.perf_counter() - extract_start
    record = PassRecord(
        status=status,
        build_seconds=build_seconds,
        solve_seconds=solve_seconds,
        extract_seconds=extract_seconds,
        build_modules=artifacts.build_modules,
        reason_unknown=reason_unknown,
        variable_count=artifacts.variable_count,
        assertion_count=len(artifacts.solver.assertions()),
    )
    return record, solution, artifacts.graph, artifacts.symmetry


# Run the first pass, then rebuild without symmetry if fallback is needed and enabled.
def route_case(case: CaseSpec, options: RouterOptions) -> RouteResult:
    pass1, solution, graph, symmetry = _solve_pass(
        case,
        options,
        require_symmetry=options.symmetry,
        timeout_ms=options.strict_timeout_ms,
    )
    pass2: Optional[PassRecord] = None
    used_fallback = False
    strict_solution = options.symmetry
    # Rebuild the relaxed model so no first-pass symmetry constraints remain.
    if pass1.status != "sat" and options.symmetry and options.fallback:
        used_fallback = True
        strict_solution = False
        pass2, solution, graph, symmetry = _solve_pass(
            case,
            options,
            require_symmetry=False,
            timeout_ms=options.fallback_timeout_ms,
        )
    final_record = pass2 if pass2 is not None else pass1
    validation_start = time.perf_counter()
    if final_record.status == "sat" and solution is not None:
        validation = validate_solution(
            case,
            graph,
            symmetry,
            solution,
            options,
            strict_symmetry=strict_solution,
        )
    else:
        validation = _empty_validation(f"solver returned {final_record.status}")
    validation_seconds = time.perf_counter() - validation_start
    return RouteResult(
        status=final_record.status,
        pass1=pass1,
        pass2=pass2,
        used_fallback=used_fallback,
        solution=solution,
        validation=validation,
        validation_seconds=validation_seconds,
        graph=graph,
        symmetry=symmetry,
    )


# Force a used resource with no flow to test upper binding.
def check_floating_resource_admissibility(
    case: CaseSpec,
    *,
    upper_binding: bool,
    timeout_ms: int = 5_000,
) -> str:
    options = RouterOptions(
        symmetry=False,
        fallback=False,
        length_bound=False,
        resource_upper_binding=upper_binding,
        no_dangling_branches=False,
        strict_timeout_ms=timeout_ms,
    )
    artifacts = build_model(
        case,
        options,
        require_symmetry=False,
        timeout_ms=timeout_ms,
    )
    witnesses: list[z3.BoolRef] = []
    for net_name in sorted(case.nets):
        commodity_count = len(case.nets[net_name].pins) - 1
        for resource in artifacts.graph.resources:
            u, v = artifacts.graph.endpoints[resource]
            resource_flows = [
                artifacts.flow[(net_name, commodity, a, b)]
                for commodity in range(commodity_count)
                for a, b in ((u, v), (v, u))
            ]
            witnesses.append(
                z3.And(
                    artifacts.use[(net_name, resource)],
                    z3.Not(z3.Or(resource_flows)),
                )
            )
    artifacts.solver.add(z3.Or(witnesses))
    return _status_text(artifacts.solver.check())
