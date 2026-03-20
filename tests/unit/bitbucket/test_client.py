"""Unit tests for BitbucketFetcher client."""
from unittest.mock import MagicMock, patch

import pytest

from mcp_atlassian.bitbucket.client import BitbucketFetcher
from mcp_atlassian.bitbucket.config import BitbucketConfig


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
    with patch("mcp_atlassian.bitbucket.client.Bitbucket", return_value=mock_bb_api):
        f = BitbucketFetcher(config=config)
        f.bb = mock_bb_api
        return f


def test_get_projects_returns_list(fetcher, mock_bb_api):
    """get_projects delegates to bb.project_list and returns a list."""
    mock_bb_api.project_list.return_value = [{"key": "PROJ", "name": "Project"}]
    result = fetcher.get_projects(limit=10)
    assert isinstance(result, list)
    assert result[0]["key"] == "PROJ"
    mock_bb_api.project_list.assert_called_once_with(limit=10)


def test_get_repos_returns_list(fetcher, mock_bb_api):
    """get_repos delegates to bb.repo_list with project key."""
    mock_bb_api.repo_list.return_value = [{"slug": "my-repo", "name": "My Repo"}]
    result = fetcher.get_repos("PROJ", limit=25)
    assert result[0]["slug"] == "my-repo"
    mock_bb_api.repo_list.assert_called_once_with("PROJ", limit=25)


def test_get_pull_requests(fetcher, mock_bb_api):
    """get_pull_requests delegates with state and order."""
    mock_bb_api.get_pull_requests.return_value = [{"id": 1, "title": "Fix bug"}]
    result = fetcher.get_pull_requests("PROJ", "my-repo", state="OPEN", limit=25)
    assert result[0]["id"] == 1
    mock_bb_api.get_pull_requests.assert_called_once_with(
        "PROJ", "my-repo", state="OPEN", order="newest", limit=25
    )


def test_get_pull_request(fetcher, mock_bb_api):
    """get_pull_request retrieves a single PR by ID."""
    mock_bb_api.get_pull_request.return_value = {"id": 42, "title": "Feature"}
    result = fetcher.get_pull_request("PROJ", "my-repo", 42)
    assert result["id"] == 42
    mock_bb_api.get_pull_request.assert_called_once_with("PROJ", "my-repo", 42)


def test_create_pull_request(fetcher, mock_bb_api):
    """create_pull_request calls open_pull_request with correct args."""
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
    mock_bb_api.open_pull_request.assert_called_once_with(
        source_project="PROJ",
        source_repo="my-repo",
        dest_project="PROJ",
        dest_repo="my-repo",
        title="New PR",
        description="desc",
        source_branch="feature/x",
        destination_branch="main",
        reviewers=[],
    )


def test_get_commits(fetcher, mock_bb_api):
    """get_commits delegates to bb.get_commits with branch as hash_newest."""
    mock_bb_api.get_commits.return_value = [{"id": "abc123"}]
    result = fetcher.get_commits("PROJ", "my-repo", branch="main", limit=25)
    assert result[0]["id"] == "abc123"
    mock_bb_api.get_commits.assert_called_once_with(
        "PROJ", "my-repo", hash_newest="main", limit=25
    )


def test_get_branches(fetcher, mock_bb_api):
    """get_branches delegates to bb.get_branches."""
    mock_bb_api.get_branches.return_value = [{"displayId": "main"}]
    result = fetcher.get_branches("PROJ", "my-repo", limit=25)
    assert result[0]["displayId"] == "main"
    mock_bb_api.get_branches.assert_called_once_with("PROJ", "my-repo", limit=25)


def test_get_file_content(fetcher, mock_bb_api):
    """get_file_content delegates to bb.get_content_of_file with at=branch."""
    mock_bb_api.get_content_of_file.return_value = "file content here"
    result = fetcher.get_file_content("PROJ", "my-repo", "README.md", branch="main")
    assert result == "file content here"
    mock_bb_api.get_content_of_file.assert_called_once_with(
        "PROJ", "my-repo", "README.md", at="main"
    )
