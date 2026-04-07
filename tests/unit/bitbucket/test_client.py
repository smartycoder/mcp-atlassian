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


# --- PR Review & Lifecycle ---


def test_get_pr_comments(fetcher, mock_bb_api):
    """get_pr_comments calls _url_pull_request_comments and _get_paged."""
    mock_bb_api._url_pull_request_comments.return_value = "http://bb/comments"
    mock_bb_api._get_paged.return_value = [{"id": 10, "text": "LGTM"}]
    result = fetcher.get_pr_comments("PROJ", "my-repo", 42)
    assert isinstance(result, list)
    assert result[0]["id"] == 10
    mock_bb_api._url_pull_request_comments.assert_called_once_with("PROJ", "my-repo", 42)
    mock_bb_api._get_paged.assert_called_once_with("http://bb/comments", params={"limit": 100})


def test_add_pr_comment(fetcher, mock_bb_api):
    """add_pr_comment delegates to bb.add_pull_request_comment without parent."""
    mock_bb_api.add_pull_request_comment.return_value = {"id": 10, "text": "LGTM"}
    result = fetcher.add_pr_comment("PROJ", "my-repo", 42, "LGTM")
    assert result["id"] == 10
    mock_bb_api.add_pull_request_comment.assert_called_once_with(
        "PROJ", "my-repo", 42, "LGTM", parent_id=None
    )


def test_add_pr_comment_with_parent(fetcher, mock_bb_api):
    """add_pr_comment passes parent_id when provided for threaded replies."""
    mock_bb_api.add_pull_request_comment.return_value = {"id": 11, "text": "Agreed"}
    result = fetcher.add_pr_comment("PROJ", "my-repo", 42, "Agreed", parent_id=10)
    assert result["id"] == 11
    mock_bb_api.add_pull_request_comment.assert_called_once_with(
        "PROJ", "my-repo", 42, "Agreed", parent_id=10
    )


def test_merge_pull_request(fetcher, mock_bb_api):
    """merge_pull_request delegates to bb.merge_pull_request with all params."""
    mock_bb_api.merge_pull_request.return_value = {"id": 42, "state": "MERGED"}
    result = fetcher.merge_pull_request(
        "PROJ", "my-repo", 42, "Merging feature", close_source_branch=True,
        merge_strategy="squash", pr_version=3
    )
    assert result["state"] == "MERGED"
    mock_bb_api.merge_pull_request.assert_called_once_with(
        "PROJ", "my-repo", 42, "Merging feature",
        close_source_branch=True,
        merge_strategy="squash",
        pr_version=3,
    )


def test_decline_pull_request(fetcher, mock_bb_api):
    """decline_pull_request delegates to bb.decline_pull_request with version."""
    mock_bb_api.decline_pull_request.return_value = {"id": 42, "state": "DECLINED"}
    result = fetcher.decline_pull_request("PROJ", "my-repo", 42, pr_version=2)
    assert result["state"] == "DECLINED"
    mock_bb_api.decline_pull_request.assert_called_once_with("PROJ", "my-repo", 42, 2)


def test_approve_pull_request(fetcher, mock_bb_api):
    """approve_pull_request calls change_reviewed_status with APPROVED status."""
    mock_bb_api.change_reviewed_status.return_value = {"approved": True}
    result = fetcher.approve_pull_request("PROJ", "my-repo", 42, "jdoe")
    assert result["approved"] is True
    mock_bb_api.change_reviewed_status.assert_called_once_with(
        "PROJ", "my-repo", 42, "APPROVED", "jdoe"
    )


def test_delete_pr_comment(fetcher, mock_bb_api):
    """delete_pr_comment delegates to bb.delete_pull_request_comment."""
    mock_bb_api.delete_pull_request_comment.return_value = None
    result = fetcher.delete_pr_comment("PROJ", "my-repo", 42, 10, comment_version=1)
    assert result is None
    mock_bb_api.delete_pull_request_comment.assert_called_once_with(
        "PROJ", "my-repo", 42, 10, 1
    )


def test_delete_pull_request(fetcher, mock_bb_api):
    """delete_pull_request delegates to bb.delete_pull_request."""
    mock_bb_api.delete_pull_request.return_value = None
    result = fetcher.delete_pull_request("PROJ", "my-repo", 42, pr_version=1)
    assert result is None
    mock_bb_api.delete_pull_request.assert_called_once_with("PROJ", "my-repo", 42, 1)


def test_update_pull_request(fetcher, mock_bb_api):
    """update_pull_request fetches current PR and sends updated data."""
    mock_bb_api.get_pull_request.return_value = {
        "title": "Old title",
        "description": "Old desc",
        "reviewers": [{"user": {"name": "jdoe"}}],
        "toRef": {"id": "refs/heads/main"},
        "fromRef": {"id": "refs/heads/feature/x"},
    }
    mock_bb_api.update_pull_request.return_value = {"id": 42, "title": "New title"}
    result = fetcher.update_pull_request(
        "PROJ", "my-repo", 42, title="New title", description="New desc", pr_version=2
    )
    assert result["title"] == "New title"
    mock_bb_api.get_pull_request.assert_called_once_with("PROJ", "my-repo", 42)
    mock_bb_api.update_pull_request.assert_called_once_with(
        "PROJ", "my-repo", 42,
        {
            "version": 2,
            "title": "New title",
            "description": "New desc",
            "reviewers": [{"user": {"name": "jdoe"}}],
            "toRef": {"id": "refs/heads/main"},
            "fromRef": {"id": "refs/heads/feature/x"},
        },
    )


def test_update_pull_request_partial(fetcher, mock_bb_api):
    """update_pull_request keeps existing title when only description changes."""
    mock_bb_api.get_pull_request.return_value = {
        "title": "Keep this",
        "description": "Old",
        "reviewers": [],
        "toRef": {"id": "refs/heads/main"},
        "fromRef": {"id": "refs/heads/feature/x"},
    }
    mock_bb_api.update_pull_request.return_value = {"id": 42, "title": "Keep this", "description": "Updated"}
    result = fetcher.update_pull_request("PROJ", "my-repo", 42, description="Updated")
    assert result["title"] == "Keep this"
    call_data = mock_bb_api.update_pull_request.call_args[0][3]
    assert call_data["title"] == "Keep this"
    assert call_data["description"] == "Updated"


def test_get_pr_changes(fetcher, mock_bb_api):
    """get_pr_changes delegates to bb.get_pull_requests_changes and wraps in list."""
    mock_bb_api.get_pull_requests_changes.return_value = [{"path": {"toString": "src/foo.py"}}]
    result = fetcher.get_pr_changes("PROJ", "my-repo", 42)
    assert isinstance(result, list)
    assert result[0]["path"]["toString"] == "src/foo.py"
    mock_bb_api.get_pull_requests_changes.assert_called_once_with(
        "PROJ", "my-repo", 42, start=0, limit=None
    )


# --- Code Browsing ---


def test_get_diff(fetcher, mock_bb_api):
    """get_diff delegates to bb.get_diff and returns the result directly."""
    segments = [{"type": "CONTEXT", "lines": []}]
    mock_bb_api.get_diff.return_value = segments
    result = fetcher.get_diff("PROJ", "my-repo", "src/foo.py", "abc123", "def456")
    assert result is segments
    mock_bb_api.get_diff.assert_called_once_with(
        "PROJ", "my-repo", "src/foo.py", "abc123", "def456"
    )


def test_get_file_list(fetcher, mock_bb_api):
    """get_file_list delegates to bb.get_file_list and wraps result in list."""
    mock_bb_api.get_file_list.return_value = ["src/foo.py", "src/bar.py"]
    result = fetcher.get_file_list("PROJ", "my-repo")
    assert result == ["src/foo.py", "src/bar.py"]
    mock_bb_api.get_file_list.assert_called_once_with(
        "PROJ", "my-repo", sub_folder=None, query=None, start=0, limit=None
    )


def test_get_file_list_with_subfolder_and_ref(fetcher, mock_bb_api):
    """get_file_list passes sub_folder and ref as query to upstream."""
    mock_bb_api.get_file_list.return_value = ["src/sub/a.py"]
    result = fetcher.get_file_list("PROJ", "my-repo", sub_folder="src/sub", ref="feature/x")
    assert result == ["src/sub/a.py"]
    mock_bb_api.get_file_list.assert_called_once_with(
        "PROJ", "my-repo", sub_folder="src/sub", query="feature/x", start=0, limit=None
    )


# --- Branch & Tag Management ---


def test_create_branch(fetcher, mock_bb_api):
    """create_branch delegates to bb.create_branch with all arguments."""
    mock_bb_api.create_branch.return_value = {"displayId": "feature/new", "id": "refs/heads/feature/new"}
    result = fetcher.create_branch("PROJ", "my-repo", "feature/new", "main", message="New branch")
    assert result["displayId"] == "feature/new"
    mock_bb_api.create_branch.assert_called_once_with(
        "PROJ", "my-repo", "feature/new", "main", message="New branch"
    )


def test_delete_branch(fetcher, mock_bb_api):
    """delete_branch delegates to bb.delete_branch with end_point=None."""
    mock_bb_api.delete_branch.return_value = None
    fetcher.delete_branch("PROJ", "my-repo", "feature/old")
    mock_bb_api.delete_branch.assert_called_once_with(
        "PROJ", "my-repo", "feature/old", end_point=None
    )


def test_get_tags(fetcher, mock_bb_api):
    """get_tags delegates to bb.get_tags with default filter and order_by."""
    mock_bb_api.get_tags.return_value = [{"displayId": "v1.0.0"}]
    result = fetcher.get_tags("PROJ", "my-repo", limit=10)
    assert result[0]["displayId"] == "v1.0.0"
    mock_bb_api.get_tags.assert_called_once_with(
        "PROJ", "my-repo", filter="", limit=10, order_by=None, start=0
    )


def test_create_tag(fetcher, mock_bb_api):
    """create_tag delegates to bb.set_tag with all arguments."""
    mock_bb_api.set_tag.return_value = {"displayId": "v2.0.0"}
    result = fetcher.create_tag("PROJ", "my-repo", "v2.0.0", "abc123", description="Release 2.0")
    assert result["displayId"] == "v2.0.0"
    mock_bb_api.set_tag.assert_called_once_with(
        "PROJ", "my-repo", "v2.0.0", "abc123", description="Release 2.0"
    )


# --- File Editing ---


def test_update_file(fetcher, mock_bb_api):
    """update_file passes args to bb.update_file with correct upstream order."""
    mock_bb_api.update_file.return_value = {"id": "deadbeef"}
    result = fetcher.update_file(
        "PROJ", "my-repo", "src/foo.py", "new content", "Update foo", "main", "oldcommit"
    )
    assert result["id"] == "deadbeef"
    mock_bb_api.update_file.assert_called_once_with(
        "PROJ", "my-repo", "new content", "Update foo", "main", "src/foo.py", "oldcommit"
    )


# --- PR Tasks ---


def test_get_pr_tasks_with_dict_response(fetcher, mock_bb_api):
    """get_pr_tasks extracts 'values' when upstream returns a paginated dict."""
    mock_bb_api.get_tasks.return_value = {"values": [{"id": 1, "text": "Fix this"}], "size": 1}
    result = fetcher.get_pr_tasks("PROJ", "my-repo", 42)
    assert isinstance(result, list)
    assert result[0]["id"] == 1
    mock_bb_api.get_tasks.assert_called_once_with("PROJ", "my-repo", 42)


def test_get_pr_tasks_with_list_response(fetcher, mock_bb_api):
    """get_pr_tasks wraps result in list when upstream returns an iterable."""
    mock_bb_api.get_tasks.return_value = [{"id": 2, "text": "Do that"}]
    result = fetcher.get_pr_tasks("PROJ", "my-repo", 42)
    assert isinstance(result, list)
    assert result[0]["id"] == 2
    mock_bb_api.get_tasks.assert_called_once_with("PROJ", "my-repo", 42)


def test_update_pr_comment(fetcher, mock_bb_api):
    """update_pr_comment delegates to bb.update_pull_request_comment."""
    mock_bb_api.update_pull_request_comment.return_value = {"id": 10, "text": "Updated"}
    result = fetcher.update_pr_comment("PROJ", "my-repo", 42, 10, "Updated", comment_version=1)
    assert result["text"] == "Updated"
    mock_bb_api.update_pull_request_comment.assert_called_once_with(
        "PROJ", "my-repo", 42, 10, "Updated", 1
    )


def test_reopen_pull_request(fetcher, mock_bb_api):
    """reopen_pull_request delegates to bb.reopen_pull_request."""
    mock_bb_api.reopen_pull_request.return_value = {"id": 42, "state": "OPEN"}
    result = fetcher.reopen_pull_request("PROJ", "my-repo", 42, pr_version=1)
    assert result["state"] == "OPEN"
    mock_bb_api.reopen_pull_request.assert_called_once_with("PROJ", "my-repo", 42, 1)


def test_unapprove_pull_request(fetcher, mock_bb_api):
    """unapprove_pull_request calls change_reviewed_status with UNAPPROVED."""
    mock_bb_api.change_reviewed_status.return_value = {"status": "UNAPPROVED"}
    result = fetcher.unapprove_pull_request("PROJ", "my-repo", 42, "jdoe")
    assert result["status"] == "UNAPPROVED"
    mock_bb_api.change_reviewed_status.assert_called_once_with(
        "PROJ", "my-repo", 42, "UNAPPROVED", "jdoe"
    )


def test_add_pr_reviewer(fetcher, mock_bb_api):
    """add_pr_reviewer fetches current PR, appends reviewer, and updates."""
    mock_bb_api.get_pull_request.return_value = {
        "title": "PR title",
        "description": "desc",
        "version": 3,
        "reviewers": [],
        "toRef": {"id": "refs/heads/main"},
        "fromRef": {"id": "refs/heads/feature/x"},
    }
    mock_bb_api.update_pull_request.return_value = {"id": 42, "reviewers": [{"user": {"name": "jdoe"}}]}
    result = fetcher.add_pr_reviewer("PROJ", "my-repo", 42, "jdoe")
    assert result["reviewers"][0]["user"]["name"] == "jdoe"
    call_data = mock_bb_api.update_pull_request.call_args[0][3]
    assert call_data["reviewers"] == [{"user": {"name": "jdoe"}}]
    assert call_data["version"] == 3


def test_get_pr_diff(fetcher, mock_bb_api):
    """get_pr_diff calls the PR diff endpoint with contextLines."""
    mock_bb_api._url_pull_request.return_value = "http://bb/pr/42"
    mock_bb_api.get.return_value = b"diff --git a/foo b/foo"
    result = fetcher.get_pr_diff("PROJ", "my-repo", 42, context_lines=5)
    assert result == b"diff --git a/foo b/foo"
    mock_bb_api.get.assert_called_once_with(
        "http://bb/pr/42/diff", params={"contextLines": 5}, not_json_response=True
    )


def test_get_commit(fetcher, mock_bb_api):
    """get_commit delegates to bb.get_commit_info."""
    mock_bb_api.get_commit_info.return_value = {"id": "abc123", "message": "Fix bug"}
    result = fetcher.get_commit("PROJ", "my-repo", "abc123")
    assert result["id"] == "abc123"
    mock_bb_api.get_commit_info.assert_called_once_with("PROJ", "my-repo", "abc123")


def test_search_code(fetcher, mock_bb_api):
    """search_code calls the REST search endpoint."""
    mock_bb_api.url = "https://bitbucket.example.com"
    mock_bb_api.get.return_value = {
        "code": {"values": [{"file": {"path": "src/main.py"}}]}
    }
    result = fetcher.search_code("PROJ", "my-repo", "def main", limit=10)
    assert result[0]["file"]["path"] == "src/main.py"
    mock_bb_api.get.assert_called_once_with(
        "https://bitbucket.example.com/rest/search/latest/search",
        params={
            "query": "def main",
            "entities": "code",
            "limits.primary.count": 10,
            "repositoryName": "my-repo",
            "projectKey": "PROJ",
        },
    )


def test_delete_tag(fetcher, mock_bb_api):
    """delete_tag delegates to bb.delete_tag."""
    mock_bb_api.delete_tag.return_value = None
    fetcher.delete_tag("PROJ", "my-repo", "v1.0.0")
    mock_bb_api.delete_tag.assert_called_once_with("PROJ", "my-repo", "v1.0.0")


def test_add_pr_task(fetcher, mock_bb_api):
    """add_pr_task delegates to bb.add_task with comment anchor."""
    mock_bb_api.add_task.return_value = {"id": 3, "text": "New task", "state": "OPEN"}
    result = fetcher.add_pr_task(10, "New task")
    assert result["id"] == 3
    mock_bb_api.add_task.assert_called_once_with(10, "New task")


def test_update_pr_task(fetcher, mock_bb_api):
    """update_pr_task delegates to bb.update_task with state."""
    mock_bb_api.update_task.return_value = {"id": 1, "state": "RESOLVED"}
    result = fetcher.update_pr_task(1, state="RESOLVED")
    assert result["state"] == "RESOLVED"
    mock_bb_api.update_task.assert_called_once_with(1, text=None, state="RESOLVED")
