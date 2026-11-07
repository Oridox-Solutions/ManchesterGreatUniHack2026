import asyncio
import io
import zipfile

import httpx
import pytest

from app.services.github import (
    GitHubClient,
    GitHubClientError,
    GitHubPullRequest,
    InvalidPullRequestUrl,
    parse_github_pull_request_url,
)


def test_parses_github_pull_request_url():
    assert parse_github_pull_request_url(
        "https://github.com/example/project/pull/42"
    ) == ("example", "project", 42)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/example/project/pull/42",
        "https://evil.example/example/project/pull/42",
        "https://github.com/example/project/issues/42",
        "https://github.com/example/project/pull/0",
        "https://github.com/example/project/pull/42?token=secret",
    ],
)
def test_rejects_invalid_or_unsafe_urls(url):
    with pytest.raises(InvalidPullRequestUrl):
        parse_github_pull_request_url(url)


def test_fetches_pull_request_and_changed_files():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/pulls/42"):
            return httpx.Response(
                200,
                json={
                    "title": "Fix task archive rules",
                    "html_url": "https://github.com/example/project/pull/42",
                    "base": {"sha": "base"},
                    "head": {"sha": "head"},
                },
            )
        if request.url.path.endswith("/pulls/42/files"):
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": "app/tasks.py",
                        "status": "modified",
                        "additions": 3,
                        "deletions": 1,
                        "patch": "@@ -1 +1 @@\n-old\n+new",
                    }
                ],
            )
        return httpx.Response(404)

    client = GitHubClient(
        token="test-token",
        api_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        client.fetch_pull_request(
            "https://github.com/example/project/pull/42"
        )
    )
    assert result.title == "Fix task archive rules"
    assert result.head_sha == "head"
    assert result.changed_files[0].path == "app/tasks.py"


def test_downloads_and_safely_extracts_archive(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("example-head/app.py", "VALUE = 1\n")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=buffer.getvalue())

    pull_request = GitHubPullRequest(
        owner="example",
        repo="project",
        number=42,
        title="Change",
        url="https://github.com/example/project/pull/42",
        base_sha="base",
        head_sha="head",
        changed_files=[],
    )
    client = GitHubClient(
        api_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
    )
    root = asyncio.run(client.download_head_archive(pull_request, tmp_path))
    assert root.name == "example-head"
    assert (root / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_rejects_archive_path_traversal(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.py", "unsafe")

    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        with pytest.raises(GitHubClientError, match="unsafe path"):
            GitHubClient._safe_extract(archive, tmp_path)
