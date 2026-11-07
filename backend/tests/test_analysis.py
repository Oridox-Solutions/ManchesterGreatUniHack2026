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



def test_javascript_change_selects_only_directly_calling_vitest_test(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"devDependencies": {"vitest": "latest"}}',
        encoding="utf-8",
    )
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "auth.ts").write_text(
        '''export function login(email: string) {
  const normalised = email.trim();
  return normalised;
}

export function logout() {
  return true;
}
''',
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "auth.test.ts").write_text(
        '''import { login, logout } from "../src/auth";

test("login trims email", () => {
  expect(login(" example@test.com ")).toBe("example@test.com");
});

test("logout clears session", () => {
  expect(logout()).toBe(true);
});
''',
        encoding="utf-8",
    )
    pull_request = GitHubPullRequest(
        owner="example",
        repo="typescript-demo",
        number=21,
        title="Normalise login email",
        url="https://github.com/example/typescript-demo/pull/21",
        base_sha="base",
        head_sha="head",
        changed_files=[
            GitHubChangedFile(
                path="src/auth.ts",
                status="modified",
                additions=1,
                deletions=1,
                patch='''@@ -1,4 +1,4 @@
 export function login(email: string) {
-  const normalised = email;
+  const normalised = email.trim();
   return normalised;
 }
''',
            )
        ],
    )

    result = PullRequestAnalysisService().analyse_repository(pull_request, tmp_path)

    assert result.selection_mode == "targeted"
    assert result.total_tests_discovered == 2
    assert [test.test_name for test in result.recommended_tests] == [
        "login trims email"
    ]
    assert result.recommended_tests[0].framework == "vitest"
    assert "src/auth.login" in result.recommended_tests[0].reasons[0]


def test_java_change_selects_only_directly_calling_junit_test(tmp_path):
    source_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "AuthService.java").write_text(
        '''package com.example;

public class AuthService {
    public boolean login(String email) {
        return email != null && !email.isBlank();
    }

    public boolean logout() {
        return true;
    }
}
''',
        encoding="utf-8",
    )
    test_dir = tmp_path / "src" / "test" / "java" / "com" / "example"
    test_dir.mkdir(parents=True)
    (test_dir / "AuthServiceTest.java").write_text(
        '''package com.example;

import org.junit.jupiter.api.Test;

class AuthServiceTest {
    private final AuthService service = new AuthService();

    @Test
    void loginRejectsBlankEmail() {
        service.login(" ");
    }

    @Test
    void logoutClearsSession() {
        service.logout();
    }
}
''',
        encoding="utf-8",
    )
    pull_request = GitHubPullRequest(
        owner="example",
        repo="java-demo",
        number=22,
        title="Reject blank login",
        url="https://github.com/example/java-demo/pull/22",
        base_sha="base",
        head_sha="head",
        changed_files=[
            GitHubChangedFile(
                path="src/main/java/com/example/AuthService.java",
                status="modified",
                additions=1,
                deletions=1,
                patch='''@@ -3,5 +3,5 @@
 public class AuthService {
     public boolean login(String email) {
-        return email != null;
+        return email != null && !email.isBlank();
     }
''',
            )
        ],
    )

    result = PullRequestAnalysisService().analyse_repository(pull_request, tmp_path)

    assert result.selection_mode == "targeted"
    assert result.total_tests_discovered == 2
    assert [test.test_name for test in result.recommended_tests] == [
        "loginRejectsBlankEmail"
    ]
    assert result.recommended_tests[0].framework == "junit"
    assert "AuthService.login" in result.recommended_tests[0].reasons[0]



def test_unsupported_cpp_change_still_selects_full_suite(tmp_path):
    make_repository(tmp_path)
    source = tmp_path / "native"
    source.mkdir()
    (source / "auth.cpp").write_text(
        "bool login() { return true; }\n",
        encoding="utf-8",
    )
    pull_request = GitHubPullRequest(
        owner="example",
        repo="mixed-demo",
        number=40,
        title="Change unsupported native code",
        url="https://github.com/example/mixed-demo/pull/40",
        base_sha="base",
        head_sha="head",
        changed_files=[
            GitHubChangedFile(
                path="native/auth.cpp",
                status="modified",
                additions=1,
                deletions=1,
                patch='''@@ -1 +1 @@
-bool login() { return false; }
+bool login() { return true; }
''',
            )
        ],
    )

    result = PullRequestAnalysisService().analyse_repository(
        pull_request, tmp_path
    )

    assert result.selection_mode == "conservative"
    assert result.tests_selected == result.total_tests_discovered == 1
