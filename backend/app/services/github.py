import io
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx


MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_FILES = 100_000


_PULL_REQUEST_PATH = re.compile(
    r"^/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/pull/(?P<number>[1-9][0-9]*)/?$"
)


class InvalidPullRequestUrl(ValueError):
    pass


class GitHubClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubChangedFile:
    path: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None
    previous_path: str | None = None


@dataclass(frozen=True)
class GitHubPullRequest:
    owner: str
    repo: str
    number: int
    title: str
    url: str
    base_sha: str
    head_sha: str
    changed_files: list[GitHubChangedFile]

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_github_pull_request_url(url: str) -> tuple[str, str, int]:
    if not isinstance(url, str):
        raise InvalidPullRequestUrl("Pull request URL must be text")

    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise InvalidPullRequestUrl(
            "Enter a GitHub pull request URL such as "
            "https://github.com/owner/repository/pull/123"
        )
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise InvalidPullRequestUrl("GitHub pull request URL contains unsupported components")

    match = _PULL_REQUEST_PATH.fullmatch(parsed.path)
    if not match:
        raise InvalidPullRequestUrl(
            "Enter a GitHub pull request URL such as "
            "https://github.com/owner/repository/pull/123"
        )

    return match["owner"], match["repo"], int(match["number"])


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        api_url: str = "https://api.github.com",
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TestPilot/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def fetch_pull_request(self, url: str) -> GitHubPullRequest:
        owner, repo, number = parse_github_pull_request_url(url)

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            details = await self._get_json(
                client, f"{self.api_url}/repos/{owner}/{repo}/pulls/{number}"
            )
            changed_files: list[GitHubChangedFile] = []
            page = 1
            while True:
                page_data = await self._get_json(
                    client,
                    f"{self.api_url}/repos/{owner}/{repo}/pulls/{number}/files",
                    params={"per_page": 100, "page": page},
                )
                if not isinstance(page_data, list):
                    raise GitHubClientError("GitHub returned an invalid changed-files response")
                for item in page_data:
                    changed_files.append(
                        GitHubChangedFile(
                            path=item["filename"],
                            status=item.get("status", "modified"),
                            additions=item.get("additions", 0),
                            deletions=item.get("deletions", 0),
                            patch=item.get("patch"),
                            previous_path=item.get("previous_filename"),
                        )
                    )
                if len(page_data) < 100:
                    break
                page += 1

        try:
            return GitHubPullRequest(
                owner=owner,
                repo=repo,
                number=number,
                title=details["title"],
                url=details["html_url"],
                base_sha=details["base"]["sha"],
                head_sha=details["head"]["sha"],
                changed_files=changed_files,
            )
        except (KeyError, TypeError) as error:
            raise GitHubClientError("GitHub returned incomplete pull request metadata") from error

    async def download_head_archive(
        self, pull_request: GitHubPullRequest, destination: Path
    ) -> Path:
        archive_url = (
            f"{self.api_url}/repos/{pull_request.owner}/{pull_request.repo}"
            f"/zipball/{pull_request.head_sha}"
        )
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=max(self.timeout, 60.0),
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            try:
                response = await client.get(archive_url)
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise GitHubClientError(self._http_error_message(error.response)) from error
            except httpx.HTTPError as error:
                raise GitHubClientError(f"Could not download repository archive: {error}") from error

        if len(response.content) > MAX_ARCHIVE_BYTES:
            raise GitHubClientError("Repository archive is too large to analyse safely")

        destination.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                self._safe_extract(archive, destination)
        except zipfile.BadZipFile as error:
            raise GitHubClientError("GitHub returned an invalid repository archive") from error

        roots = [path for path in destination.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise GitHubClientError("Repository archive did not contain one project root")
        return roots[0]

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, int] | None = None,
    ):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise GitHubClientError(self._http_error_message(error.response)) from error
        except (httpx.HTTPError, ValueError) as error:
            raise GitHubClientError(f"Could not read GitHub response: {error}") from error

    @staticmethod
    def _http_error_message(response: httpx.Response) -> str:
        if response.status_code == 404:
            return "Pull request or repository was not found, or it is private"
        if response.status_code == 403:
            return "GitHub rejected the request; check the API rate limit or token"
        return f"GitHub API request failed with status {response.status_code}"

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
        destination = destination.resolve()
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_FILES:
            raise GitHubClientError("Repository archive contains too many files")
        if sum(member.file_size for member in members) > MAX_EXTRACTED_BYTES:
            raise GitHubClientError("Extracted repository would be too large")

        for member in members:
            target = (destination / member.filename).resolve()
            if destination != target and destination not in target.parents:
                raise GitHubClientError("Repository archive contains an unsafe path")
            mode = member.external_attr >> 16
            if mode & 0o170000 == 0o120000:
                raise GitHubClientError("Repository archive contains an unsupported symlink")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
