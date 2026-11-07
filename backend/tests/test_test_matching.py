from app.services.test_matching import match_tests, select_all_tests


def _test(
    name,
    *,
    file="tests/test_tasks.py",
    test_class="TaskServiceTests",
    imports=None,
    calls=None,
    start=1,
    end=5,
):
    return {
        "test_file": file,
        "test_name": name,
        "test_class": test_class,
        "node_id": f"{file}::{test_class}::{name}" if test_class else f"{file}::{name}",
        "framework": "unittest",
        "imports": imports or [],
        "referenced_names": calls or [],
        "called_names": calls or [],
        "start_line": start,
        "end_line": end,
    }


def _change(
    *,
    path="app/services/tasks.py",
    functions=None,
    classes=None,
    affected=None,
    changed_lines=None,
    module_level=False,
):
    return {
        "path": path,
        "changed_functions": functions or [],
        "changed_classes": classes or [],
        "affected_modules": affected or [],
        "changed_lines": changed_lines or [],
        "module_level_change": module_level,
    }


def test_legacy_function_name_matching_remains_available():
    tests = [
        {"test_file": "tests/test_auth.py", "test_name": "test_authenticate_user"},
        {"test_file": "tests/test_users.py", "test_name": "test_delete_user"},
    ]
    result = match_tests(["authenticate_user"], [], tests)
    assert [item["test_name"] for item in result] == ["test_authenticate_user"]
    assert result[0]["confidence"] == 0.95


def test_direct_call_in_changed_module_is_selected():
    tests = [
        _test(
            "test_creates_task",
            imports=["app.services.tasks", "app.services.tasks.TaskService"],
            calls=["create"],
        ),
        _test(
            "test_lists_tasks",
            imports=["app.services.tasks", "app.services.tasks.TaskService"],
            calls=["list_for"],
            start=7,
            end=11,
        ),
    ]
    result = match_tests(
        ["create"],
        ["TaskService"],
        tests,
        [_change(functions=["create"], classes=["TaskService"])],
    )
    assert [item["test_name"] for item in result] == ["test_creates_task"]
    assert result[0]["confidence"] == 0.96
    assert "TaskService.create" in result[0]["reasons"][0]


def test_generic_method_name_is_scoped_to_owning_module():
    tests = [
        _test(
            "test_create_project",
            file="tests/test_projects.py",
            test_class="ProjectServiceTests",
            imports=["app.services.projects.ProjectService"],
            calls=["create"],
        )
    ]
    result = match_tests(
        ["create"],
        ["TaskService"],
        tests,
        [_change(functions=["create"], classes=["TaskService"])],
    )
    assert result == []


def test_broad_dependent_import_requires_semantic_test_name():
    tests = [
        _test(
            "test_create_task_appears_in_task_list",
            file="tests/integration/test_api.py",
            test_class="ApiIntegrationTests",
            imports=["app.api"],
            calls=["request"],
        ),
        _test(
            "test_register_returns_created_and_session",
            file="tests/integration/test_api.py",
            test_class="ApiIntegrationTests",
            imports=["app.api"],
            calls=["request"],
            start=7,
            end=11,
        ),
        _test(
            "test_health_check_is_public",
            file="tests/integration/test_api.py",
            test_class="ApiIntegrationTests",
            imports=["app.api"],
            calls=["request"],
            start=13,
            end=17,
        ),
    ]
    change = _change(
        functions=["create"],
        classes=["TaskService"],
        affected=["app.services.tasks", "app.api"],
    )
    result = match_tests(["create"], ["TaskService"], tests, [change])
    assert [item["test_name"] for item in result] == [
        "test_create_task_appears_in_task_list"
    ]
    assert result[0]["confidence"] == 0.88


def test_changed_test_selects_only_overlapping_test():
    tests = [
        _test("test_existing", start=5, end=8),
        _test("test_new_regression", start=10, end=16),
    ]
    changed_test = _change(
        path="tests/test_tasks.py",
        functions=["test_new_regression"],
        classes=["TaskServiceTests"],
        changed_lines=[10, 11, 12, 13, 14, 15, 16],
    )
    result = match_tests([], [], tests, [changed_test])
    assert [item["test_name"] for item in result] == ["test_new_regression"]
    assert result[0]["confidence"] == 1.0


def test_shared_test_fixture_change_selects_whole_file():
    tests = [
        _test("test_first", start=10, end=12),
        _test("test_second", start=14, end=16),
    ]
    fixture_change = _change(
        path="tests/test_tasks.py",
        functions=["setUp"],
        classes=["TaskServiceTests"],
        changed_lines=[5, 6],
    )
    result = match_tests([], [], tests, [fixture_change])
    assert {item["test_name"] for item in result} == {"test_first", "test_second"}
    assert all(item["confidence"] == 0.90 for item in result)


def test_module_level_production_change_selects_direct_importers():
    tests = [
        _test(
            "test_task_defaults",
            imports=["app.services.tasks.TaskService"],
            calls=["TaskService"],
        )
    ]
    change = _change(module_level=True)
    result = match_tests([], [], tests, [change])
    assert [item["test_name"] for item in result] == ["test_task_defaults"]
    assert result[0]["confidence"] == 0.90


def test_conservative_selection_returns_every_test():
    tests = [
        {"test_file": "tests/test_a.py", "test_name": "test_a"},
        {"test_file": "tests/test_b.py", "test_name": "test_b"},
    ]
    result = select_all_tests(tests, "Safety fallback")
    assert len(result) == 2
    assert all(item["reasons"] == ["Safety fallback"] for item in result)


def test_handles_empty_inputs():
    assert match_tests([], [], []) == []
