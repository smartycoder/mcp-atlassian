"""Unit tests for the Bitbucket FastMCP server implementation."""
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Create a mock BitbucketFetcher with predefined responses."""
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
    """Create a mock BitbucketConfig for MainAppContext."""
    return BitbucketConfig(
        url="https://bitbucket.example.com",
        personal_token="test-pat",
        ssl_verify=False,
    )


@pytest.fixture
def test_bitbucket_mcp_instance(mock_bitbucket_fetcher, mock_base_bitbucket_config):
    """Create a test FastMCP instance with Bitbucket tools registered."""

    @asynccontextmanager
    async def test_lifespan(app: FastMCP) -> AsyncGenerator[MainAppContext, None]:
        try:
            yield MainAppContext(full_bitbucket_config=mock_base_bitbucket_config)
        finally:
            pass

    from src.mcp_atlassian.servers.bitbucket import (
        create_pull_request,
        get_branches,
        get_commits,
        get_file_content,
        get_projects,
        get_pull_request,
        get_pull_requests,
        get_repos,
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

    return test_mcp


@pytest.fixture
async def bitbucket_client(test_bitbucket_mcp_instance, mock_bitbucket_fetcher):
    """Create a FastMCP client with mocked Bitbucket fetcher."""
    with patch(
        "src.mcp_atlassian.servers.bitbucket.get_bitbucket_fetcher",
        AsyncMock(return_value=mock_bitbucket_fetcher),
    ):
        async with Client(transport=FastMCPTransport(test_bitbucket_mcp_instance)) as client:
            yield client


def test_bitbucket_mcp(mock_bitbucket_fetcher, mock_base_bitbucket_config):
    """Verify the bitbucket_mcp instance exists without errors."""
    from src.mcp_atlassian.servers.bitbucket import bitbucket_mcp

    assert bitbucket_mcp is not None


@pytest.mark.anyio
async def test_get_projects(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_projects tool returns list of projects."""
    response = await bitbucket_client.call_tool("get_projects", {"limit": 10})
    assert isinstance(response, list)
    assert len(response) > 0
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["key"] == "PROJ"
    mock_bitbucket_fetcher.get_projects.assert_called_once_with(limit=10)


@pytest.mark.anyio
async def test_get_repos(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_repos tool returns list of repos."""
    response = await bitbucket_client.call_tool(
        "get_repos", {"project_key": "PROJ", "limit": 25}
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["slug"] == "my-repo"
    mock_bitbucket_fetcher.get_repos.assert_called_once_with(project_key="PROJ", limit=25)


@pytest.mark.anyio
async def test_get_pull_requests(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_pull_requests tool returns PRs filtered by state."""
    response = await bitbucket_client.call_tool(
        "get_pull_requests",
        {"project_key": "PROJ", "repo_slug": "my-repo", "state": "OPEN", "limit": 25},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["id"] == 1
    mock_bitbucket_fetcher.get_pull_requests.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", state="OPEN", limit=25
    )


@pytest.mark.anyio
async def test_get_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_pull_request tool returns a single PR."""
    response = await bitbucket_client.call_tool(
        "get_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["id"] == 1
    mock_bitbucket_fetcher.get_pull_request.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1
    )


@pytest.mark.anyio
async def test_get_commits(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_commits tool returns commit history."""
    response = await bitbucket_client.call_tool(
        "get_commits",
        {"project_key": "PROJ", "repo_slug": "my-repo", "branch": "main", "limit": 25},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["id"] == "abc123def456"
    mock_bitbucket_fetcher.get_commits.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", branch="main", limit=25
    )


@pytest.mark.anyio
async def test_get_branches(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_branches tool returns list of branches."""
    response = await bitbucket_client.call_tool(
        "get_branches",
        {"project_key": "PROJ", "repo_slug": "my-repo", "limit": 25},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["displayId"] == "main"
    mock_bitbucket_fetcher.get_branches.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", limit=25
    )


@pytest.mark.anyio
async def test_get_file_content(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_file_content tool returns raw file content."""
    response = await bitbucket_client.call_tool(
        "get_file_content",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "file_path": "README.md",
            "branch": "main",
        },
    )
    content = response[0].text
    assert "README" in content
    mock_bitbucket_fetcher.get_file_content.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", file_path="README.md", branch="main"
    )


@pytest.mark.anyio
async def test_create_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the create_pull_request tool creates a PR."""
    response = await bitbucket_client.call_tool(
        "create_pull_request",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "title": "New PR",
            "from_branch": "feature/x",
            "to_branch": "main",
            "description": "My description",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["id"] == 5
    mock_bitbucket_fetcher.create_pull_request.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        title="New PR",
        description="My description",
        from_branch="feature/x",
        to_branch="main",
        reviewers=[],
    )
