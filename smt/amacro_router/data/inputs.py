"""Parse and validate grid, net and constraint input files."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from amacro_router.data.types import (
    CaseSpec,
    ConstraintSpec,
    GridSpec,
    NetSpec,
    Resource,
)


# Skip blank lines and full-line comments while retaining diagnostic line numbers.
def _data_lines(path: Path) -> Iterable[tuple[int, str]]:
    if not path.exists():
        raise ValueError(f"missing required input file: {path}")
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield line_number, line


# Read and validate the grid dimensions.
def _parse_grid(path: Path) -> GridSpec:
    lines = list(_data_lines(path))
    if len(lines) != 1:
        raise ValueError(f"{path}: expected exactly one grid definition")
    line_number, line = lines[0]
    parts = line.split()
    if len(parts) != 2:
        raise ValueError(f"{path}:{line_number}: expected 'rows cols'")
    try:
        rows, cols = (int(value) for value in parts)
    except ValueError as exc:
        raise ValueError(f"{path}:{line_number}: grid dimensions must be integers") from exc
    if rows <= 0 or cols <= 0:
        raise ValueError(f"{path}:{line_number}: grid dimensions must be positive")
    return GridSpec(rows=rows, cols=cols)


# Parse pins and check bounds and duplicates within each net.
def _parse_nets(path: Path, grid: GridSpec) -> dict[str, NetSpec]:
    nets: dict[str, NetSpec] = {}
    for line_number, line in _data_lines(path):
        parts = line.split()
        name, values = parts[0], parts[1:]
        if name in nets:
            raise ValueError(f"{path}:{line_number}: duplicate net '{name}'")
        if len(values) < 4 or len(values) % 2:
            raise ValueError(
                f"{path}:{line_number}: net '{name}' requires at least two x/y pin pairs"
            )
        try:
            pins = tuple(
                (int(values[index]), int(values[index + 1]))
                for index in range(0, len(values), 2)
            )
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: pin coordinates must be integers") from exc
        if len(set(pins)) != len(pins):
            raise ValueError(f"{path}:{line_number}: duplicate pin in net '{name}'")
        for x, y in pins:
            if not (1 <= x <= grid.cols and 1 <= y <= grid.rows):
                raise ValueError(
                    f"{path}:{line_number}: pin {(x, y)} is outside "
                    f"{grid.cols}x{grid.rows} grid"
                )
        nets[name] = NetSpec(name=name, pins=pins)
    if not nets:
        raise ValueError(f"{path}: no routable nets found")
    return nets


# Read optional constraints; use defaults when the file is absent.
def _parse_constraints(
    path: Path,
    net_names: set[str],
    grid: GridSpec,
) -> ConstraintSpec:
    if not path.exists():
        return ConstraintSpec()
    self_nets: set[str] = set()
    ordinary: set[str] = set()
    pairs: list[tuple[str, str]] = []
    conflict_sets: list[tuple[Resource, ...]] = []
    length_slack = 8
    assigned: set[str] = set()
    for line_number, line in _data_lines(path):
        parts = line.split()
        keyword = parts[0].lower()
        if keyword == "length_slack" and len(parts) == 2:
            length_slack = int(parts[1])
            if length_slack < 0:
                raise ValueError(f"{path}:{line_number}: length_slack must be nonnegative")
            continue
        if keyword == "conflict" and len(parts) >= 3:
            resources: list[Resource] = []
            for token in parts[1:]:
                fields = token.split(":")
                if len(fields) != 4:
                    raise ValueError(
                        f"{path}:{line_number}: resource '{token}' must use "
                        "KIND:LAYER:X:Y"
                    )
                kind = fields[0].upper()
                try:
                    layer, x, y = (int(value) for value in fields[1:])
                except ValueError as exc:
                    raise ValueError(
                        f"{path}:{line_number}: invalid resource '{token}'"
                    ) from exc
                resource = Resource(kind, layer, x, y)
                if kind == "H":
                    valid = layer == 1 and 1 <= x < grid.cols and 1 <= y <= grid.rows
                elif kind == "V":
                    valid = layer == 2 and 1 <= x <= grid.cols and 1 <= y < grid.rows
                elif kind == "VIA":
                    valid = layer == 0 and 1 <= x <= grid.cols and 1 <= y <= grid.rows
                else:
                    valid = False
                if not valid:
                    raise ValueError(
                        f"{path}:{line_number}: resource '{token}' is outside the graph"
                    )
                resources.append(resource)
            if len(set(resources)) != len(resources):
                raise ValueError(
                    f"{path}:{line_number}: duplicate resource in conflict set"
                )
            conflict_sets.append(tuple(resources))
            continue
        if keyword in {"self", "ordinary"} and len(parts) == 2:
            names = [parts[1]]
        elif keyword == "pair" and len(parts) == 3:
            names = [parts[1], parts[2]]
        elif keyword == "axis" and len(parts) == 3 and parts[1].lower() == "vertical":
            try:
                axis = float(parts[2])
            except ValueError as exc:
                raise ValueError(
                    f"{path}:{line_number}: symmetry axis must be numeric"
                ) from exc
            expected_axis = (grid.cols + 1) / 2
            if abs(axis - expected_axis) > 1e-9:
                raise ValueError(
                    f"{path}:{line_number}: current router requires the vertical "
                    f"symmetry axis at the geometric center {expected_axis}"
                )
            continue
        else:
            raise ValueError(f"{path}:{line_number}: unsupported constraint '{line}'")
        unknown = set(names) - net_names
        if unknown:
            raise ValueError(f"{path}:{line_number}: unknown nets {sorted(unknown)}")
        overlap = set(names) & assigned
        if overlap:
            raise ValueError(
                f"{path}:{line_number}: nets assigned more than once: {sorted(overlap)}"
            )
        assigned.update(names)
        if keyword == "self":
            self_nets.add(names[0])
        elif keyword == "ordinary":
            ordinary.add(names[0])
        else:
            pairs.append(tuple(names))
    return ConstraintSpec(
        self_nets=frozenset(self_nets),
        pairs=tuple(pairs),
        ordinary=frozenset(ordinary),
        length_slack=length_slack,
        conflict_sets=tuple(conflict_sets),
    )


# Load grid, net and constraint files from a case directory.
def load_case(case_dir: str | Path) -> CaseSpec:
    path = Path(case_dir).resolve()
    grid = _parse_grid(path / "grid_config.txt")
    nets = _parse_nets(path / "net_config.txt", grid)
    constraints = _parse_constraints(
        path / "constraint_config.txt",
        set(nets),
        grid,
    )
    return CaseSpec(
        name=path.name,
        path=path,
        grid=grid,
        nets=nets,
        constraints=constraints,
    )
