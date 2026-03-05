# Bitbucket Server Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Bitbucket Server/DC v9.4+ as a third service in mcp-atlassian, with per-request Bearer token auth and 8 MCP tools covering projects, repos, PRs, commits, branches, and file content.

**Architecture:** Hybrid approach — `bitbucket/config.py` + `bitbucket/client.py` (single class, no mixin) + `servers/bitbucket.py`. Mirrors the Jira/Confluence pattern exactly: `BitbucketConfig` loaded at startup, `BitbucketFetcher` built per-request from Bearer token, mounted as `bitbucket_mcp` in `main.py`.

**Tech Stack:** `atlassian-python-api` (already a dependency, has `atlassian.Bitbucket` for Server), `fastmcp`, `pytest`, `pytest-asyncio`.

---

### Task 1: BitbucketConfig

**Files:**
- Create: `src/mcp_atlassian/bitbucket/__init__.py`
- Create: `src/mcp_atlassian/bitbucket/config.py`
- Create: `tests/unit/bitbucket/__init__.py`
- Create: `tests/unit/bitbucket/test_config.py`

**Step 1: Write the failing tests**

```python
# tests/unit/bitbucket/test_config.py
import os
import pytest
from src.mcp_atlassian.bitbucket.config import BitbucketConfig


def test_from_env_with_pat(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com")
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "my-pat")
    config = BitbucketConfig.from_env()
    assert config.url == "https://bitbucket.example.com"
    assert config.personal_token == "my-pat"
    assert config.ssl_verify is True


def test_from_env_ssl_verify_false(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com")
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "my-pat")
    monkeypatch.setenv("BITBUCKET_SSL_VERIFY", "false")
    config = BitbucketConfig.from_env()
    assert config.ssl_verify is False


def test_from_env_missing_url_raises(monkeypatch):
    monkeypatch.delenv("BITBUCKET_URL", raising=False)
    monkeypatch.delenv("BITBUCKET_PERSONAL_TOKEN", raising=False)
    with pytest.raises(ValueError, match="BITBUCKET_URL"):
        BitbucketConfig.from_env()


def test_is_auth_configured_with_pat():
    config = BitbucketConfig(
        url="https://bitbucket.example.com",
        personal_token="my-pat",
    )
    assert config.is_auth_configured() is True


def test_is_auth_configured_without_token():
    config = BitbucketConfig(url="https://bitbucket.example.com")
    assert config.is_auth_configured() is False
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/bitbucket/test_config.py -v
```
Expected: `ModuleNotFoundError` — `bitbucket` module doesn't exist yet.

**Step 3: Implement**

```python
# src/mcp_atlassian/bitbucket/__init__.py
"""Bitbucket Server/DC integration module."""
from .client import BitbucketFetcher
from .config import BitbucketConfig

__all__ = ["BitbucketConfig", "BitbucketFetcher"]
```

```python
# src/mcp_atlassian/bitbucket/config.py
"""Configuration for Bitbucket Server/DC API interactions."""
import logging
import os
from dataclasses import dataclass, field

from ..utils.env import is_env_ssl_verify

logger = logging.getLogger(__name__)


@dataclass
class BitbucketConfig:
    """Bitbucket Server/DC API configuration.

    Authentication: Personal Access Token (PAT) only.
    PAT can come from environment (global fallback) or per-request Bearer header.
    """

    url: str = ""
    personal_token: str | None = None
    ssl_verify: bool = True

    @classmethod
    def from_env(cls) -> "BitbucketConfig":
        """Create configuration from environment variables.

        Raises:
            ValueError: If BITBUCKET_URL is missing.
        """
        url = os.getenv("BITBUCKET_URL")
        if not url:
            raise ValueError("Missing required BITBUCKET_URL environment variable")

        personal_token = os.getenv("BITBUCKET_PERSONAL_TOKEN")
        ssl_verify = is_env_ssl_verify("BITBUCKET_SSL_VERIFY")

        return cls(url=url, personal_token=personal_token, ssl_verify=ssl_verify)

    def is_auth_configured(self) -> bool:
        """Check if authentication is configured."""
        return bool(self.personal_token)
```

**Step 4: Run tests**

```bash
pytest tests/unit/bitbucket/test_config.py -v
```
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add src/mcp_atlassian/bitbucket/ tests/unit/bitbucket/
git commit -m "feat(bitbucket): add BitbucketConfig with PAT auth and env loading"
```

---

### Task 2: BitbucketFetcher client

**Files:**
- Create: `src/mcp_atlassian/bitbucket/client.py`
- Create: `tests/unit/bitbucket/test_client.py`

**Step 1: Write the failing tests**

```python
# tests/unit/bitbucket/test_client.py
from unittest.mock import MagicMock, patch
import pytest
from src.mcp_atlassian.bitbucket.config import BitbucketConfig
from src.mcp_atlassian.bitbucket.client import BitbucketFetcher


@pytest.fixture
def config():
    return BitbucketConfig(
        url="https://bitbucket.example.com",
        personal_token="test-pat",
        ssl_verify=False,
    )


@pytest.fixture
def mock_bb_api():
    return MagicMock()


@pytest.fixture
def fetcher(config, mock_bb_api):
    with patch("src.mcp_atlassian.bitbucket.client.Bitbucket", return_value=mock_bb_api):
        f = BitbucketFetcher(config=config)
        f.bb = mock_bb_api
        return f


def test_get_projects_returns_list(fetcher, mock_bb_api):
    mock_bb_api.projects.return_value = [{"key": "PROJ", "name": "Project"}]
    result = fetcher.get_projects(limit=10)
    assert isinstance(result, list)
    assert result[0]["key"] == "PROJ"
    mock_bb_api.projects.assert_called_once_with(limit=10)


def test_get_repos_returns_list(fetcher, mock_bb_api):
    mock_bb_api.repos.return_value = [{"slug": "my-repo", "name": "My Repo"}]
    result = fetcher.get_repos("PROJ", limit=25)
    assert result[0]["slug"] == "my-repo"
    mock_bb_api.repos.assert_called_once_with("PROJ", limit=25)


def test_get_pull_requests(fetcher, mock_bb_api):
    mock_bb_api.get_pull_requests.return_value = [{"id": 1, "title": "Fix bug"}]
    result = fetcher.get_pull_requests("PROJ", "my-repo", state="OPEN", limit=25)
    assert result[0]["id"] == 1
    mock_bb_api.get_pull_requests.assert_called_once_with(
        "PROJ", "my-repo", state="OPEN", order="newest", limit=25
    )


def test_get_pull_request(fetcher, mock_bb_api):
    mock_bb_api.get_pull_request.return_value = {"id": 42, "title": "Feature"}
    result = fetcher.get_pull_request("PROJ", "my-repo", 42)
    assert result["id"] == 42
    mock_bb_api.get_pull_request.assert_called_once_with("PROJ", "my-repo", 42)


def test_create_pull_request(fetcher, mock_bb_api):
    mock_bb_api.open_pull_request.return_value = {"id": 5, "title": "New PR"}
    result = fetcher.create_pull_request(
        project_key="PROJ",
        repo_slug="my-repo",
        title="New PR",
        description="desc",
        from_branch="feature/x",
        to_branch="main",
        reviewers=[],
    )
    assert result["id"] == 5


def test_get_commits(fetcher, mock_bb_api):
    mock_bb_api.get_commits.return_value = [{"id": "abc123"}]
    result = fetcher.get_commits("PROJ", "my-repo", branch="main", limit=25)
    assert result[0]["id"] == "abc123"


def test_get_branches(fetcher, mock_bb_api):
    mock_bb_api.get_branches.return_value = [{"displayId": "main"}]
    result = fetcher.get_branches("PROJ", "my-repo", limit=25)
    assert result[0]["displayId"] == "main"


def test_get_file_content(fetcher, mock_bb_api):
    mock_bb_api.get_content_of_file.return_value = "file content here"
    result = fetcher.get_file_content("PROJ", "my-repo", "README.md", branch="main")
    assert result == "file content here"
    mock_bb_api.get_content_of_file.assert_called_once_with(
        "PROJ", "my-repo", "README.md", at="main"
    )
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/bitbucket/test_client.py -v
```
Expected: `ImportError` — `client.py` doesn't exist.

**Step 3: Implement**

```python
# src/mcp_atlassian/bitbucket/client.py
"""Bitbucket Server/DC client wrapping atlassian-python-api."""
import logging
from typing import Any

from atlassian import Bitbucket

from .config import BitbucketConfig

logger = logging.getLogger(__name__)


class BitbucketFetcher:
    """Fetcher for Bitbucket Server/DC operations.

    Wraps atlassian.Bitbucket with a clean interface for MCP tools.
    """

    def __init__(self, config: BitbucketConfig) -> None:
        self.config = config
        self.bb = Bitbucket(
            url=config.url,
            token=config.personal_token,
            verify_ssl=config.ssl_verify,
        )

    def get_projects(self, limit: int = 25) -> list[dict[str, Any]]:
        """List all accessible Bitbucket projects."""
        try:
            result = self.bb.projects(limit=limit)
            return list(result) if result else []
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            return []

    def get_repos(self, project_key: str, limit: int = 25) -> list[dict[str, Any]]:
        """List repositories in a project."""
        try:
            result = self.bb.repos(project_key, limit=limit)
            return list(result) if result else []
        except Exception as e:
            logger.error(f"Error getting repos for project {project_key}: {e}")
            return []

    def get_repo(self, project_key: str, repo_slug: str) -> dict[str, Any] | None:
        """Get a single repository."""
        try:
            return self.bb.repo(project_key, repo_slug)
        except Exception as e:
            logger.error(f"Error getting repo {project_key}/{repo_slug}: {e}")
            return None

    def get_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str = "OPEN",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """List pull requests. state: OPEN, MERGED, DECLINED, ALL."""
        try:
            result = self.bb.get_pull_requests(
                project_key, repo_slug, state=state, order="newest", limit=limit
            )
            return list(result) if result else []
        except Exception as e:
            logger.error(f"Error getting PRs for {project_key}/{repo_slug}: {e}")
            return []

    def get_pull_request(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict[str, Any] | None:
        """Get a single pull request by ID."""
        try:
            return self.bb.get_pull_request(project_key, repo_slug, pr_id)
        except Exception as e:
            logger.error(f"Error getting PR {pr_id} in {project_key}/{repo_slug}: {e}")
            return None

    def create_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        title: str,
        description: str,
        from_branch: str,
        to_branch: str,
        reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a pull request."""
        return self.bb.open_pull_request(
            source_project=project_key,
            source_repo=repo_slug,
            dest_project=project_key,
            dest_repo=repo_slug,
            title=title,
            description=description,
            from_branch=from_branch,
            to_branch=to_branch,
            reviewers=reviewers or [],
        )

    def get_commits(
        self,
        project_key: str,
        repo_slug: str,
        branch: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Get commit history for a repository/branch."""
        try:
            result = self.bb.get_commits(
                project=project_key,
                repository=repo_slug,
                hash_newest=branch,
                limit=limit,
            )
            return list(result) if result else []
        except Exception as e:
            logger.error(f"Error getting commits for {project_key}/{repo_slug}: {e}")
            return []

    def get_branches(
        self, project_key: str, repo_slug: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        """List branches in a repository."""
        try:
            result = self.bb.get_branches(project_key, repo_slug, limit=limit)
            return list(result) if result else []
        except Exception as e:
            logger.error(f"Error getting branches for {project_key}/{repo_slug}: {e}")
            return []

    def get_file_content(
        self,
        project_key: str,
        repo_slug: str,
        file_path: str,
        branch: str | None = None,
    ) -> str:
        """Get the content of a file at a given path and branch."""
        try:
            return self.bb.get_content_of_file(
                project_key, repo_slug, file_path, at=branch
            )
        except Exception as e:
            logger.error(f"Error getting file {file_path} in {project_key}/{repo_slug}: {e}")
            return ""
```

**Step 4: Run tests**

```bash
pytest tests/unit/bitbucket/test_client.py -v
```
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add src/mcp_atlassian/bitbucket/client.py tests/unit/bitbucket/test_client.py
git commit -m "feat(bitbucket): add BitbucketFetcher client wrapping atlassian.Bitbucket"
```

---

### Task 3: Context and dependency injection

**Files:**
- Modify: `src/mcp_atlassian/servers/context.py`
- Modify: `src/mcp_atlassian/servers/dependencies.py`
- Modify: `tests/unit/servers/test_dependencies.py`

**Step 1: Update context.py**

Add `BitbucketConfig` to `MainAppContext`. Open `src/mcp_atlassian/servers/context.py` and add:

```python
# Add to TYPE_CHECKING block:
from mcp_atlassian.bitbucket.config import BitbucketConfig

# Add field to MainAppContext:
full_bitbucket_config: BitbucketConfig | None = None
```

Full updated file:

```python
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_atlassian.bitbucket.config import BitbucketConfig
    from mcp_atlassian.confluence.config import ConfluenceConfig
    from mcp_atlassian.jira.config import JiraConfig


@dataclass
class UserAuthContext:
    """Per-request user authentication context for multi-user PAT/OAuth support."""

    auth_type: str | None = None  # 'pat' or 'oauth'
    token: str | None = None
    email: str | None = None
    cloud_id: str | None = None


# ContextVar to store per-request user authentication
user_auth_context: ContextVar[UserAuthContext | None] = ContextVar(
    "user_auth_context", default=None
)


@dataclass(frozen=True)
class MainAppContext:
    """
    Context holding fully configured Jira, Confluence, and Bitbucket configurations
    loaded from environment variables at server startup.
    These configurations include any global/default authentication details.
    """

    full_jira_config: JiraConfig | None = None
    full_confluence_config: ConfluenceConfig | None = None
    full_bitbucket_config: BitbucketConfig | None = None
    read_only: bool = False
    enabled_tools: list[str] | None = None
```

**Step 2: Write the failing test for get_bitbucket_fetcher**

Add to `tests/unit/servers/test_dependencies.py` (check existing tests first to match patterns):

```python
@pytest.mark.anyio
async def test_get_bitbucket_fetcher_uses_user_token(mock_ctx):
    """get_bitbucket_fetcher builds fetcher from Bearer token in context."""
    from src.mcp_atlassian.bitbucket.config import BitbucketConfig
    from src.mcp_atlassian.servers.dependencies import get_bitbucket_fetcher
    from src.mcp_atlassian.servers.context import UserAuthContext, user_auth_context

    base_config = BitbucketConfig(
        url="https://bitbucket.example.com",
        personal_token="global-pat",
        ssl_verify=False,
    )
    mock_ctx.request_context.lifespan_context = {
        "app_lifespan_context": MainAppContext(full_bitbucket_config=base_config)
    }
    user_auth_context.set(UserAuthContext(auth_type="pat", token="user-pat"))

    with patch("src.mcp_atlassian.servers.dependencies.BitbucketFetcher") as MockFetcher:
        MockFetcher.return_value = MagicMock()
        fetcher = await get_bitbucket_fetcher(mock_ctx)
        assert fetcher is not None
        call_config = MockFetcher.call_args[1]["config"]
        assert call_config.personal_token == "user-pat"
```

**Step 3: Run to verify failure**

```bash
pytest tests/unit/servers/test_dependencies.py -k "bitbucket" -v
```
Expected: `ImportError` — `get_bitbucket_fetcher` doesn't exist.

**Step 4: Implement get_bitbucket_fetcher in dependencies.py**

Add to the bottom of `src/mcp_atlassian/servers/dependencies.py`:

```python
from mcp_atlassian.bitbucket import BitbucketConfig, BitbucketFetcher


async def get_bitbucket_fetcher(ctx: Context) -> BitbucketFetcher:
    """Returns a BitbucketFetcher for the current request context.

    Uses Bearer token from request header if present; falls back to global PAT.

    Raises:
        ValueError: If configuration is missing or token is invalid.
    """
    logger.debug(f"get_bitbucket_fetcher: ENTERED. Context ID: {id(ctx)}")

    lifespan_ctx_dict = ctx.request_context.lifespan_context  # type: ignore
    app_lifespan_ctx: MainAppContext | None = (
        lifespan_ctx_dict.get("app_lifespan_context")
        if isinstance(lifespan_ctx_dict, dict)
        else None
    )
    if not app_lifespan_ctx or not app_lifespan_ctx.full_bitbucket_config:
        raise ValueError(
            "Bitbucket global configuration (URL, SSL) is not available from lifespan context."
        )

    base_config = app_lifespan_ctx.full_bitbucket_config

    # Check contextvar for user-provided Bearer token
    user_auth_ctx = user_auth_context.get()
    if user_auth_ctx and user_auth_ctx.token and user_auth_ctx.auth_type == "pat":
        logger.info(
            f"Creating user-specific BitbucketFetcher with token ...{str(user_auth_ctx.token)[-8:]}"
        )
        import dataclasses
        user_config = dataclasses.replace(base_config, personal_token=user_auth_ctx.token)
        return BitbucketFetcher(config=user_config)

    # Fallback to global PAT
    logger.debug("get_bitbucket_fetcher: Using global BitbucketFetcher from lifespan_context.")
    return BitbucketFetcher(config=base_config)
```

**Step 5: Run tests**

```bash
pytest tests/unit/servers/test_dependencies.py -v
```
Expected: All tests PASS (including existing ones).

**Step 6: Commit**

```bash
git add src/mcp_atlassian/servers/context.py src/mcp_atlassian/servers/dependencies.py tests/unit/servers/test_dependencies.py
git commit -m "feat(bitbucket): add BitbucketConfig to context and get_bitbucket_fetcher dependency"
```

---

### Task 4: FastMCP server with tools

**Files:**
- Create: `src/mcp_atlassian/servers/bitbucket.py`
- Create: `tests/unit/servers/test_bitbucket_server.py`
- Create: `tests/fixtures/bitbucket_mocks.py`

**Step 1: Create test fixtures**

```python
# tests/fixtures/bitbucket_mocks.py
"""Mock data for Bitbucket unit tests."""

MOCK_BB_PROJECTS = [
    {"key": "PROJ", "name": "My Project", "description": "Test project", "type": "NORMAL"},
]

MOCK_BB_REPOS = [
    {"slug": "my-repo", "name": "My Repo", "project": {"key": "PROJ"}},
]

MOCK_BB_PULL_REQUESTS = [
    {
        "id": 1,
        "title": "Fix bug in login",
        "state": "OPEN",
        "fromRef": {"displayId": "feature/fix-login"},
        "toRef": {"displayId": "main"},
        "author": {"user": {"displayName": "John Doe"}},
    }
]

MOCK_BB_COMMITS = [
    {"id": "abc123def456", "message": "Fix login bug", "author": {"name": "John Doe"}},
]

MOCK_BB_BRANCHES = [
    {"displayId": "main", "isDefault": True},
    {"displayId": "feature/fix-login", "isDefault": False},
]
```

**Step 2: Write failing tests**

```python
# tests/unit/servers/test_bitbucket_server.py
"""Unit tests for the Bitbucket FastMCP server."""
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.client import FastMCPTransport

from src.mcp_atlassian.bitbucket.client import BitbucketFetcher
from src.mcp_atlassian.bitbucket.config import BitbucketConfig
from src.mcp_atlassian.servers.context import MainAppContext
from src.mcp_atlassian.servers.main import AtlassianMCP
from tests.fixtures.bitbucket_mocks import (
    MOCK_BB_BRANCHES,
    MOCK_BB_COMMITS,
    MOCK_BB_PROJECTS,
    MOCK_BB_PULL_REQUESTS,
    MOCK_BB_REPOS,
)


@pytest.fixture
def mock_bitbucket_fetcher():
    mock = MagicMock(spec=BitbucketFetcher)
    mock.config = MagicMock()
    mock.config.url = "https://bitbucket.example.com"
    mock.get_projects.return_value = MOCK_BB_PROJECTS
    mock.get_repos.return_value = MOCK_BB_REPOS
    mock.get_pull_requests.return_value = MOCK_BB_PULL_REQUESTS
    mock.get_pull_request.return_value = MOCK_BB_PULL_REQUESTS[0]
    mock.get_commits.return_value = MOCK_BB_COMMITS
    mock.get_branches.return_value = MOCK_BB_BRANCHES
    mock.get_file_content.return_value = "# README\nHello world"
    mock.create_pull_request.return_value = {"id": 5, "title": "New PR", "state": "OPEN"}
    return mock


@pytest.fixture
def mock_base_bitbucket_config():
    return BitbucketConfig(
        url="https://bitbucket.example.com",
        personal_token="test-pat",
        ssl_verify=False,
    )


@pytest.fixture
def bitbucket_client(mock_bitbucket_fetcher, mock_base_bitbucket_config):
    @asynccontextmanager
    async def test_lifespan(app: FastMCP) -> AsyncGenerator[MainAppContext, None]:
        try:
            yield MainAppContext(full_bitbucket_config=mock_base_bitbucket_config)
        finally:
            pass

    from src.mcp_atlassian.servers.bitbucket import (
        get_projects,
        get_repos,
        get_pull_requests,
        get_pull_request,
        create_pull_request,
        get_commits,
        get_branches,
        get_file_content,
    )

    test_mcp = AtlassianMCP("TestBitbucket", lifespan=test_lifespan)
    test_mcp.tool()(get_projects)
    test_mcp.tool()(get_repos)
    test_mcp.tool()(get_pull_requests)
    test_mcp.tool()(get_pull_request)
    test_mcp.tool()(create_pull_request)
    test_mcp.tool()(get_commits)
    test_mcp.tool()(get_branches)
    test_mcp.tool()(get_file_content)

    with patch(
        "src.mcp_atlassian.servers.bitbucket.get_bitbucket_fetcher",
        return_value=mock_bitbucket_fetcher,
    ):
        transport = FastMCPTransport(test_mcp)
        yield Client(transport)


@pytest.mark.anyio
async def test_get_projects(bitbucket_client, mock_bitbucket_fetcher):
    response = await bitbucket_client.call_tool("get_projects", {"limit": 10})
    assert len(response) > 0
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["key"] == "PROJ"
    mock_bitbucket_fetcher.get_projects.assert_called_once_with(limit=10)


@pytest.mark.anyio
async def test_get_repos(bitbucket_client, mock_bitbucket_fetcher):
    response = await bitbucket_client.call_tool("get_repos", {"project_key": "PROJ"})
    content = json.loads(response[0].text)
    assert content[0]["slug"] == "my-repo"


@pytest.mark.anyio
async def test_get_pull_requests(bitbucket_client, mock_bitbucket_fetcher):
    response = await bitbucket_client.call_tool(
        "get_pull_requests", {"project_key": "PROJ", "repo_slug": "my-repo"}
    )
    content = json.loads(response[0].text)
    assert content[0]["id"] == 1
    mock_bitbucket_fetcher.get_pull_requests.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", state="OPEN", limit=25
    )


@pytest.mark.anyio
async def test_get_commits(bitbucket_client, mock_bitbucket_fetcher):
    response = await bitbucket_client.call_tool(
        "get_commits", {"project_key": "PROJ", "repo_slug": "my-repo", "branch": "main"}
    )
    content = json.loads(response[0].text)
    assert content[0]["id"] == "abc123def456"


@pytest.mark.anyio
async def test_get_branches(bitbucket_client, mock_bitbucket_fetcher):
    response = await bitbucket_client.call_tool(
        "get_branches", {"project_key": "PROJ", "repo_slug": "my-repo"}
    )
    content = json.loads(response[0].text)
    assert len(content) == 2
    assert content[0]["displayId"] == "main"


@pytest.mark.anyio
async def test_get_file_content(bitbucket_client, mock_bitbucket_fetcher):
    response = await bitbucket_client.call_tool(
        "get_file_content",
        {"project_key": "PROJ", "repo_slug": "my-repo", "file_path": "README.md"},
    )
    content = json.loads(response[0].text)
    assert "README" in content
```

**Step 3: Run to verify failure**

```bash
pytest tests/unit/servers/test_bitbucket_server.py -v
```
Expected: `ImportError` — `servers/bitbucket.py` doesn't exist.

**Step 4: Implement servers/bitbucket.py**

```python
# src/mcp_atlassian/servers/bitbucket.py
"""Bitbucket FastMCP server instance and tool definitions."""
import json
import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from mcp_atlassian.servers.dependencies import get_bitbucket_fetcher

logger = logging.getLogger(__name__)

bitbucket_mcp = FastMCP(
    name="Bitbucket MCP Service",
    description="Provides tools for interacting with Bitbucket Server/DC.",
)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_projects(
    ctx: Context,
    limit: Annotated[int, Field(description="Maximum number of projects to return (1-100)", default=25, ge=1, le=100)] = 25,
) -> str:
    """List all accessible Bitbucket projects.

    Returns a JSON list of project objects with key, name, and description.
    """
    bb = await get_bitbucket_fetcher(ctx)
    projects = bb.get_projects(limit=limit)
    return json.dumps(projects, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_repos(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    limit: Annotated[int, Field(description="Maximum number of repos to return (1-100)", default=25, ge=1, le=100)] = 25,
) -> str:
    """List repositories in a Bitbucket project.

    Returns a JSON list of repository objects with slug, name, and clone URLs.
    """
    bb = await get_bitbucket_fetcher(ctx)
    repos = bb.get_repos(project_key=project_key, limit=limit)
    return json.dumps(repos, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pull_requests(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    state: Annotated[str, Field(description="PR state filter: OPEN, MERGED, DECLINED, or ALL", default="OPEN")] = "OPEN",
    limit: Annotated[int, Field(description="Maximum number of PRs to return (1-100)", default=25, ge=1, le=100)] = 25,
) -> str:
    """List pull requests in a repository.

    Returns PRs ordered newest first. Use state='ALL' to see all PRs regardless of status.
    """
    bb = await get_bitbucket_fetcher(ctx)
    prs = bb.get_pull_requests(project_key=project_key, repo_slug=repo_slug, state=state, limit=limit)
    return json.dumps(prs, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
) -> str:
    """Get details of a single pull request including description, reviewers, and diff stats."""
    bb = await get_bitbucket_fetcher(ctx)
    pr = bb.get_pull_request(project_key=project_key, repo_slug=repo_slug, pr_id=pr_id)
    if pr is None:
        return json.dumps({"error": f"Pull request {pr_id} not found"})
    return json.dumps(pr, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
async def create_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    title: Annotated[str, Field(description="Title of the pull request")],
    from_branch: Annotated[str, Field(description="Source branch name (e.g. 'feature/my-feature')")],
    to_branch: Annotated[str, Field(description="Target branch name (e.g. 'main')")],
    description: Annotated[str, Field(description="Description of the pull request", default="")] = "",
    reviewers: Annotated[list[str], Field(description="List of reviewer usernames", default_factory=list)] = [],
) -> str:
    """Create a new pull request in a repository."""
    bb = await get_bitbucket_fetcher(ctx)
    pr = bb.create_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        title=title,
        description=description,
        from_branch=from_branch,
        to_branch=to_branch,
        reviewers=reviewers,
    )
    return json.dumps(pr, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_commits(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    branch: Annotated[str | None, Field(description="Branch name to get commits from. Defaults to default branch.", default=None)] = None,
    limit: Annotated[int, Field(description="Maximum number of commits to return (1-100)", default=25, ge=1, le=100)] = 25,
) -> str:
    """Get commit history for a repository, optionally filtered to a branch."""
    bb = await get_bitbucket_fetcher(ctx)
    commits = bb.get_commits(project_key=project_key, repo_slug=repo_slug, branch=branch, limit=limit)
    return json.dumps(commits, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_branches(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    limit: Annotated[int, Field(description="Maximum number of branches to return (1-100)", default=25, ge=1, le=100)] = 25,
) -> str:
    """List branches in a repository. The default branch is marked with isDefault=true."""
    bb = await get_bitbucket_fetcher(ctx)
    branches = bb.get_branches(project_key=project_key, repo_slug=repo_slug, limit=limit)
    return json.dumps(branches, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_file_content(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    file_path: Annotated[str, Field(description="Path to the file (e.g. 'src/main.py' or 'README.md')")],
    branch: Annotated[str | None, Field(description="Branch or commit hash to read from. Defaults to default branch.", default=None)] = None,
) -> str:
    """Get the content of a file from a repository at a specific branch or commit."""
    bb = await get_bitbucket_fetcher(ctx)
    content = bb.get_file_content(
        project_key=project_key, repo_slug=repo_slug, file_path=file_path, branch=branch
    )
    return json.dumps(content, indent=2, ensure_ascii=False)
```

**Step 5: Run tests**

```bash
pytest tests/unit/servers/test_bitbucket_server.py -v
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/mcp_atlassian/servers/bitbucket.py tests/unit/servers/test_bitbucket_server.py tests/fixtures/bitbucket_mocks.py
git commit -m "feat(bitbucket): add FastMCP server with 8 Bitbucket tools"
```

---

### Task 5: Wire into main.py

**Files:**
- Modify: `src/mcp_atlassian/servers/main.py`
- Modify: `tests/unit/servers/test_main_server.py`

**Step 1: Write failing test**

Open `tests/unit/servers/test_main_server.py` and add a test that checks Bitbucket tools appear when configured:

```python
def test_bitbucket_tools_excluded_when_not_configured(mock_ctx_with_no_bitbucket):
    """Bitbucket tools should not appear when BITBUCKET_URL is not set."""
    # Verify that "bitbucket_get_projects" is not in tool list
    # (test pattern depends on existing test_main_server.py structure — match it)
    pass  # expand after reading existing tests
```

First read `tests/unit/servers/test_main_server.py` to understand the pattern, then write a matching test.

**Step 2: Run to verify current state**

```bash
pytest tests/unit/servers/test_main_server.py -v
```
Note: All existing tests should still pass before making changes.

**Step 3: Update main.py**

In `src/mcp_atlassian/servers/main.py`, make these changes:

**a) Add imports:**
```python
from mcp_atlassian.bitbucket import BitbucketFetcher
from mcp_atlassian.bitbucket.config import BitbucketConfig
from .bitbucket import bitbucket_mcp
```

**b) In `main_lifespan`, add after the Confluence block:**
```python
    loaded_bitbucket_config: BitbucketConfig | None = None

    if services.get("bitbucket"):
        try:
            bitbucket_config = BitbucketConfig.from_env()
            if bitbucket_config.is_auth_configured():
                loaded_bitbucket_config = bitbucket_config
                logger.info(
                    "Bitbucket configuration loaded and authentication is configured."
                )
            else:
                logger.warning(
                    "Bitbucket URL found, but authentication is not fully configured. Bitbucket tools will be unavailable."
                )
        except Exception as e:
            logger.error(f"Failed to load Bitbucket configuration: {e}", exc_info=True)
```

**c) Add `full_bitbucket_config` to `MainAppContext` construction:**
```python
    app_context = MainAppContext(
        full_jira_config=loaded_jira_config,
        full_confluence_config=loaded_confluence_config,
        full_bitbucket_config=loaded_bitbucket_config,
        read_only=read_only,
        enabled_tools=enabled_tools,
    )
```

**d) In `_mcp_list_tools`, add Bitbucket filtering after the Confluence check:**
```python
            is_bitbucket_tool = "bitbucket" in tool_tags
            # ... in the service_configured_and_available block:
            if is_bitbucket_tool and not app_lifespan_state.full_bitbucket_config:
                logger.debug(
                    f"Excluding Bitbucket tool '{registered_name}' as Bitbucket configuration/authentication is incomplete."
                )
                service_configured_and_available = False
```

**e) Mount bitbucket_mcp (add at the bottom):**
```python
main_mcp.mount("bitbucket", bitbucket_mcp)
```

**f) Update `get_available_services` — open `src/mcp_atlassian/utils/environment.py` and add `"bitbucket"` detection:**
```python
# Find the existing function and add:
"bitbucket": bool(os.getenv("BITBUCKET_URL")),
```

**Step 4: Run all tests**

```bash
pytest tests/unit/servers/ -v
```
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/mcp_atlassian/servers/main.py src/mcp_atlassian/utils/environment.py tests/unit/servers/test_main_server.py
git commit -m "feat(bitbucket): wire Bitbucket service into main MCP server"
```

---

### Task 6: Docker Compose for integration testing

**Files:**
- Create: `docker-compose.bitbucket.yml` (if not exists, it does already from the session — verify content)

**Step 1: Verify or create docker-compose.bitbucket.yml**

```yaml
version: "3.3"

services:
  mcp-atlassian:
    build: .
    container_name: mcp-atlassian
    ports:
      - "9000:9000"
    environment:
      BITBUCKET_URL: "${BITBUCKET_URL}"
      BITBUCKET_SSL_VERIFY: "false"
      BITBUCKET_PERSONAL_TOKEN: "${BITBUCKET_PERSONAL_TOKEN}"
      MCP_LOGGING_STDOUT: "true"
      MCP_VERBOSE: "true"
    command: ["--transport", "streamable-http", "--port", "9000", "-vv"]
```

**Step 2: Run all unit tests to confirm nothing is broken**

```bash
pytest tests/unit/ -v --tb=short
```
Expected: All tests PASS.

**Step 3: Commit**

```bash
git add docker-compose.bitbucket.yml
git commit -m "feat(bitbucket): add docker-compose for Bitbucket integration testing"
```

---

### Task 7: Final verification

**Step 1: Run full test suite**

```bash
pytest tests/unit/ -v --tb=short
```
Expected: All tests PASS.

**Step 2: Verify tool list includes Bitbucket tools**

Build and start with Bitbucket env vars set, then call `tools/list` and confirm these appear:
- `bitbucket_get_projects`
- `bitbucket_get_repos`
- `bitbucket_get_pull_requests`
- `bitbucket_get_pull_request`
- `bitbucket_create_pull_request`
- `bitbucket_get_commits`
- `bitbucket_get_branches`
- `bitbucket_get_file_content`

**Step 3: Verify Bitbucket tools absent without BITBUCKET_URL**

Start without `BITBUCKET_URL` env var. Call `tools/list`. Bitbucket tools must not appear.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(bitbucket): complete Bitbucket Server/DC support"
```
