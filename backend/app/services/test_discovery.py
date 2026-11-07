
import ast
from pathlib import Path


def discover_tests(
    tests_directory: str | Path,
    project_root: str | Path | None = None
) -> list[dict]:

    tests_path = Path(tests_directory)

    if not tests_path.is_dir():
        return []

    root_path = Path(project_root) if project_root else tests_path.parent

    discovered_tests = []

    for file_path in sorted(tests_path.rglob("*.py")):

        try:
            source_code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source_code)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        try:
            relative_path = str(file_path.relative_to(root_path))
        except ValueError:
            relative_path = str(file_path.relative_to(tests_path))

        for node in tree.body:

            # Discover standalone test functions.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    discovered_tests.append({
                        "test_file": relative_path,
                        "test_name": node.name,
                        "test_class": None
                    })

            # Discover test classes and their test methods.
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("Test"):
                    for method in node.body:
                        if isinstance(
                            method,
                            (ast.FunctionDef, ast.AsyncFunctionDef)
                        ) and method.name.startswith("test_"):

                            discovered_tests.append({
                                "test_file": relative_path,
                                "test_name": method.name,
                                "test_class": node.name
                            })

    return discovered_tests
