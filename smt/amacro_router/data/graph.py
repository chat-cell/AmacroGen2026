"""Build the two-layer routing graph and mirror resources."""
from __future__ import annotations


from amacro_router.data.types import (
    GridSpec,
    Node,
    Pin,
    Resource,
    RoutingGraph,
)


# Reflect a pin about the central vertical axis using one-based coordinates.
def mirror_pin(pin: Pin, grid: GridSpec) -> Pin:
    x, y = pin
    return grid.cols + 1 - x, y


# Reflect a segment or via, adjusting segment origins for their direction.
def mirror_resource(resource: Resource, grid: GridSpec) -> Resource:
    if resource.kind == "H":
        return Resource("H", resource.layer, grid.cols - resource.x, resource.y)
    if resource.kind in {"V", "VIA"}:
        return Resource(
            resource.kind,
            resource.layer,
            grid.cols + 1 - resource.x,
            resource.y,
        )
    raise ValueError(f"unsupported resource kind: {resource.kind}")


# Build horizontal layer 1, vertical layer 2 and inter-layer vias.
def build_routing_graph(grid: GridSpec) -> RoutingGraph:
    nodes = tuple(
        (layer, x, y)
        for layer in (1, 2)
        for y in range(1, grid.rows + 1)
        for x in range(1, grid.cols + 1)
    )
    endpoints: dict[Resource, tuple[Node, Node]] = {}
    for y in range(1, grid.rows + 1):
        for x in range(1, grid.cols):
            endpoints[Resource("H", 1, x, y)] = (
                (1, x, y),
                (1, x + 1, y),
            )
    for y in range(1, grid.rows):
        for x in range(1, grid.cols + 1):
            endpoints[Resource("V", 2, x, y)] = (
                (2, x, y),
                (2, x, y + 1),
            )
    for y in range(1, grid.rows + 1):
        for x in range(1, grid.cols + 1):
            endpoints[Resource("VIA", 0, x, y)] = (
                (1, x, y),
                (2, x, y),
            )

    resources = tuple(sorted(endpoints))
    resource_by_endpoints = {
        frozenset(edge_endpoints): resource
        for resource, edge_endpoints in endpoints.items()
    }
    mutable_adjacency: dict[Node, list[tuple[Node, Resource]]] = {
        node: [] for node in nodes
    }
    for resource in resources:
        u, v = endpoints[resource]
        mutable_adjacency[u].append((v, resource))
        mutable_adjacency[v].append((u, resource))
    adjacency = {
        node: tuple(sorted(neighbors, key=lambda item: (item[0], item[1])))
        for node, neighbors in mutable_adjacency.items()
    }
    return RoutingGraph(
        grid=grid,
        nodes=nodes,
        resources=resources,
        endpoints=endpoints,
        resource_by_endpoints=resource_by_endpoints,
        adjacency=adjacency,
    )
