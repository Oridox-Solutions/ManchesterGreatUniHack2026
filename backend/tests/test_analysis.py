import asyncio

from app.services.analysis import PullRequestAnalysisService
from app.services.github import GitHubChangedFile, GitHubPullRequest


class FakeGitHubClient:
    def __init__(self, repository):
        self.repository = repository
        self.pull_request = GitHubPullRequest(
            owner="example",
            repo="demo",
            number=12,
            title="Protect archived tasks",
            url="https://github.com/example/demo/pull/12",
            base_sha="base123",
            head_sha="head456",
            changed_files=[
                GitHubChangedFile(
                    path="app/services/tasks.py",
                    status="modified",
                    additions=2,
                    deletions=1,
                    patch=(
                        "@@ -1,3 +1,4 @@\n"
                        " class TaskService:\n"
                        "     def create(self):\n"
                        "-        return None\n"
                        "+        archived = False\n"
                        "+        return archived\n"
                    ),
                )
            ],
        )

    async def fetch_pull_request(self, url):
        return self.pull_request

    async def download_head_archive(self, pull_request, destination):
        return self.repository


def make_repository(tmp_path):
    service = tmp_path / "app" / "services"
    service.mkdir(parents=True)
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (service / "__init__.py").write_text("", encoding="utf-8")
    (service / "tasks.py").write_text(
        "class TaskService:\n"
        "    def create(self):\n"
        "        archived = False\n"
        "        return archived\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_tasks.py").write_text(
        "import unittest\n"
        "from app.services.tasks import TaskService\n\n"
        "class TaskServiceTests(unittest.TestCase):\n"
        "    def test_create(self):\n"
        "        self.assertFalse(TaskService().create())\n",
        encoding="utf-8",
    )


def test_analysis_service_runs_complete_pipeline(tmp_path):
    make_repository(tmp_path)
    service = PullRequestAnalysisService(FakeGitHubClient(tmp_path))
    result = asyncio.run(
        service.analyse("https://github.com/example/demo/pull/12")
    )
    assert result.selection_mode == "targeted"
    assert result.total_tests_discovered == 1
    assert result.tests_selected == 1
    assert result.recommended_tests[0].test_class == "TaskServiceTests"
    assert result.changed_files[0].changed_functions == ["create"]


def test_unknown_patch_selects_full_suite(tmp_path):
    make_repository(tmp_path)
    client = FakeGitHubClient(tmp_path)
    original = client.pull_request.changed_files[0]
    client.pull_request = GitHubPullRequest(
        owner="example",
        repo="demo",
        number=13,
        title="Unknown task change",
        url="https://github.com/example/demo/pull/13",
        base_sha="base123",
        head_sha="head789",
        changed_files=[
            GitHubChangedFile(
                path=original.path,
                status=original.status,
                additions=original.additions,
                deletions=original.deletions,
                patch=None,
            )
        ],
    )
    result = PullRequestAnalysisService(client).analyse_repository(
        client.pull_request, tmp_path
    )
    assert result.selection_mode == "conservative"
    assert result.tests_selected == result.total_tests_discovered == 1


def test_dependency_reasons_are_scoped_to_each_changed_module(tmp_path):
    make_repository(tmp_path)
    (tmp_path / "app" / "services" / "projects.py").write_text(
        '''class ProjectService:
    def create(self):
        fixed = True
        return fixed
''',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_tasks.py").write_text(
        '''import unittest
from app.services.tasks import TaskService

class TaskServiceTests(unittest.TestCase):
    def test_cannot_create_task_in_archived_project(self):
        self.assertFalse(TaskService().create())
''',
        encoding="utf-8",
    )
    pull_request = GitHubPullRequest(
        owner="example",
        repo="demo",
        number=14,
        title="Fix project and task creation",
        url="https://github.com/example/demo/pull/14",
        base_sha="base123",
        head_sha="head999",
        changed_files=[
            GitHubChangedFile(
                path="app/services/projects.py",
                status="modified",
                additions=2,
                deletions=1,
                patch='''@@ -1,3 +1,4 @@
 class ProjectService:
     def create(self):
-        return None
+        fixed = True
+        return fixed
''',
            ),
            GitHubChangedFile(
                path="app/services/tasks.py",
                status="modified",
                additions=2,
                deletions=1,
                patch='''@@ -1,3 +1,4 @@
 class TaskService:
     def create(self):
-        return None
+        archived = False
+        return archived
''',
            ),
        ],
    )

    result = PullRequestAnalysisService().analyse_repository(
        pull_request, tmp_path
    )

    assert result.tests_selected == 1
    reasons = result.recommended_tests[0].reasons
    assert any("TaskService.create" in reason for reason in reasons)
    assert all("ProjectService.create" not in reason for reason in reasons)
