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
    MOCK_BB_COMMIT,
    MOCK_BB_COMMITS,
    MOCK_BB_DIFF,
    MOCK_BB_FILE_LIST,
    MOCK_BB_PR_CHANGES,
    MOCK_BB_PR_COMMENT,
    MOCK_BB_PR_COMMENTS,
    MOCK_BB_PR_DIFF,
    MOCK_BB_PR_TASKS,
    MOCK_BB_PROJECTS,
    MOCK_BB_PULL_REQUESTS,
    MOCK_BB_REPO,
    MOCK_BB_REPOS,
    MOCK_BB_SEARCH_RESULTS,
    MOCK_BB_TAGS,
)


@pytest.fixture
def mock_bitbucket_fetcher():
    """Create a mock BitbucketFetcher with predefined responses."""
    mock = MagicMock(spec=BitbucketFetcher)
    mock.config = MagicMock()
    mock.config.url = "https://bitbucket.example.com"
    mock.get_projects.return_value = MOCK_BB_PROJECTS
    mock.get_repo.return_value = MOCK_BB_REPO
    mock.get_repos.return_value = MOCK_BB_REPOS
    mock.get_pull_requests.return_value = MOCK_BB_PULL_REQUESTS
    mock.get_pull_request.return_value = MOCK_BB_PULL_REQUESTS[0]
    mock.get_commits.return_value = MOCK_BB_COMMITS
    mock.get_branches.return_value = MOCK_BB_BRANCHES
    mock.get_file_content.return_value = "# README\nHello world"
    mock.create_pull_request.return_value = {"id": 5, "title": "New PR", "state": "OPEN"}
    mock.get_pr_comments.return_value = MOCK_BB_PR_COMMENTS
    mock.update_pr_comment.return_value = {"id": 10, "text": "Updated comment", "version": 1}
    mock.add_pr_comment.return_value = MOCK_BB_PR_COMMENT
    mock.merge_pull_request.return_value = {"id": 1, "state": "MERGED"}
    mock.decline_pull_request.return_value = {"id": 1, "state": "DECLINED"}
    mock.approve_pull_request.return_value = {"status": "APPROVED"}
    mock.reopen_pull_request.return_value = {"id": 1, "state": "OPEN"}
    mock.unapprove_pull_request.return_value = {"status": "UNAPPROVED"}
    mock.add_pr_reviewer.return_value = {"id": 1, "reviewers": [{"user": {"name": "jdoe"}}]}
    mock.get_pr_changes.return_value = MOCK_BB_PR_CHANGES
    mock.get_pr_diff.return_value = MOCK_BB_PR_DIFF
    mock.get_diff.return_value = MOCK_BB_DIFF
    mock.get_file_list.return_value = MOCK_BB_FILE_LIST
    mock.get_commit.return_value = MOCK_BB_COMMIT
    mock.search_code.return_value = MOCK_BB_SEARCH_RESULTS
    mock.create_branch.return_value = {"displayId": "feature/new", "type": "BRANCH"}
    mock.delete_branch.return_value = None
    mock.get_tags.return_value = MOCK_BB_TAGS
    mock.create_tag.return_value = {"displayId": "v2.0.0", "latestCommit": "def456"}
    mock.delete_tag.return_value = None
    mock.update_file.return_value = {"id": "new_commit_hash"}
    mock.delete_pr_comment.return_value = None
    mock.delete_pull_request.return_value = None
    mock.update_pull_request.return_value = {"id": 1, "title": "Updated title", "description": "Updated desc", "state": "OPEN"}
    mock.get_pr_tasks.return_value = MOCK_BB_PR_TASKS
    mock.add_pr_task.return_value = {"id": 3, "text": "New task", "state": "OPEN"}
    mock.update_pr_task.return_value = {"id": 1, "text": "Fix failing tests", "state": "RESOLVED"}
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
        add_pr_comment,
        add_pr_reviewer,
        add_pr_task,
        approve_pull_request,
        create_branch,
        create_pull_request,
        create_tag,
        decline_pull_request,
        delete_branch,
        delete_pr_comment,
        delete_pull_request,
        delete_tag,
        get_branches,
        get_commit,
        get_commits,
        get_diff,
        get_file_content,
        get_file_list,
        get_pr_changes,
        get_pr_comments,
        get_pr_diff,
        get_pr_tasks,
        get_projects,
        get_pull_request,
        get_pull_requests,
        get_repo,
        get_repos,
        get_tags,
        merge_pull_request,
        reopen_pull_request,
        search_code,
        unapprove_pull_request,
        update_file,
        update_pr_comment,
        update_pr_task,
        update_pull_request,
    )

    test_mcp = AtlassianMCP("TestBitbucket", lifespan=test_lifespan)
    test_mcp.tool()(get_projects)
    test_mcp.tool()(get_repo)
    test_mcp.tool()(get_repos)
    test_mcp.tool()(get_pull_requests)
    test_mcp.tool()(get_pull_request)
    test_mcp.tool()(create_pull_request)
    test_mcp.tool()(get_commits)
    test_mcp.tool()(get_commit)
    test_mcp.tool()(get_branches)
    test_mcp.tool()(get_file_content)
    test_mcp.tool()(get_pr_comments)
    test_mcp.tool()(add_pr_comment)
    test_mcp.tool()(update_pr_comment)
    test_mcp.tool()(merge_pull_request)
    test_mcp.tool()(decline_pull_request)
    test_mcp.tool()(reopen_pull_request)
    test_mcp.tool()(approve_pull_request)
    test_mcp.tool()(unapprove_pull_request)
    test_mcp.tool()(add_pr_reviewer)
    test_mcp.tool()(delete_pr_comment)
    test_mcp.tool()(delete_pull_request)
    test_mcp.tool()(update_pull_request)
    test_mcp.tool()(get_pr_changes)
    test_mcp.tool()(get_pr_diff)
    test_mcp.tool()(get_diff)
    test_mcp.tool()(get_file_list)
    test_mcp.tool()(search_code)
    test_mcp.tool()(create_branch)
    test_mcp.tool()(delete_branch)
    test_mcp.tool()(get_tags)
    test_mcp.tool()(create_tag)
    test_mcp.tool()(delete_tag)
    test_mcp.tool()(update_file)
    test_mcp.tool()(get_pr_tasks)
    test_mcp.tool()(add_pr_task)
    test_mcp.tool()(update_pr_task)

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


@pytest.mark.anyio
async def test_add_pr_comment(bitbucket_client, mock_bitbucket_fetcher):
    """Test the add_pr_comment tool posts a comment on a PR."""
    response = await bitbucket_client.call_tool(
        "add_pr_comment",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "text": "LGTM"},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["id"] == 10
    assert content["text"] == "LGTM"
    mock_bitbucket_fetcher.add_pr_comment.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        pr_id=1,
        text="LGTM",
        parent_id=None,
    )


@pytest.mark.anyio
async def test_merge_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the merge_pull_request tool merges a PR."""
    response = await bitbucket_client.call_tool(
        "merge_pull_request",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "pr_id": 1,
            "merge_message": "Merge feature/x into main",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["state"] == "MERGED"
    mock_bitbucket_fetcher.merge_pull_request.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        pr_id=1,
        merge_message="Merge feature/x into main",
        close_source_branch=False,
        merge_strategy="merge_commit",
        pr_version=None,
    )


@pytest.mark.anyio
async def test_decline_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the decline_pull_request tool declines a PR."""
    response = await bitbucket_client.call_tool(
        "decline_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["state"] == "DECLINED"
    mock_bitbucket_fetcher.decline_pull_request.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        pr_id=1,
        pr_version=0,
    )


@pytest.mark.anyio
async def test_approve_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the approve_pull_request tool approves a PR."""
    response = await bitbucket_client.call_tool(
        "approve_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "user_slug": "jdoe"},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["status"] == "APPROVED"
    mock_bitbucket_fetcher.approve_pull_request.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        pr_id=1,
        user_slug="jdoe",
    )


@pytest.mark.anyio
async def test_get_pr_changes(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_pr_changes tool returns changed files for a PR."""
    response = await bitbucket_client.call_tool(
        "get_pr_changes",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["type"] == "MODIFY"
    mock_bitbucket_fetcher.get_pr_changes.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1
    )


@pytest.mark.anyio
async def test_get_diff(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_diff tool returns diff segments for a file between commits."""
    response = await bitbucket_client.call_tool(
        "get_diff",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "path": "src/main.py",
            "hash_oldest": "abc123",
            "hash_newest": "def456",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 1
    assert "hunks" in content[0]
    mock_bitbucket_fetcher.get_diff.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        path="src/main.py",
        hash_oldest="abc123",
        hash_newest="def456",
    )


@pytest.mark.anyio
async def test_get_file_list(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_file_list tool returns file paths in a repository."""
    response = await bitbucket_client.call_tool(
        "get_file_list",
        {"project_key": "PROJ", "repo_slug": "my-repo"},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert "src/main.py" in content
    mock_bitbucket_fetcher.get_file_list.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        sub_folder=None,
        ref=None,
    )


@pytest.mark.anyio
async def test_create_branch(bitbucket_client, mock_bitbucket_fetcher):
    """Test the create_branch tool creates a new branch."""
    response = await bitbucket_client.call_tool(
        "create_branch",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "name": "feature/new",
            "start_point": "main",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["displayId"] == "feature/new"
    mock_bitbucket_fetcher.create_branch.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        name="feature/new",
        start_point="main",
    )


@pytest.mark.anyio
async def test_delete_branch(bitbucket_client, mock_bitbucket_fetcher):
    """Test the delete_branch tool deletes a branch and returns success message."""
    response = await bitbucket_client.call_tool(
        "delete_branch",
        {"project_key": "PROJ", "repo_slug": "my-repo", "name": "feature/old"},
    )
    content = json.loads(response[0].text)
    assert content["success"] is True
    assert "feature/old" in content["message"]
    mock_bitbucket_fetcher.delete_branch.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", name="feature/old"
    )


@pytest.mark.anyio
async def test_get_tags(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_tags tool returns repository tags."""
    response = await bitbucket_client.call_tool(
        "get_tags",
        {"project_key": "PROJ", "repo_slug": "my-repo", "limit": 25},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["displayId"] == "v1.0.0"
    mock_bitbucket_fetcher.get_tags.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", limit=25
    )


@pytest.mark.anyio
async def test_create_tag(bitbucket_client, mock_bitbucket_fetcher):
    """Test the create_tag tool creates an annotated tag."""
    response = await bitbucket_client.call_tool(
        "create_tag",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "tag_name": "v2.0.0",
            "commit_id": "def456",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["displayId"] == "v2.0.0"
    mock_bitbucket_fetcher.create_tag.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        tag_name="v2.0.0",
        commit_id="def456",
        description=None,
    )


@pytest.mark.anyio
async def test_update_file(bitbucket_client, mock_bitbucket_fetcher):
    """Test the update_file tool commits a file change."""
    response = await bitbucket_client.call_tool(
        "update_file",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "file_path": "src/main.py",
            "content": "print('hello')",
            "commit_message": "Update main.py",
            "branch": "main",
            "source_commit_id": "abc123def456",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["id"] == "new_commit_hash"
    mock_bitbucket_fetcher.update_file.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        file_path="src/main.py",
        content="print('hello')",
        commit_message="Update main.py",
        branch="main",
        source_commit_id="abc123def456",
    )


@pytest.mark.anyio
async def test_get_pr_tasks(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_pr_tasks tool returns tasks on a PR."""
    response = await bitbucket_client.call_tool(
        "get_pr_tasks",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["state"] == "OPEN"
    assert content[1]["state"] == "RESOLVED"
    mock_bitbucket_fetcher.get_pr_tasks.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1
    )


@pytest.mark.anyio
async def test_get_pr_comments(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_pr_comments tool returns comments on a PR."""
    response = await bitbucket_client.call_tool(
        "get_pr_comments",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["id"] == 10
    assert content[0]["text"] == "LGTM"
    mock_bitbucket_fetcher.get_pr_comments.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, limit=100
    )


@pytest.mark.anyio
async def test_delete_pr_comment(bitbucket_client, mock_bitbucket_fetcher):
    """Test the delete_pr_comment tool deletes a comment from a PR."""
    response = await bitbucket_client.call_tool(
        "delete_pr_comment",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "comment_id": 10},
    )
    content = json.loads(response[0].text)
    assert content["success"] is True
    mock_bitbucket_fetcher.delete_pr_comment.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, comment_id=10, comment_version=0
    )


@pytest.mark.anyio
async def test_delete_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the delete_pull_request tool deletes a PR."""
    response = await bitbucket_client.call_tool(
        "delete_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert content["success"] is True
    mock_bitbucket_fetcher.delete_pull_request.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, pr_version=0
    )


@pytest.mark.anyio
async def test_update_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the update_pull_request tool updates PR title and description."""
    response = await bitbucket_client.call_tool(
        "update_pull_request",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "pr_id": 1,
            "title": "Updated title",
            "description": "Updated desc",
        },
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["title"] == "Updated title"
    mock_bitbucket_fetcher.update_pull_request.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        pr_id=1,
        title="Updated title",
        description="Updated desc",
        pr_version=None,
    )


@pytest.mark.anyio
async def test_get_repo(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_repo tool returns repository details."""
    response = await bitbucket_client.call_tool(
        "get_repo",
        {"project_key": "PROJ", "repo_slug": "my-repo"},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, dict)
    assert content["slug"] == "my-repo"
    mock_bitbucket_fetcher.get_repo.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo"
    )


@pytest.mark.anyio
async def test_update_pr_comment(bitbucket_client, mock_bitbucket_fetcher):
    """Test the update_pr_comment tool updates an existing comment."""
    response = await bitbucket_client.call_tool(
        "update_pr_comment",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "pr_id": 1,
            "comment_id": 10,
            "text": "Updated comment",
        },
    )
    content = json.loads(response[0].text)
    assert content["text"] == "Updated comment"
    mock_bitbucket_fetcher.update_pr_comment.assert_called_once_with(
        project_key="PROJ",
        repo_slug="my-repo",
        pr_id=1,
        comment_id=10,
        text="Updated comment",
        comment_version=0,
    )


@pytest.mark.anyio
async def test_reopen_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the reopen_pull_request tool re-opens a declined PR."""
    response = await bitbucket_client.call_tool(
        "reopen_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert content["state"] == "OPEN"
    mock_bitbucket_fetcher.reopen_pull_request.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, pr_version=0
    )


@pytest.mark.anyio
async def test_unapprove_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test the unapprove_pull_request tool removes approval."""
    response = await bitbucket_client.call_tool(
        "unapprove_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "user_slug": "jdoe"},
    )
    content = json.loads(response[0].text)
    assert content["status"] == "UNAPPROVED"
    mock_bitbucket_fetcher.unapprove_pull_request.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, user_slug="jdoe"
    )


@pytest.mark.anyio
async def test_add_pr_reviewer(bitbucket_client, mock_bitbucket_fetcher):
    """Test the add_pr_reviewer tool adds a reviewer to a PR."""
    response = await bitbucket_client.call_tool(
        "add_pr_reviewer",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "reviewer_slug": "jdoe"},
    )
    content = json.loads(response[0].text)
    assert content["reviewers"][0]["user"]["name"] == "jdoe"
    mock_bitbucket_fetcher.add_pr_reviewer.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, reviewer_slug="jdoe"
    )


@pytest.mark.anyio
async def test_get_pr_diff(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_pr_diff tool returns unified diff of a PR."""
    response = await bitbucket_client.call_tool(
        "get_pr_diff",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = response[0].text
    assert "diff --git" in content
    mock_bitbucket_fetcher.get_pr_diff.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, context_lines=10
    )


@pytest.mark.anyio
async def test_get_commit(bitbucket_client, mock_bitbucket_fetcher):
    """Test the get_commit tool returns details of a single commit."""
    response = await bitbucket_client.call_tool(
        "get_commit",
        {"project_key": "PROJ", "repo_slug": "my-repo", "commit_id": "abc123def456"},
    )
    content = json.loads(response[0].text)
    assert content["id"] == "abc123def456"
    assert content["message"] == "Fix login bug"
    mock_bitbucket_fetcher.get_commit.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", commit_id="abc123def456"
    )


@pytest.mark.anyio
async def test_search_code(bitbucket_client, mock_bitbucket_fetcher):
    """Test the search_code tool returns search results."""
    response = await bitbucket_client.call_tool(
        "search_code",
        {"project_key": "PROJ", "repo_slug": "my-repo", "query": "def main"},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["file"]["path"] == "src/main.py"
    mock_bitbucket_fetcher.search_code.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", query="def main", limit=25
    )


@pytest.mark.anyio
async def test_delete_tag(bitbucket_client, mock_bitbucket_fetcher):
    """Test the delete_tag tool deletes a tag."""
    response = await bitbucket_client.call_tool(
        "delete_tag",
        {"project_key": "PROJ", "repo_slug": "my-repo", "tag_name": "v1.0.0"},
    )
    content = json.loads(response[0].text)
    assert content["success"] is True
    mock_bitbucket_fetcher.delete_tag.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", tag_name="v1.0.0"
    )


@pytest.mark.anyio
async def test_add_pr_task(bitbucket_client, mock_bitbucket_fetcher):
    """Test the add_pr_task tool adds a task to a PR comment."""
    response = await bitbucket_client.call_tool(
        "add_pr_task",
        {"comment_id": 10, "text": "New task"},
    )
    content = json.loads(response[0].text)
    assert content["id"] == 3
    assert content["text"] == "New task"
    mock_bitbucket_fetcher.add_pr_task.assert_called_once_with(
        comment_id=10, text="New task"
    )


@pytest.mark.anyio
async def test_update_pr_task(bitbucket_client, mock_bitbucket_fetcher):
    """Test the update_pr_task tool updates a task state."""
    response = await bitbucket_client.call_tool(
        "update_pr_task",
        {"task_id": 1, "state": "RESOLVED"},
    )
    content = json.loads(response[0].text)
    assert content["state"] == "RESOLVED"
    mock_bitbucket_fetcher.update_pr_task.assert_called_once_with(
        task_id=1, text=None, state="RESOLVED"
    )
