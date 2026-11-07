
import ast


def analyse_python_file(
    source_code: str,
    changed_lines: list[int]
) -> dict[str, list[str]]:
    """
    Identify functions and classes affected by changed lines.

    Args:
        source_code: Full contents of the Python file.
        changed_lines: Line numbers changed in the pull request.

    Returns:
        A dictionary containing affected functions and classes.
    """

    if not changed_lines:
        return {
            "changed_functions": [],
            "changed_classes": []
        }

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {
            "changed_functions": [],
            "changed_classes": []
        }

    changed_functions = []
    changed_classes = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue

        # Include decorator lines when calculating the start.
        start_line = node.lineno

        if hasattr(node, "decorator_list") and node.decorator_list:
            start_line = min(
                start_line,
                *(decorator.lineno for decorator in node.decorator_list)
            )

        end_line = node.end_lineno or node.lineno

        # Check whether any changed line overlaps this node.
        affected = any(
            start_line <= line <= end_line
            for line in changed_lines
        )

        if not affected:
            continue

        if isinstance(node, ast.ClassDef):
            changed_classes.append(node.name)

        else:
            changed_functions.append(node.name)

    return {
        "changed_functions": sorted(set(changed_functions)),
        "changed_classes": sorted(set(changed_classes))
    }
