"""Construct the SMT variables and routing constraints."""
from __future__ import annotations

import time
import z3

from amacro_router.data.graph import (
    build_routing_graph,
    mirror_resource,
)
from amacro_router.data.symmetry import (
    infer_symmetry,
)
from amacro_router.data.types import (
    BuildModuleTiming,
    CaseSpec,
    ModelArtifacts,
    Node,
    Resource,
    RouterOptions,
)
from amacro_router.encoding.helpers import (
    _bool_sum,
    _incident_resources,
    _lmax,
    _symbol,
)


# Construct one SMT model and its variable mappings without solving it.
def build_model(
    case: CaseSpec,
    options: RouterOptions,
    *,
    require_symmetry: bool,
    timeout_ms: int,
) -> ModelArtifacts:
    module_timings: dict[str, BuildModuleTiming] = {}

    # Accumulate construction time and assertion increments across nets.
    def record_module(name: str, started: float, assertions_before: int) -> None:
        current = module_timings.get(name, BuildModuleTiming(0.0, 0))
        module_timings[name] = BuildModuleTiming(
            seconds=current.seconds + (time.perf_counter() - started),
            assertions_added=(
                current.assertions_added
                + len(solver.assertions())
                - assertions_before
            ),
        )

    module_start = time.perf_counter()
    graph = build_routing_graph(case.grid)
    symmetry = infer_symmetry(case)
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.set(random_seed=0)

    # use tracks physical occupancy; flow tracks directed source-to-sink commodities.
    use: dict[tuple[str, Resource], z3.BoolRef] = {}
    flow: dict[tuple[str, int, Node, Node], z3.BoolRef] = {}
    access: dict[tuple[str, int, int], z3.BoolRef] = {}
    # active, parent and depth constrain selected physical resources to a rooted tree.
    active: dict[tuple[str, Node], z3.BoolRef] = {}
    parent: dict[tuple[str, Node, Node], z3.BoolRef] = {}
    depth: dict[tuple[str, Node], z3.IntNumRef] = {}

    for net_name in sorted(case.nets):
        for resource in graph.resources:
            use[(net_name, resource)] = z3.Bool(
                f"use__{_symbol(net_name)}__{resource.kind}_{resource.x}_{resource.y}"
            )

    for net_name in sorted(case.nets):
        net = case.nets[net_name]
        for commodity in range(len(net.pins) - 1):
            for node in graph.nodes:
                for neighbor, _ in graph.adjacency[node]:
                    flow[(net_name, commodity, node, neighbor)] = z3.Bool(
                        "flow__"
                        f"{_symbol(net_name)}__m{commodity}__"
                        f"{node[0]}_{node[1]}_{node[2]}__"
                        f"{neighbor[0]}_{neighbor[1]}_{neighbor[2]}"
                    )
    record_module("graph_and_variables", module_start, 0)

    for net_name in sorted(case.nets):
        net = case.nets[net_name]
        source = (1, net.pins[0][0], net.pins[0][1])
        module_start = time.perf_counter()
        assertions_before = len(solver.assertions())
        # Enforce conservation per sink; commodities of the same net may share resources.
        for commodity, sink_pin in enumerate(net.pins[1:]):
            sink = (1, sink_pin[0], sink_pin[1])
            for node in graph.nodes:
                outgoing = [
                    flow[(net_name, commodity, node, neighbor)]
                    for neighbor, _ in graph.adjacency[node]
                ]
                incoming = [
                    flow[(net_name, commodity, neighbor, node)]
                    for neighbor, _ in graph.adjacency[node]
                ]
                if node == source:
                    solver.add(_bool_sum(outgoing) - _bool_sum(incoming) == 1)
                elif node == sink:
                    solver.add(_bool_sum(incoming) - _bool_sum(outgoing) == 1)
                else:
                    solver.add(_bool_sum(outgoing) - _bool_sum(incoming) == 0)
        record_module("multi_commodity_flow", module_start, assertions_before)

        module_start = time.perf_counter()
        assertions_before = len(solver.assertions())
        for resource in graph.resources:
            u, v = graph.endpoints[resource]
            resource_flows: list[z3.BoolRef] = []
            for commodity in range(len(net.pins) - 1):
                forward = flow[(net_name, commodity, u, v)]
                backward = flow[(net_name, commodity, v, u)]
                solver.add(z3.Implies(forward, use[(net_name, resource)]))
                solver.add(z3.Implies(backward, use[(net_name, resource)]))
                resource_flows.extend((forward, backward))
            # Upper binding requires each occupied resource to carry at least one commodity flow.
            if options.resource_upper_binding:
                solver.add(
                    z3.Implies(
                        use[(net_name, resource)],
                        z3.Or(resource_flows),
                    )
                )
        record_module("flow_resource_binding", module_start, assertions_before)

        # The selected physical resources form one rooted tree. This makes
        # loop elimination a model invariant instead of relying on the solver
        # to happen to choose an acyclic connected subgraph.
        module_start = time.perf_counter()
        assertions_before = len(solver.assertions())
        for node in graph.nodes:
            active[(net_name, node)] = z3.Bool(
                f"active__{_symbol(net_name)}__{node[0]}_{node[1]}_{node[2]}"
            )
            depth[(net_name, node)] = z3.Int(
                f"depth__{_symbol(net_name)}__{node[0]}_{node[1]}_{node[2]}"
            )
            solver.add(
                active[(net_name, node)]
                == z3.Or(
                    [
                        use[(net_name, resource)]
                        for resource in _incident_resources(graph, node)
                    ]
                )
            )
            solver.add(
                z3.If(
                    active[(net_name, node)],
                    z3.And(
                        depth[(net_name, node)] >= 0,
                        depth[(net_name, node)] < len(graph.nodes),
                    ),
                    depth[(net_name, node)] == 0,
                )
            )

        for resource in graph.resources:
            u, v = graph.endpoints[resource]
            parent[(net_name, u, v)] = z3.Bool(
                "parent__"
                f"{_symbol(net_name)}__"
                f"{u[0]}_{u[1]}_{u[2]}__{v[0]}_{v[1]}_{v[2]}"
            )
            parent[(net_name, v, u)] = z3.Bool(
                "parent__"
                f"{_symbol(net_name)}__"
                f"{v[0]}_{v[1]}_{v[2]}__{u[0]}_{u[1]}_{u[2]}"
            )
            forward_parent = parent[(net_name, u, v)]
            backward_parent = parent[(net_name, v, u)]
            solver.add(
                _bool_sum((forward_parent, backward_parent))
                == z3.If(use[(net_name, resource)], 1, 0)
            )
            solver.add(
                z3.Implies(
                    forward_parent,
                    depth[(net_name, v)] == depth[(net_name, u)] + 1,
                )
            )
            solver.add(
                z3.Implies(
                    backward_parent,
                    depth[(net_name, u)] == depth[(net_name, v)] + 1,
                )
            )

        solver.add(active[(net_name, source)])
        solver.add(depth[(net_name, source)] == 0)
        for node in graph.nodes:
            incoming_parents = [
                parent[(net_name, neighbor, node)]
                for neighbor, _ in graph.adjacency[node]
            ]
            if node == source:
                solver.add(_bool_sum(incoming_parents) == 0)
            else:
                solver.add(
                    _bool_sum(incoming_parents)
                    == z3.If(active[(net_name, node)], 1, 0)
                )
        record_module("rooted_tree", module_start, assertions_before)

        module_start = time.perf_counter()
        assertions_before = len(solver.assertions())
        # Exclude degree-one non-pin nodes to eliminate dangling branches.
        if options.no_dangling_branches:
            pin_nodes = {(1, x, y) for x, y in net.pins}
            for node in graph.nodes:
                if node not in pin_nodes:
                    solver.add(
                        _bool_sum(
                            use[(net_name, resource)]
                            for resource in _incident_resources(graph, node)
                        )
                        != 1
                    )
        record_module(
            "no_dangling_branches",
            module_start,
            assertions_before,
        )

        module_start = time.perf_counter()
        assertions_before = len(solver.assertions())
        # Each pin has one fixed access point and must use at least one incident resource.
        for pin_index, pin in enumerate(net.pins):
            access_var = z3.Bool(f"access__{_symbol(net_name)}__p{pin_index}__a0")
            access[(net_name, pin_index, 0)] = access_var
            solver.add(access_var)
            pin_node = (1, pin[0], pin[1])
            incident = [
                use[(net_name, resource)]
                for resource in _incident_resources(graph, pin_node)
            ]
            solver.add(z3.Implies(access_var, z3.Or(incident)))
        record_module("pin_access", module_start, assertions_before)

        module_start = time.perf_counter()
        assertions_before = len(solver.assertions())
        # The budget counts both segments and vias, not geometric wire length.
        if options.length_bound:
            slack = (
                case.constraints.length_slack
                if options.length_slack is None
                else options.length_slack
            )
            solver.add(
                _bool_sum(use[(net_name, resource)] for resource in graph.resources)
                <= _lmax(net, slack)
            )
        record_module("length_bound", module_start, assertions_before)

    module_start = time.perf_counter()
    assertions_before = len(solver.assertions())
    # Disallow shared resources; input conflict_sets specify additional DRC exclusions.
    for resource in graph.resources:
        solver.add(
            z3.PbLe(
                [(use[(net_name, resource)], 1) for net_name in sorted(case.nets)],
                1,
            )
        )

    for conflict_set in case.constraints.conflict_sets:
        solver.add(
            z3.PbLe(
                [
                    (use[(net_name, resource)], 1)
                    for net_name in sorted(case.nets)
                    for resource in conflict_set
                ],
                1,
            )
        )
    record_module(
        "resource_exclusivity_and_drc",
        module_start,
        assertions_before,
    )

    module_start = time.perf_counter()
    assertions_before = len(solver.assertions())
    # Constrain only self_nets and pairs; ordinary nets are exempt even in the first pass.
    if require_symmetry:
        for net_name in symmetry.self_nets:
            for resource in graph.resources:
                solver.add(
                    use[(net_name, resource)]
                    == use[(net_name, mirror_resource(resource, graph.grid))]
                )
        for net1, net2 in symmetry.pairs:
            for resource in graph.resources:
                solver.add(
                    use[(net1, resource)]
                    == use[(net2, mirror_resource(resource, graph.grid))]
                )
    record_module("symmetry", module_start, assertions_before)

    return ModelArtifacts(
        solver=solver,
        graph=graph,
        symmetry=symmetry,
        use=use,
        flow=flow,
        access=access,
        variable_count=(
            len(use)
            + len(flow)
            + len(access)
            + len(active)
            + len(parent)
            + len(depth)
        ),
        build_modules=module_timings,
    )
