from app.services.risk import calculate_risk


def test_test_files_do_not_inflate_risk_to_critical():
    files = [
        {
            "path": f"app/services/{name}.py",
            "additions": 12,
            "deletions": 2,
            "status": "modified",
            "module_level_change": False,
            "analysis_status": "analysed",
        }
        for name in ("auth", "projects", "search", "tasks")
    ]
    files.extend(
        {
            "path": f"tests/unit/test_{name}.py",
            "additions": 12,
            "deletions": 0,
            "status": "modified",
            "module_level_change": True,
            "analysis_status": "analysed",
        }
        for name in ("auth", "projects", "search", "tasks")
    )

    score, level = calculate_risk(files, tests_selected=30, selection_mode="targeted")

    assert score < 80
    assert level in {"medium", "high"}


def test_unanalysable_production_change_remains_high_risk():
    files = [
        {
            "path": "app/security.py",
            "additions": 100,
            "deletions": 20,
            "status": "modified",
            "module_level_change": True,
            "analysis_status": "parse_failed",
        }
    ]
    score, level = calculate_risk(files, tests_selected=5, selection_mode="conservative")
    assert score >= 60
    assert level in {"high", "critical"}
