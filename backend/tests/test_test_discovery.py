
from app.services.test_discovery import discover_tests


def test_discovers_standalone_test_functions(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_auth.py").write_text(
        """
def test_login():
    pass

def test_logout():
    pass
"""
    )

    result = discover_tests(tests_dir, tmp_path)

    assert len(result) == 2
    assert result[0]["test_name"] == "test_login"
    assert result[1]["test_name"] == "test_logout"


def test_discovers_test_class_methods(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_users.py").write_text(
        """
class TestUserService:
    def test_get_user(self):
        pass

    def test_delete_user(self):
        pass
"""
    )

    result = discover_tests(tests_dir, tmp_path)

    assert len(result) == 2
    assert result[0]["test_class"] == "TestUserService"
    assert result[0]["test_name"] == "test_get_user"


def test_ignores_non_test_functions(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_auth.py").write_text(
        """
def helper_function():
    pass

def test_login():
    pass
"""
    )

    result = discover_tests(tests_dir, tmp_path)

    assert len(result) == 1
    assert result[0]["test_name"] == "test_login"


def test_handles_invalid_python_file(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_broken.py").write_text(
        "def test_something(:"
    )

    assert discover_tests(tests_dir, tmp_path) == []


def test_handles_missing_directory(tmp_path):
    assert discover_tests(tmp_path / "missing") == []
