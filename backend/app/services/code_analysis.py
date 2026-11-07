import ast
from typing import Literal, TypedDict


class PythonImpact(TypedDict):
    changed_functions: list[str]
    changed_classes: list[str]
    module_level_change: bool
    analysis_status: Literal["analysed", "file_level", "parse_failed"]


def analyse_python_impact(
    source_code: str,
    changed_lines: list[int],
) -> PythonImpact:
    if not changed_lines:
        return {
            "changed_functions": [],
            "changed_classes": [],
            "module_level_change": True,
            "analysis_status": "file_level",
        }

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {
            "changed_functions": [],
            "changed_classes": [],
            "module_level_change": True,
            "analysis_status": "parse_failed",
        }

    changed = set(changed_lines)
    changed_functions: set[str] = set()
    changed_classes: set[str] = set()
    covered_lines: set[int] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        start_line = node.lineno
        if node.decorator_list:
            start_line = min(start_line, *(decorator.lineno for decorator in node.decorator_list))
        end_line = node.end_lineno or node.lineno
        overlapping = {line for line in changed if start_line <= line <= end_line}
        if not overlapping:
            continue

        covered_lines.update(overlapping)
        if isinstance(node, ast.ClassDef):
            changed_classes.add(node.name)
        else:
            changed_functions.add(node.name)

    source_lines = source_code.splitlines()
    meaningful_uncovered_lines = {
        line
        for line in changed - covered_lines
        if line <= len(source_lines)
        and source_lines[line - 1].strip()
        and not source_lines[line - 1].lstrip().startswith("#")
    }

    return {
        "changed_functions": sorted(changed_functions),
        "changed_classes": sorted(changed_classes),
        "module_level_change": bool(meaningful_uncovered_lines),
        "analysis_status": "analysed",
    }


def analyse_python_file(
    source_code: str,
    changed_lines: list[int],
) -> dict[str, list[str]]:
    """Backward-compatible symbol-only view used by existing callers."""
    impact = analyse_python_impact(source_code, changed_lines)
    return {
        "changed_functions": impact["changed_functions"],
        "changed_classes": impact["changed_classes"],
    }
