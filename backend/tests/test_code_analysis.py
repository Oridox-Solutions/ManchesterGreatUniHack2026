from app.services.code_analysis import analyse_python_file, analyse_python_impact


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


def test_identifies_changed_class_and_method():
    source = """
class UserService:
    def get_user(self):
        return "user"
"""
    result = analyse_python_file(source, [3])
    assert result["changed_functions"] == ["get_user"]
    assert result["changed_classes"] == ["UserService"]


def test_handles_no_changed_lines_with_file_level_fallback():
    result = analyse_python_impact("def hello(): pass", [])
    assert result["changed_functions"] == []
    assert result["changed_classes"] == []
    assert result["module_level_change"] is True
    assert result["analysis_status"] == "file_level"


def test_marks_module_level_constant_change():
    source = 'PRIORITIES = {"low", "high"}\n\ndef create():\n    pass\n'
    result = analyse_python_impact(source, [1])
    assert result["module_level_change"] is True
    assert result["changed_functions"] == []


def test_ignores_changed_blank_lines_outside_a_function():
    source = "def hello():\n    return True\n\n"
    result = analyse_python_impact(source, [2, 3])
    assert result["changed_functions"] == ["hello"]
    assert result["module_level_change"] is False


def test_reports_parse_failure_conservatively():
    result = analyse_python_impact("def broken(:", [1])
    assert result["analysis_status"] == "parse_failed"
    assert result["module_level_change"] is True


def test_decorator_line_affects_function():
    source = "@route('/users')\ndef list_users():\n    return []\n"
    result = analyse_python_impact(source, [1])
    assert result["changed_functions"] == ["list_users"]
