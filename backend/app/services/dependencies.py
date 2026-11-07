import ast
from collections import defaultdict, deque
from pathlib import Path


IGNORED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
    ".bundle", ".gradle", "vendor", "bin", "obj", "target", "coverage",
}


def module_name_for_path(path: str | Path) -> str:
    value = Path(path).as_posix()
    if value.endswith(".py"):
        value = value[:-3]
    parts = [part for part in value.split("/") if part]
    if parts and parts[0] == "src":
        parts.pop(0)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def extract_imports(source_code: str, current_module: str = "") -> set[str]:
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import(current_module, node.level, node.module or "")
            if base:
                imports.add(base)
            for alias in node.names:
                if alias.name != "*":
                    imports.add(f"{base}.{alias.name}" if base else alias.name)
    return imports


def build_import_graph(project_root: str | Path) -> dict[str, set[str]]:
    root = Path(project_root)
    graph: dict[str, set[str]] = {}
    for path in root.rglob("*.py"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(root)
        module = module_name_for_path(relative)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        graph[module] = extract_imports(source, module)
    return graph


def find_reverse_dependencies(
    graph: dict[str, set[str]],
    changed_modules: set[str],
) -> set[str]:
    reverse: dict[str, set[str]] = defaultdict(set)
    modules = set(graph)

    for importer, dependencies in graph.items():
        for dependency in dependencies:
            for candidate in modules:
                if (
                    dependency == candidate
                    or dependency.startswith(candidate + ".")
                    or candidate.startswith(dependency + ".")
                    or dependency.startswith(candidate + "/")
                    or candidate.startswith(dependency + "/")
                ):
                    reverse[candidate].add(importer)

    affected = set(changed_modules)
    queue = deque(changed_modules)
    while queue:
        module = queue.popleft()
        for dependent in reverse.get(module, set()):
            if dependent not in affected:
                affected.add(dependent)
                queue.append(dependent)
    return affected


def _resolve_import(current_module: str, level: int, imported: str) -> str:
    if level == 0:
        return imported

    package = current_module.split(".")[:-1]
    keep = max(0, len(package) - (level - 1))
    prefix = package[:keep]
    if imported:
        prefix.extend(imported.split("."))
    return ".".join(prefix)
