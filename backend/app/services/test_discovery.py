import ast
from pathlib import Path

from app.services.dependencies import IGNORED_PARTS, extract_imports, module_name_for_path


def discover_tests(
    tests_directory: str | Path,
    project_root: str | Path | None = None,
) -> list[dict]:
    tests_path = Path(tests_directory)
    if not tests_path.is_dir():
        return []

    root_path = Path(project_root) if project_root else tests_path.parent
    discovered_tests: list[dict] = []

    for file_path in sorted(tests_path.rglob("*.py")):
        if any(part in IGNORED_PARTS for part in file_path.parts):
            continue
        if not _is_test_file(file_path, tests_path):
            continue

        try:
            source_code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source_code)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        try:
            relative_path = file_path.relative_to(root_path).as_posix()
        except ValueError:
            relative_path = file_path.relative_to(tests_path).as_posix()

        module_name = module_name_for_path(relative_path)
        imports = sorted(extract_imports(source_code, module_name))

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    discovered_tests.append(
                        _test_record(relative_path, node, None, "pytest", imports)
                    )
            elif isinstance(node, ast.ClassDef):
                methods = [
                    method
                    for method in node.body
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and method.name.startswith("test_")
                ]
                if not methods or not _is_test_class(node):
                    continue
                framework = "unittest" if _is_unittest_class(node) else "pytest"
                for method in methods:
                    discovered_tests.append(
                        _test_record(relative_path, method, node.name, framework, imports)
                    )

    return discovered_tests


def discover_project_tests(project_root: str | Path) -> list[dict]:
    root = Path(project_root)
    return discover_tests(root, root)


def _test_record(
    relative_path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    test_class: str | None,
    framework: str,
    imports: list[str],
) -> dict:
    node_parts = [relative_path]
    if test_class:
        node_parts.append(test_class)
    node_parts.append(node.name)

    references = {
        child.id for child in ast.walk(node) if isinstance(child, ast.Name)
    }
    references.update(
        child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute)
    )
    called_names = {
        name
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for name in [_callable_name(child.func)]
        if name
    }

    return {
        "test_file": relative_path,
        "test_name": node.name,
        "test_class": test_class,
        "node_id": "::".join(node_parts),
        "framework": framework,
        "imports": imports,
        "referenced_names": sorted(references),
        "called_names": sorted(called_names),
        "start_line": node.lineno,
        "end_line": node.end_lineno or node.lineno,
    }


def _callable_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_test_file(path: Path, search_root: Path) -> bool:
    name = path.name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in path.relative_to(search_root).parts
        or search_root.name == "tests"
    )


def _is_test_class(node: ast.ClassDef) -> bool:
    return node.name.startswith("Test") or _is_unittest_class(node) or any(
        isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        and method.name.startswith("test_")
        for method in node.body
    )


def _is_unittest_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith("TestCase"):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith("TestCase"):
            return True
    return False
