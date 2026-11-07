import re
from pathlib import Path

from app.services.language_support import is_test_path


_GENERIC_FUNCTIONS = {
    "add", "create", "delete", "get", "handle", "list", "process",
    "remove", "run", "set", "update",
}


def normalise_name(name: str) -> str:
    """Remove separators and convert an identifier to lowercase."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match_tests(
    changed_functions: list[str],
    changed_classes: list[str],
    discovered_tests: list[dict],
    changed_files: list[dict] | None = None,
) -> list[dict]:
    """Rank tests using scoped symbols, direct calls, and precise test changes."""
    changed_files = changed_files or []
    production_changes = _production_changes(
        changed_functions, changed_classes, changed_files
    )
    test_changes = _changed_test_impacts(changed_files, discovered_tests)
    legacy_mode = not changed_files
    recommendations: list[dict] = []

    for test in discovered_tests:
        test_path = _path(test["test_file"])
        test_name = test["test_name"]
        test_tokens = _identifier_tokens(test_name)
        references = {
            normalise_name(reference)
            for reference in test.get("referenced_names", [])
            if normalise_name(reference)
        }
        has_call_metadata = "called_names" in test
        called_names = {
            normalise_name(name)
            for name in test.get("called_names", [])
            if normalise_name(name)
        }
        imports = set(test.get("imports", []))
        reasons: list[str] = []
        confidence = 0.0

        test_impact = test_changes.get(test_path)
        if test_impact:
            if _test_impact_key(test) in test_impact["direct_nodes"]:
                confidence = 1.0
                reasons.append("Test implementation was changed in this pull request")
            elif test_impact["broad"]:
                confidence = max(confidence, 0.90)
                reasons.append(
                    "Shared setup or module-level code changed in this test file"
                )

        for change in production_changes:
            module = change["module"]
            functions = change["functions"]
            classes = change["classes"]
            direct_module = bool(module) and any(
                _import_matches_module(imported, module) for imported in imports
            )
            class_context = _matches_class_context(
                classes,
                test.get("test_class") or "",
                references,
                called_names,
                imports,
            )
            direct_context = direct_module or class_context or not module

            for function in functions:
                normalised = normalise_name(function)
                if len(normalised) < 3:
                    continue

                if direct_context and normalised in called_names:
                    confidence = max(confidence, 0.96)
                    reasons.append(
                        f"Test directly calls changed symbol '{_symbol_label(change, function)}'"
                    )
                    continue

                if (
                    legacy_mode
                    and normalised in normalise_name(test_name)
                    and not has_call_metadata
                ):
                    confidence = max(confidence, 0.95)
                    reasons.append(
                        f"Test name directly matches changed function '{function}'"
                    )
                    continue

                if (
                    direct_context
                    and not has_call_metadata
                    and _semantic_name_match(function, change["domains"], test_tokens)
                ):
                    confidence = max(confidence, 0.92)
                    reasons.append(
                        f"Test name matches changed symbol '{_symbol_label(change, function)}'"
                    )
                    continue

                affected_module = _matching_affected_module(
                    imports, change["affected_modules"], module
                )
                if affected_module and normalised in called_names:
                    confidence = max(confidence, 0.92)
                    reasons.append(
                        f"Test calls changed symbol '{_symbol_label(change, function)}' "
                        f"through dependent module '{affected_module}'"
                    )
                    continue
                if affected_module and _semantic_name_match(
                    function, change["domains"], test_tokens
                ):
                    confidence = max(confidence, 0.88)
                    reasons.append(
                        f"Test name maps changed symbol '{_symbol_label(change, function)}' "
                        f"through dependent module '{affected_module}'"
                    )

            if change["module_level"] and direct_module:
                confidence = max(confidence, 0.90)
                reasons.append(
                    f"Test directly imports changed module '{module}'"
                )
            elif not functions and classes and class_context:
                confidence = max(confidence, 0.90)
                reasons.append(
                    f"Test directly uses changed class '{sorted(classes)[0]}'"
                )

        if legacy_mode:
            for class_name in changed_classes:
                normalised = normalise_name(class_name)
                if normalised and (
                    normalised in normalise_name(test.get("test_class") or "")
                    or normalised in normalise_name(test_name)
                    or normalised in references
                ):
                    confidence = max(confidence, 0.90)
                    reasons.append(
                        f"Test is associated with changed class '{class_name}'"
                    )

        if confidence == 0:
            continue

        recommendations.append(
            _recommendation(test, confidence, list(dict.fromkeys(reasons)))
        )

    recommendations.sort(key=lambda item: (-item["confidence"], item["node_id"]))
    return recommendations


def select_all_tests(
    discovered_tests: list[dict],
    reason: str,
    confidence: float = 0.50,
) -> list[dict]:
    return [
        _recommendation(test, confidence, [reason])
        for test in sorted(
            discovered_tests,
            key=lambda item: item.get("node_id") or _legacy_node_id(item),
        )
    ]


def _production_changes(
    changed_functions: list[str],
    changed_classes: list[str],
    changed_files: list[dict],
) -> list[dict]:
    changes: list[dict] = []
    for file in changed_files:
        path = _path(file["path"])
        if file.get("is_test_file", _is_test_path(path)):
            continue

        module = file.get("module") or _module_for_path(path)
        functions = set(file.get("changed_functions", []))
        classes = set(file.get("changed_classes", []))
        module_level = bool(file.get("module_level_change"))
        if not functions and not classes and not module_level:
            continue

        changes.append(
            {
                "path": path,
                "module": module,
                "functions": functions,
                "classes": classes,
                "module_level": module_level,
                "affected_modules": set(file.get("affected_modules", [])),
                "domains": _domain_tokens(module, classes),
            }
        )

    if not changes and not changed_files and (changed_functions or changed_classes):
        changes.append(
            {
                "path": "",
                "module": "",
                "functions": set(changed_functions),
                "classes": set(changed_classes),
                "module_level": False,
                "affected_modules": set(),
                "domains": _domain_tokens("", set(changed_classes)),
            }
        )
    return changes


def _changed_test_impacts(
    changed_files: list[dict],
    discovered_tests: list[dict],
) -> dict[str, dict]:
    tests_by_file: dict[str, list[dict]] = {}
    for test in discovered_tests:
        tests_by_file.setdefault(_path(test["test_file"]), []).append(test)

    impacts: dict[str, dict] = {}
    for file in changed_files:
        path = _path(file["path"])
        if not file.get("is_test_file", _is_test_path(path)):
            continue

        tests = tests_by_file.get(path, [])
        changed_lines = set(file.get("changed_lines", []))
        positions_available = bool(tests) and all(
            isinstance(test.get("start_line"), int)
            and isinstance(test.get("end_line"), int)
            for test in tests
        )

        direct_nodes: set[tuple[str, int | None, int | None]] = set()
        if changed_lines and positions_available:
            for test in tests:
                if any(
                    test["start_line"] <= line <= test["end_line"]
                    for line in changed_lines
                ):
                    direct_nodes.add(_test_impact_key(test))

        changed_lines_are_test_scoped = (
            bool(changed_lines)
            and positions_available
            and all(
                any(
                    test["start_line"] <= line <= test["end_line"]
                    for test in tests
                )
                for line in changed_lines
            )
        )
        functions = set(file.get("changed_functions", []))
        discovered_test_names = {
            test.get("test_name") for test in tests
        }
        non_test_function_changed = any(
            function not in discovered_test_names
            and not function.startswith("test_")
            for function in functions
        ) and not changed_lines_are_test_scoped
        class_only_change = (
            bool(file.get("changed_classes"))
            and not direct_nodes
            and not changed_lines_are_test_scoped
        )
        broad = (
            not positions_available
            or (
                bool(file.get("module_level_change"))
                and not changed_lines_are_test_scoped
            )
            or non_test_function_changed
            or class_only_change
        )
        impacts[path] = {"direct_nodes": direct_nodes, "broad": broad}

    return impacts


def _test_impact_key(test: dict) -> tuple[str, int | None, int | None]:
    return (
        test.get("node_id") or _legacy_node_id(test),
        test.get("start_line"),
        test.get("end_line"),
    )


def _matches_class_context(
    classes: set[str],
    test_class: str,
    references: set[str],
    called_names: set[str],
    imports: set[str],
) -> bool:
    import_leaves = {
        normalise_name(imported.rsplit(".", 1)[-1]) for imported in imports
    }
    normalised_test_class = normalise_name(test_class)
    return any(
        (normalised := normalise_name(class_name))
        and (
            normalised in references
            or normalised in called_names
            or normalised in import_leaves
            or normalised in normalised_test_class
        )
        for class_name in classes
    )


def _matching_affected_module(
    imports: set[str],
    affected_modules: set[str],
    direct_module: str,
) -> str | None:
    for affected in sorted(affected_modules):
        if affected == direct_module or _is_test_path(affected.replace(".", "/") + ".py"):
            continue
        if any(_import_matches_module(imported, affected) for imported in imports):
            return affected
    return None


def _semantic_name_match(
    function: str,
    domains: set[str],
    test_tokens: set[str],
) -> bool:
    function_tokens = _identifier_tokens(function)
    if not function_tokens:
        return False

    meaningful = function_tokens - _GENERIC_FUNCTIONS
    if meaningful:
        function_match = meaningful <= test_tokens
    else:
        function_match = function_tokens <= test_tokens
    if not function_match:
        return False

    needs_domain = bool(function_tokens & _GENERIC_FUNCTIONS)
    return not needs_domain or bool(domains & test_tokens)


def _domain_tokens(module: str, classes: set[str]) -> set[str]:
    domains: set[str] = set()
    if module:
        stem = module.rsplit(".", 1)[-1]
        domains.update(_identifier_tokens(stem))
        if stem.endswith("s") and len(stem) > 3:
            domains.add(stem[:-1].lower())

    for class_name in classes:
        tokens = _identifier_tokens(class_name)
        domains.update(tokens - {"service", "controller", "manager", "repository"})
    return domains


def _identifier_tokens(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", expanded)
        if token
    }


def _symbol_label(change: dict, function: str) -> str:
    if len(change["classes"]) == 1:
        return f"{next(iter(change['classes']))}.{function}"
    if change["module"]:
        return f"{change['module']}.{function}"
    return function


def _recommendation(test: dict, confidence: float, reasons: list[str]) -> dict:
    if confidence >= 0.98:
        priority = "critical"
    elif confidence >= 0.85:
        priority = "high"
    elif confidence >= 0.65:
        priority = "medium"
    else:
        priority = "low"

    return {
        "test_file": test["test_file"],
        "test_name": test["test_name"],
        "test_class": test.get("test_class"),
        "node_id": test.get("node_id") or _legacy_node_id(test),
        "framework": test.get("framework", "pytest"),
        "priority": priority,
        "confidence": confidence,
        "reasons": reasons,
    }


def _legacy_node_id(test: dict) -> str:
    parts = [test["test_file"]]
    if test.get("test_class"):
        parts.append(test["test_class"])
    parts.append(test["test_name"])
    return "::".join(parts)


def _import_matches_module(imported: str, module: str) -> bool:
    return (
        imported == module
        or imported.startswith(module + ".")
        or module.startswith(imported + ".")
        or imported.startswith(module + "/")
        or module.startswith(imported + "/")
    )


def _module_for_path(path: str) -> str:
    value = path[:-3] if path.endswith(".py") else path
    parts = [part for part in value.split("/") if part]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_test_path(path: str) -> bool:
    return is_test_path(path)


def _path(value: str) -> str:
    return Path(value).as_posix()
