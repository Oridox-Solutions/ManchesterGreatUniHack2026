from app.services.test_discovery import discover_project_tests, discover_tests


def test_discovers_standalone_test_functions(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "def test_login():\n    pass\n\ndef test_logout():\n    pass\n",
        encoding="utf-8",
    )
    result = discover_tests(tests_dir, tmp_path)
    assert [test["test_name"] for test in result] == ["test_login", "test_logout"]
    assert result[0]["node_id"] == "tests/test_auth.py::test_login"


def test_discovers_pytest_class_methods(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_users.py").write_text(
        "class TestUserService:\n"
        "    def test_get_user(self):\n        pass\n\n"
        "    def test_delete_user(self):\n        pass\n",
        encoding="utf-8",
    )
    result = discover_tests(tests_dir, tmp_path)
    assert len(result) == 2
    assert result[0]["test_class"] == "TestUserService"
    assert result[0]["framework"] == "pytest"


def test_discovers_unittest_class_that_does_not_start_with_test(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_tasks.py").write_text(
        "import unittest\n"
        "from app.tasks import TaskService\n\n"
        "class TaskServiceTests(unittest.TestCase):\n"
        "    def test_create_task(self):\n"
        "        service = TaskService()\n"
        "        service.create()\n",
        encoding="utf-8",
    )
    result = discover_tests(tests_dir, tmp_path)
    assert len(result) == 1
    assert result[0]["test_class"] == "TaskServiceTests"
    assert result[0]["framework"] == "unittest"
    assert result[0]["node_id"].endswith(
        "::TaskServiceTests::test_create_task"
    )
    assert "app.tasks" in result[0]["imports"]
    assert "create" in result[0]["referenced_names"]
    assert "create" in result[0]["called_names"]
    assert result[0]["start_line"] < result[0]["end_line"]


def test_ignores_non_test_functions(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "def helper_function():\n    pass\n\ndef test_login():\n    pass\n",
        encoding="utf-8",
    )
    result = discover_tests(tests_dir, tmp_path)
    assert [test["test_name"] for test in result] == ["test_login"]


def test_handles_invalid_python_file(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_broken.py").write_text("def test_something(:", encoding="utf-8")
    assert discover_tests(tests_dir, tmp_path) == []


def test_handles_missing_directory(tmp_path):
    assert discover_tests(tmp_path / "missing") == []


def test_project_discovery_ignores_non_test_modules(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text(
        "def test_named_but_not_in_test_file(): pass\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_service.py").write_text(
        "def test_real(): pass\n", encoding="utf-8"
    )
    result = discover_project_tests(tmp_path)
    assert [test["test_name"] for test in result] == ["test_real"]
