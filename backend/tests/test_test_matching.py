
from app.services.test_matching import match_tests


def test_matches_changed_function():
    tests = [
        {
            "test_file": "tests/test_auth.py",
            "test_name": "test_authenticate_user",
            "test_class": None
        },
        {
            "test_file": "tests/test_users.py",
            "test_name": "test_delete_user",
            "test_class": None
        }
    ]

    result = match_tests(
        ["authenticate_user"],
        [],
        tests
    )

    assert len(result) == 1
    assert result[0]["test_name"] == "test_authenticate_user"
    assert result[0]["priority"] == "high"
    assert result[0]["confidence"] == 0.95


def test_matches_changed_class():
    tests = [
        {
            "test_file": "tests/test_auth.py",
            "test_name": "test_login",
            "test_class": "TestAuthenticationService"
        }
    ]

    result = match_tests(
        [],
        ["AuthenticationService"],
        tests
    )

    assert len(result) == 1
    assert result[0]["priority"] == "high"
    assert result[0]["confidence"] == 0.90


def test_ignores_unrelated_tests():
    tests = [
        {
            "test_file": "tests/test_users.py",
            "test_name": "test_delete_user",
            "test_class": None
        }
    ]

    result = match_tests(
        ["authenticate_user"],
        [],
        tests
    )

    assert result == []


def test_returns_multiple_matching_tests():
    tests = [
        {
            "test_file": "tests/test_auth.py",
            "test_name": "test_authenticate_user",
            "test_class": None
        },
        {
            "test_file": "tests/test_auth.py",
            "test_name": "test_authenticate_user_invalid_password",
            "test_class": None
        }
    ]

    result = match_tests(
        ["authenticate_user"],
        [],
        tests
    )

    assert len(result) == 2
    assert all(test["priority"] == "high" for test in result)


def test_handles_empty_inputs():
    assert match_tests([], [], []) == []
