"""Validate extracted routes against the abstract routing model."""
from __future__ import annotations

from collections import Counter

from amacro_router.data.graph import (
    mirror_resource,
)
from amacro_router.data.types import (
    CaseSpec,
    NetSpec,
    Node,
    Resource,
    RouteSolution,
    RouterOptions,
    RoutingGraph,
    SymmetrySpec,
    ValidationReport,
)
from amacro_router.encoding.helpers import (
    _incident_resources,
    _lmax,
)


# Check pin connectivity and compute the physical graph cycle rank.
def _connected_pin_check(
    net: NetSpec,
    resources: tuple[Resource, ...],
    graph: RoutingGraph,
) -> tuple[bool, int]:
    adjacency: dict[Node, set[Node]] = {}
    vertices: set[Node] = set()
    for resource in resources:
        u, v = graph.endpoints[resource]
        adjacency.setdefault(u, set()).add(v)
        adjacency.setdefault(v, set()).add(u)
        vertices.update((u, v))
    pin_nodes = [(1, x, y) for x, y in net.pins]
    if not pin_nodes or pin_nodes[0] not in vertices:
        return False, 0
    seen = {pin_nodes[0]}
    stack = [pin_nodes[0]]
    while stack:
        node = stack.pop()
        for neighbor in adjacency.get(node, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    all_connected = all(pin in seen for pin in pin_nodes)
    component_count = 0
    unseen = set(vertices)
    while unseen:
        component_count += 1
        seed = unseen.pop()
        frontier = [seed]
        while frontier:
            node = frontier.pop()
            for neighbor in adjacency.get(node, ()):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    frontier.append(neighbor)
    cycle_rank = max(0, len(resources) - len(vertices) + component_count)
    return all_connected, cycle_rank


# Find degree-one non-pin nodes representing dangling route ends.
def _non_pin_leaves(
    net: NetSpec,
    resources: tuple[Resource, ...],
    graph: RoutingGraph,
) -> tuple[Node, ...]:
    degrees: Counter[Node] = Counter()
    for resource in resources:
        u, v = graph.endpoints[resource]
        degrees[u] += 1
        degrees[v] += 1
    pin_nodes = {(1, x, y) for x, y in net.pins}
    return tuple(
        sorted(node for node, degree in degrees.items() if degree == 1 and node not in pin_nodes)
    )


# Check connectivity, flows, resources, length and specified symmetry.
def validate_solution(
    case: CaseSpec,
    graph: RoutingGraph,
    symmetry: SymmetrySpec,
    solution: RouteSolution,
    options: RouterOptions,
    *,
    strict_symmetry: bool,
) -> ValidationReport:
    errors: list[str] = []
    all_pins_connected = True
    cycle_rank_by_net: dict[str, int] = {}
    resource_owners: dict[Resource, list[str]] = {}
    no_zero_flow_resources = True
    flow_resource_consistent = True
    flow_conservation_satisfied = True
    pin_access_satisfied = True
    length_bound_satisfied = True
    no_dangling_branches = True
    non_pin_leaves_by_net: dict[str, tuple[Node, ...]] = {}

    for net_name, net in case.nets.items():
        connected, cycle_rank = _connected_pin_check(
            net,
            solution.resources[net_name],
            graph,
        )
        cycle_rank_by_net[net_name] = cycle_rank
        if not connected:
            all_pins_connected = False
            errors.append(f"{net_name}: not all pins are connected")
        non_pin_leaves = _non_pin_leaves(
            net,
            solution.resources[net_name],
            graph,
        )
        non_pin_leaves_by_net[net_name] = non_pin_leaves
        if non_pin_leaves:
            no_dangling_branches = False
            errors.append(
                f"{net_name}: non-pin routing leaves detected at "
                f"{list(non_pin_leaves)}"
            )
        for resource in solution.resources[net_name]:
            resource_owners.setdefault(resource, []).append(net_name)

        flow_resources = {
            graph.resource_by_endpoints[frozenset((u, v))]
            for _, u, v in solution.flows[net_name]
        }
        if not set(solution.resources[net_name]).issubset(flow_resources):
            no_zero_flow_resources = False
            errors.append(f"{net_name}: selected physical resource carries no commodity")
        if not flow_resources.issubset(set(solution.resources[net_name])):
            flow_resource_consistent = False
            errors.append(f"{net_name}: commodity flow uses an unselected resource")

        for commodity, sink_pin in enumerate(net.pins[1:]):
            source = (1, net.pins[0][0], net.pins[0][1])
            sink = (1, sink_pin[0], sink_pin[1])
            arcs = [
                (u, v)
                for flow_commodity, u, v in solution.flows[net_name]
                if flow_commodity == commodity
            ]
            for node in graph.nodes:
                outflow = sum(u == node for u, _ in arcs)
                inflow = sum(v == node for _, v in arcs)
                expected = 1 if node == source else (-1 if node == sink else 0)
                if outflow - inflow != expected:
                    flow_conservation_satisfied = False
                    errors.append(
                        f"{net_name}: commodity {commodity} violates flow "
                        f"conservation at {node}"
                    )
                    break

        if set(solution.accesses[net_name]) != set(range(len(net.pins))):
            pin_access_satisfied = False
            errors.append(f"{net_name}: fixed pin access was not selected")
        for pin_index, pin in enumerate(net.pins):
            pin_node = (1, pin[0], pin[1])
            if not any(
                resource in solution.resources[net_name]
                for resource in _incident_resources(graph, pin_node)
            ):
                pin_access_satisfied = False
                errors.append(f"{net_name}: pin {pin_index} has no incident route")

        if options.length_bound:
            slack = (
                case.constraints.length_slack
                if options.length_slack is None
                else options.length_slack
            )
            if len(solution.resources[net_name]) > _lmax(net, slack):
                length_bound_satisfied = False
                errors.append(f"{net_name}: routing-length bound exceeded")

    no_shared_resources = all(len(owners) == 1 for owners in resource_owners.values())
    if not no_shared_resources:
        errors.append("one or more physical resources are shared by different nets")
    abstract_drc_satisfied = no_shared_resources
    for conflict_index, conflict_set in enumerate(case.constraints.conflict_sets):
        selected_count = sum(
            resource in solution.resources[net_name]
            for net_name in case.nets
            for resource in conflict_set
        )
        if selected_count > 1:
            abstract_drc_satisfied = False
            errors.append(f"abstract DRC conflict set {conflict_index} is violated")

    # Check only declared or inferred symmetry; ordinary nets have no symmetry requirement.
    symmetry_satisfied = True
    for net_name in symmetry.self_nets:
        selected = set(solution.resources[net_name])
        mirrored = {mirror_resource(resource, graph.grid) for resource in selected}
        if selected != mirrored:
            symmetry_satisfied = False
            if strict_symmetry:
                errors.append(f"{net_name}: self-symmetry validation failed")
    for net1, net2 in symmetry.pairs:
        selected1 = set(solution.resources[net1])
        mirrored2 = {
            mirror_resource(resource, graph.grid)
            for resource in solution.resources[net2]
        }
        if selected1 != mirrored2:
            symmetry_satisfied = False
            if strict_symmetry:
                errors.append(f"{net1}/{net2}: paired symmetry validation failed")
    valid = all(
        (
            all_pins_connected,
            abstract_drc_satisfied,
            no_zero_flow_resources,
            flow_resource_consistent,
            flow_conservation_satisfied,
            no_dangling_branches,
            symmetry_satisfied if strict_symmetry else True,
            length_bound_satisfied,
            pin_access_satisfied,
        )
    )
    return ValidationReport(
        valid=valid,
        all_pins_connected=all_pins_connected,
        no_shared_resources=no_shared_resources,
        abstract_drc_satisfied=abstract_drc_satisfied,
        no_zero_flow_resources=no_zero_flow_resources,
        flow_resource_consistent=flow_resource_consistent,
        flow_conservation_satisfied=flow_conservation_satisfied,
        no_dangling_branches=no_dangling_branches,
        non_pin_leaves_by_net=non_pin_leaves_by_net,
        symmetry_satisfied=symmetry_satisfied,
        length_bound_satisfied=length_bound_satisfied,
        pin_access_satisfied=pin_access_satisfied,
        cycle_rank_by_net=cycle_rank_by_net,
        errors=tuple(errors),
    )


# Return a failed validation record when no solution is available.
def _empty_validation(message: str) -> ValidationReport:
    return ValidationReport(
        valid=False,
        all_pins_connected=False,
        no_shared_resources=False,
        abstract_drc_satisfied=False,
        no_zero_flow_resources=False,
        flow_resource_consistent=False,
        flow_conservation_satisfied=False,
        no_dangling_branches=False,
        non_pin_leaves_by_net={},
        symmetry_satisfied=False,
        length_bound_satisfied=False,
        pin_access_satisfied=False,
        cycle_rank_by_net={},
        errors=(message,),
    )
