"""Render routing solutions and pin annotations."""
from __future__ import annotations

from pathlib import Path

from amacro_router.data.types import (
    CaseSpec,
    RouteResult,
)


# Prepare pin label positions and via styling for rendering.
def rendering_metadata(
    case: CaseSpec,
    result: RouteResult,
) -> dict[str, object]:
    offsets = ((5, 7), (5, -13), (-5, 7), (-5, -13))
    pin_labels: list[dict[str, object]] = []
    for net_name in sorted(case.nets):
        for pin_index, (x, y) in enumerate(case.nets[net_name].pins):
            if y == 1:
                offset = (0, 10)
            elif y == case.grid.rows:
                offset = (0, -10)
            elif x == 1:
                offset = (7, 0)
            elif x == case.grid.cols:
                offset = (-7, 0)
            else:
                offset = offsets[pin_index % len(offsets)]
            pin_labels.append(
                {
                    "net": net_name,
                    "pin_index": pin_index,
                    "x": x,
                    "y": y,
                    "text": f"{net_name}:p{pin_index} ({x},{y})",
                    "offset_points": offset,
                }
            )
    return {
        "pin_labels": pin_labels,
        "via_marker": {"outer": "s", "inner": "x"},
        "net_names": sorted(case.nets),
    }


# Draw routes when available; otherwise show only the input grid and pins.
def render_solution(
    case: CaseSpec,
    result: RouteResult,
    output_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    metadata = rendering_metadata(case, result)
    fig, axis = plt.subplots(
        figsize=(
            max(7.5, case.grid.cols * 0.62 + 2.5),
            max(3.5, case.grid.rows * 0.85),
        )
    )
    for y in range(1, case.grid.rows + 1):
        for x in range(1, case.grid.cols + 1):
            axis.plot(x, y, marker=".", color="#D5D8DC", markersize=3, zorder=0)

    palette = (
        "#D62728",
        "#1F77B4",
        "#2CA02C",
        "#9467BD",
        "#FF7F0E",
        "#17BECF",
        "#8C564B",
    )
    colors = {
        net_name: palette[index % len(palette)]
        for index, net_name in enumerate(sorted(case.nets))
    }
    if result.solution is not None:
        for net_name in sorted(result.solution.resources):
            color = colors[net_name]
            for resource in result.solution.resources[net_name]:
                if resource.kind == "H":
                    axis.plot(
                        [resource.x, resource.x + 1],
                        [resource.y - 0.04, resource.y - 0.04],
                        color=color,
                        linewidth=3.2,
                        solid_capstyle="round",
                        zorder=2,
                    )
                elif resource.kind == "V":
                    axis.plot(
                        [resource.x + 0.04, resource.x + 0.04],
                        [resource.y, resource.y + 1],
                        color=color,
                        linewidth=2.3,
                        linestyle="--",
                        zorder=2,
                    )
                else:
                    axis.plot(
                        resource.x,
                        resource.y,
                        marker="s",
                        color=color,
                        markeredgecolor="#17202A",
                        markersize=7,
                        zorder=3,
                    )
                    axis.plot(
                        resource.x,
                        resource.y,
                        marker="x",
                        color="#111111",
                        markeredgewidth=1.2,
                        markersize=4.5,
                        linestyle="None",
                        zorder=4,
                    )

    for net_name, net in case.nets.items():
        for x, y in net.pins:
            axis.plot(
                x,
                y,
                marker="o",
                markerfacecolor=colors[net_name],
                markeredgecolor="#17202A",
                markersize=8,
                zorder=5,
            )
    for label in metadata["pin_labels"]:
        offset_x, offset_y = label["offset_points"]
        horizontal_alignment = (
            "center"
            if offset_x == 0
            else ("left" if offset_x > 0 else "right")
        )
        vertical_alignment = "bottom" if offset_y >= 0 else "top"
        axis.annotate(
            label["text"],
            xy=(label["x"], label["y"]),
            xytext=(offset_x, offset_y),
            textcoords="offset points",
            fontsize=7.5,
            color="#17202A",
            horizontalalignment=horizontal_alignment,
            verticalalignment=vertical_alignment,
            bbox={
                "boxstyle": "round,pad=0.15",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.78,
            },
            zorder=6,
        )
    axis.axvline(
        (case.grid.cols + 1) / 2,
        color="#7F8C8D",
        linewidth=0.8,
        linestyle=":",
        zorder=1,
    )
    axis.set_xlim(0.5, case.grid.cols + 0.5)
    axis.set_ylim(0.5, case.grid.rows + 0.5)
    axis.set_aspect("equal")
    axis.set_title(case.name)
    axis.set_xlabel("Routing column")
    axis.set_ylabel("Routing row")
    net_handles = [
        Line2D(
            [0],
            [0],
            color=colors[net_name],
            linewidth=3,
            marker="o",
            markeredgecolor="#17202A",
            label=net_name,
        )
        for net_name in metadata["net_names"]
    ]
    net_legend = axis.legend(
        handles=net_handles,
        title="Nets",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0,
        fontsize=8,
        title_fontsize=9,
    )
    axis.add_artist(net_legend)
    layer_handles = [
        Line2D([0], [0], color="#555555", linewidth=3, label="M1 horizontal"),
        Line2D(
            [0],
            [0],
            color="#555555",
            linewidth=2.3,
            linestyle="--",
            label="M2 vertical",
        ),
        Line2D(
            [0],
            [0],
            color="#111111",
            marker="s",
            markerfacecolor="white",
            linestyle="None",
            label="Via (square + ×)",
        ),
        Line2D(
            [0],
            [0],
            color="#111111",
            marker="o",
            markerfacecolor="white",
            linestyle="None",
            label="Pin",
        ),
    ]
    axis.legend(
        handles=layer_handles,
        title="Symbols",
        loc="lower left",
        bbox_to_anchor=(1.01, 0.02),
        borderaxespad=0,
        fontsize=8,
        title_fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
