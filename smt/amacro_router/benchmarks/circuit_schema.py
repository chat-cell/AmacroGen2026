"""Circuit benchmark ordering and summary column definitions."""
from __future__ import annotations




TABLE_II_CASE_ORDER = (
    "amacro_cp_M5",
    "amacro_cp_M6",
    "amacro_cp_M9",
    "amacro_cp_M11",
    "amacro_LDO_FORPLL_M1",
    "amacro_LDO_FORPLL_M3",
    "amacro_LDO_FORPLL_M5",
    "amacro_LDO_FORPLL_M6",
    "amacro_LDO_FORPLL_M14",
    "amacro_LDO_FORPLL_M18",
    "amacro_cp_op_M10",
    "amacro_cp_op_M25",
    "amacro_cp_op_M26",
    "amacro_cp_op_M28",
    "amacro_cp_op_M30",
    "amacro_cp_op_M32",
    "amacro_cp_op_M35",
    "amacro_cp_op_M45",
    "amacro_cp_op_M48",
    "amacro_cp_op_M49",
)


MODULE_NAMES = (
    "graph_and_variables",
    "multi_commodity_flow",
    "flow_resource_binding",
    "rooted_tree",
    "no_dangling_branches",
    "pin_access",
    "length_bound",
    "resource_exclusivity_and_drc",
    "symmetry",
)


BASE_FIELDS = (
    "case",
    "status",
    "valid",
    "used_fallback",
    "rows",
    "cols",
    "nets",
    "pins",
    "nodes",
    "resources",
    "input_parse_seconds",
    "strict_status",
    "strict_build_seconds",
    "strict_solve_seconds",
    "strict_extract_seconds",
    "strict_total_seconds",
    "fallback_status",
    "fallback_build_seconds",
    "fallback_solve_seconds",
    "fallback_extract_seconds",
    "fallback_total_seconds",
    "validation_seconds",
    "render_seconds",
    "export_seconds",
    "total_wall_seconds",
    "result_dir",
    "strict_variables",
    "strict_assertions",
    "strict_reason_unknown",
    "fallback_variables",
    "fallback_assertions",
    "fallback_reason_unknown",
    "error",
)


MODULE_FIELDS = tuple(
    field
    for prefix in ("strict", "fallback")
    for module in MODULE_NAMES
    for field in (
        f"{prefix}_{module}_seconds",
        f"{prefix}_{module}_assertions",
    )
)


CSV_FIELDS = BASE_FIELDS + MODULE_FIELDS
