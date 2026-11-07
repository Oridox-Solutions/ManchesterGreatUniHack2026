from pathlib import Path

from app.services.language_support import is_test_path


SENSITIVE_TERMS = {
    "auth", "security", "permission", "migration", "database", "schema",
    "payment", "billing", "deploy", "workflow", "requirements", "lock",
}


def calculate_risk(
    changed_files: list[dict],
    tests_selected: int,
    selection_mode: str,
) -> tuple[int, str]:
    production_files = [
        file for file in changed_files
        if not _is_documentation(file["path"]) and not _is_test(file["path"])
    ]
    test_files = [
        file for file in changed_files if _is_test(file["path"])
    ]
    production_churn = sum(
        int(file.get("additions", 0)) + int(file.get("deletions", 0))
        for file in production_files
    )

    score = min(30, len(production_files) * 6)
    score += min(8, len(test_files) * 2)
    score += min(20, production_churn // 10)

    sensitive_files = 0
    for file in production_files:
        path = Path(file["path"]).as_posix().lower()
        if any(term in path for term in SENSITIVE_TERMS):
            sensitive_files += 1
        if file.get("status") == "removed":
            score += 8
        if file.get("module_level_change"):
            score += 6
        if file.get("analysis_status") in {"parse_failed", "missing_source"}:
            score += 20

    score += min(20, sensitive_files * 15)

    if selection_mode == "conservative":
        score += 10
    if tests_selected == 0 and production_files:
        score += 20

    score = max(0, min(100, score))
    if score >= 80:
        level = "critical"
    elif score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"
    return score, level


def _is_test(path: str) -> bool:
    return is_test_path(path)


def _is_documentation(path: str) -> bool:
    return Path(path).suffix.lower() in {
        ".md", ".rst", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".svg"
    }
