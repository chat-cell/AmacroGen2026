"""Infer symmetry relationships from explicit intent and pin geometry."""
from __future__ import annotations

from collections import Counter

from amacro_router.data.graph import (
    mirror_pin,
)
from amacro_router.data.types import (
    CaseSpec,
    GridSpec,
    NetSpec,
    Pin,
    SymmetrySpec,
)


# Count reflected pin coordinates for geometric matching.
def _mirrored_pin_counter(net: NetSpec, grid: GridSpec) -> Counter[Pin]:
    return Counter(mirror_pin(pin, grid) for pin in net.pins)


# Honor explicit constraints, then infer symmetry from the remaining pin sets.
def infer_symmetry(case: CaseSpec) -> SymmetrySpec:
    explicit = case.constraints
    self_nets = set(explicit.self_nets)
    pairs = [tuple(pair) for pair in explicit.pairs]
    ordinary = set(explicit.ordinary)
    # Explicitly classified nets are excluded from automatic inference.
    assigned = self_nets | ordinary | {name for pair in pairs for name in pair}
    remaining = sorted(set(case.nets) - assigned)

    pin_counters = {name: Counter(case.nets[name].pins) for name in case.nets}
    for name in tuple(remaining):
        if name in assigned:
            continue
        if _mirrored_pin_counter(case.nets[name], case.grid) == pin_counters[name]:
            self_nets.add(name)
            assigned.add(name)

    for name in remaining:
        if name in assigned:
            continue
        mirrored = _mirrored_pin_counter(case.nets[name], case.grid)
        candidates = [
            other
            for other in remaining
            if other not in assigned and other != name and pin_counters[other] == mirrored
        ]
        if len(candidates) > 1:
            raise ValueError(
                f"ambiguous mirrored-net inference for '{name}': {sorted(candidates)}"
            )
        if candidates:
            other = candidates[0]
            pairs.append(tuple(sorted((name, other))))
            assigned.update((name, other))
        else:
            # Unmatched nets become ordinary; this does not invoke the solver or establish UNSAT.
            ordinary.add(name)
            assigned.add(name)

    return SymmetrySpec(
        self_nets=tuple(sorted(self_nets)),
        pairs=tuple(sorted(set(pairs))),
        ordinary=tuple(sorted(ordinary)),
    )
