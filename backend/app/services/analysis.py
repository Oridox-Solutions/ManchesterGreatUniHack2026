import tempfile
from pathlib import Path

from app.models.analyse import (
    AnalysisResponse,
    ChangedFile,
    PullRequestInfo,
    RecommendedTest,
)
from app.services.code_analysis import analyse_python_impact
from app.services.dependencies import (
    build_import_graph,
    find_reverse_dependencies,
    module_name_for_path,
)
from app.services.diff_parser import parse_changed_lines
from app.services.github import GitHubClient, GitHubPullRequest
from app.services.risk import calculate_risk
from app.services.test_discovery import discover_project_tests
from app.services.test_matching import match_tests, select_all_tests


DOCUMENTATION_EXTENSIONS = {".md", ".rst", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".svg"}
SUPPORTED_CODE_EXTENSIONS = {".py"}
CONFIG_NAMES = {
    "requirements.txt", "pyproject.toml", "poetry.lock", "pipfile", "pipfile.lock",
    "package.json", "package-lock.json", "yarn.lock", "jenkinsfile", "dockerfile",
}


class PullRequestAnalysisService:
    def __init__(self, github_client: GitHubClient | None = None):
        self.github_client = github_client or GitHubClient()

    async def analyse(self, pull_request_url: str) -> AnalysisResponse:
        pull_request = await self.github_client.fetch_pull_request(pull_request_url)

        with tempfile.TemporaryDirectory(prefix="testpilot-") as directory:
            project_root = await self.github_client.download_head_archive(
                pull_request, Path(directory)
            )
            return self.analyse_repository(pull_request, project_root)

    def analyse_repository(
        self,
        pull_request: GitHubPullRequest,
        project_root: str | Path,
    ) -> AnalysisResponse:
        root = Path(project_root).resolve()
        discovered_tests = discover_project_tests(root)
        import_graph = build_import_graph(root)

        changed_modules = {
            module_name_for_path(file.path)
            for file in pull_request.changed_files
            if Path(file.path).suffix.lower() == ".py"
            and not _looks_like_test(file.path)
        }
        affected_modules_by_module = {
            module: find_reverse_dependencies(import_graph, {module})
            for module in changed_modules
        }

        response_files: list[ChangedFile] = []
        matcher_files: list[dict] = []
        all_functions: set[str] = set()
        all_classes: set[str] = set()
        requires_conservative_selection = False
        has_executable_change = False

        for file in pull_request.changed_files:
            extension = Path(file.path).suffix.lower()
            name = Path(file.path).name.lower()
            module = module_name_for_path(file.path)
            parsed_lines = parse_changed_lines(file.patch)
            functions: list[str] = []
            classes: list[str] = []
            module_level = False
            status = "unsupported"

            if extension in SUPPORTED_CODE_EXTENSIONS:
                has_executable_change = True
                source_path = (root / file.path).resolve()
                if root != source_path and root not in source_path.parents:
                    status = "missing_source"
                    module_level = True
                    requires_conservative_selection = True
                elif not source_path.is_file():
                    status = "missing_source"
                    module_level = True
                    requires_conservative_selection = True
                else:
                    try:
                        source = source_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        status = "missing_source"
                        module_level = True
                        requires_conservative_selection = True
                    else:
                        impact = analyse_python_impact(source, parsed_lines.new)
                        functions = impact["changed_functions"]
                        classes = impact["changed_classes"]
                        module_level = impact["module_level_change"]
                        status = impact["analysis_status"]
                        if status in {"file_level", "parse_failed"}:
                            requires_conservative_selection = True
            elif extension in DOCUMENTATION_EXTENSIONS:
                status = "unsupported"
            else:
                has_executable_change = True
                status = "unsupported"
                requires_conservative_selection = True

            if name in CONFIG_NAMES or file.path.startswith(".github/"):
                has_executable_change = True
                module_level = True
                requires_conservative_selection = True

            if not _looks_like_test(file.path):
                all_functions.update(functions)
                all_classes.update(classes)
            changed_file = ChangedFile(
                path=file.path,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                changed_functions=functions,
                changed_classes=classes,
                changed_lines=parsed_lines.new,
                analysis_status=status,
                module_level_change=module_level,
            )
            response_files.append(changed_file)
            matcher_files.append(
                changed_file.model_dump()
                | {
                    "module": module,
                    "is_test_file": _looks_like_test(file.path),
                    "affected_modules": sorted(
                        affected_modules_by_module.get(module, set())
                    ),
                }
            )

        recommendations = match_tests(
            sorted(all_functions),
            sorted(all_classes),
            discovered_tests,
            matcher_files,
        )

        selection_mode = "targeted"
        if requires_conservative_selection:
            selection_mode = "conservative"
            recommendations = select_all_tests(
                discovered_tests,
                "Full suite selected because part of the change could not be analysed safely",
            )
        elif has_executable_change and not recommendations:
            selection_mode = "conservative"
            recommendations = select_all_tests(
                discovered_tests,
                "Full suite selected because no reliable test relationship was found",
            )

        risk_score, risk_level = calculate_risk(
            [file.model_dump() for file in response_files],
            len(recommendations),
            selection_mode,
        )
        summary = _summary(
            pull_request,
            len(discovered_tests),
            len(recommendations),
            selection_mode,
        )

        return AnalysisResponse(
            pull_request=PullRequestInfo(
                title=pull_request.title,
                number=pull_request.number,
                repository=pull_request.repository,
                url=pull_request.url,
                base_sha=pull_request.base_sha,
                head_sha=pull_request.head_sha,
            ),
            risk_score=risk_score,
            risk_level=risk_level,
            selection_mode=selection_mode,
            summary=summary,
            changed_files=response_files,
            recommended_tests=[
                RecommendedTest.model_validate(item) for item in recommendations
            ],
            total_tests_discovered=len(discovered_tests),
            tests_selected=len(recommendations),
        )


def _looks_like_test(path: str) -> bool:
    file = Path(path)
    return (
        file.name.startswith("test_")
        or file.name.endswith("_test.py")
        or "tests" in file.parts
    )


def _summary(
    pull_request: GitHubPullRequest,
    discovered: int,
    selected: int,
    mode: str,
) -> str:
    if discovered == 0:
        return (
            f"Analysed {len(pull_request.changed_files)} changed files, but no supported "
            "Python tests were discovered."
        )
    if selected == 0:
        return (
            f"Analysed {len(pull_request.changed_files)} changed files. "
            "No tests are needed for documentation-only changes."
        )
    if mode == "conservative":
        return (
            f"Selected all {selected} discovered tests because at least one change "
            "could not be mapped safely."
        )
    saving = max(0, discovered - selected)
    return (
        f"Selected {selected} of {discovered} tests from "
        f"{len(pull_request.changed_files)} changed files, skipping {saving} unrelated tests."
    )
