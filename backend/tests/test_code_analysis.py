
from app.services.code_analysis import analyse_python_file


def test_identifies_changed_function():
    source = """
def get_user():
    return "user"

def delete_user():
    return "deleted"
"""

    result = analyse_python_file(source, [3])

    assert result["changed_functions"] == ["get_user"]
    assert result["changed_classes"] == []


def test_identifies_changed_class():
    source = """
class UserService:
    def get_user(self):
        return "user"
"""

    result = analyse_python_file(source, [3])

    assert result["changed_functions"] == ["get_user"]
    assert result["changed_classes"] == ["UserService"]


def test_handles_no_changed_lines():
    result = analyse_python_file("def hello(): pass", [])

    assert result == {
        "changed_functions": [],
        "changed_classes": []
    }
