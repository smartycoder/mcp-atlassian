# Bitbucket Extended Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 13 new Bitbucket MCP tools for PR review/lifecycle, code browsing, branch/tag management, and file editing.

**Architecture:** Thin-wrapper approach - add methods to existing `BitbucketFetcher` in `client.py`, then expose as MCP tools in `servers/bitbucket.py`. Each tool follows the established pattern: async function, `get_bitbucket_fetcher(ctx)`, JSON serialization, write tools get `@check_write_access`.

**Tech Stack:** Python 3.11, FastMCP, atlassian-python-api (Bitbucket class), pytest + anyio

**API notes from `atlassian-python-api` signatures:**
- `merge_pull_request(self, project_key, repository_slug, pr_id, merge_message, close_source_branch=False, merge_strategy=<MergeStrategy.MERGE_COMMIT>, pr_version=None)`
- `decline_pull_request(self, project_key, repository_slug, pr_id, pr_version)` - requires `pr_version` (int from PR object `"version"` field)
- `add_pull_request_comment(self, project_key, repository_slug, pull_request_id, text, parent_id=None)`
- `get_pull_requests_changes(self, project_key, repository_slug, pull_request_id, start=0, limit=None)` - uses `_get_paged`, returns generator/list of change objects directly (NOT a dict with `"values"` key)
- `get_diff(self, project_key, repository_slug, path, hash_oldest, hash_newest)` - returns `response.get("diffs")`, which is a list of diff segment dicts (NOT a unified-diff string)
- `get_file_list(self, project_key, repository_slug, sub_folder=None, query=None, start=0, limit=None)` - `query` is a branch/commit ref (maps to `?at=`), NOT a filename filter. Uses `_get_paged`, returns list of **strings** (file paths), NOT dicts.
- `get_tasks(self, project_key, repository_slug, pull_request_id)` - uses `self.get()` directly, may return paginated dict with `"values"` key
- `create_branch(self, project_key, repository_slug, name, start_point, message='')`
- `delete_branch(self, project_key, repository_slug, name, end_point=None)`
- `get_tags(self, project_key, repository_slug, filter='', limit=1000, order_by=None, start=0)`
- `set_tag(self, project_key, repository_slug, tag_name, commit_revision, description=None)`
- `change_reviewed_status(self, project_key, repository_slug, pull_request_id, status, user_slug)`
- `update_file(self, project_key, repository_slug, content, message, branch, filename, source_commit_id)`
- `get_tasks(self, project_key, repository_slug, pull_request_id)`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/mcp_atlassian/bitbucket/client.py` | Modify | Add 13 new methods to BitbucketFetcher |
| `src/mcp_atlassian/servers/bitbucket.py` | Modify | Add 13 new MCP tool definitions |
| `tests/unit/bitbucket/test_client.py` | Modify | Add unit tests for each new client method |
| `tests/unit/servers/test_bitbucket_server.py` | Modify | Add integration tests for each new MCP tool |
| `tests/fixtures/bitbucket_mocks.py` | Modify | Add mock data for new operations |

---

### Task 1: PR Comment & Review Tools (client layer)

**Files:**
- Modify: `src/mcp_atlassian/bitbucket/client.py`
- Test: `tests/unit/bitbucket/test_client.py`

- [ ] **Step 1: Write failing tests for add_pr_comment, merge_pr, decline_pr, approve_pr, get_pr_changes**

Add to `tests/unit/bitbucket/test_client.py`:

```python
def test_add_pr_comment(fetcher, mock_bb_api):
    """add_pr_comment delegates to bb.add_pull_request_comment."""
    mock_bb_api.add_pull_request_comment.return_value = {"id": 10, "text": "LGTM"}
    result = fetcher.add_pr_comment("PROJ", "my-repo", 1, "LGTM")
    assert result["id"] == 10
    mock_bb_api.add_pull_request_comment.assert_called_once_with(
        "PROJ", "my-repo", 1, "LGTM", parent_id=None
    )


def test_add_pr_comment_with_parent(fetcher, mock_bb_api):
    """add_pr_comment supports threaded replies via parent_id."""
    mock_bb_api.add_pull_request_comment.return_value = {"id": 11, "text": "Reply"}
    result = fetcher.add_pr_comment("PROJ", "my-repo", 1, "Reply", parent_id=5)
    mock_bb_api.add_pull_request_comment.assert_called_once_with(
        "PROJ", "my-repo", 1, "Reply", parent_id=5
    )


def test_merge_pull_request(fetcher, mock_bb_api):
    """merge_pull_request delegates with merge strategy."""
    mock_bb_api.merge_pull_request.return_value = {"id": 1, "state": "MERGED"}
    result = fetcher.merge_pull_request("PROJ", "my-repo", 1, "Merging PR")
    assert result["state"] == "MERGED"
    mock_bb_api.merge_pull_request.assert_called_once_with(
        "PROJ", "my-repo", 1, "Merging PR",
        close_source_branch=False, merge_strategy="merge_commit", pr_version=None
    )


def test_decline_pull_request(fetcher, mock_bb_api):
    """decline_pull_request delegates with pr_version."""
    mock_bb_api.decline_pull_request.return_value = {"id": 1, "state": "DECLINED"}
    result = fetcher.decline_pull_request("PROJ", "my-repo", 1, pr_version=0)
    assert result["state"] == "DECLINED"
    mock_bb_api.decline_pull_request.assert_called_once_with("PROJ", "my-repo", 1, 0)


def test_approve_pull_request(fetcher, mock_bb_api):
    """approve_pull_request delegates to change_reviewed_status with APPROVED."""
    mock_bb_api.change_reviewed_status.return_value = {"status": "APPROVED"}
    result = fetcher.approve_pull_request("PROJ", "my-repo", 1, "jdoe")
    assert result["status"] == "APPROVED"
    mock_bb_api.change_reviewed_status.assert_called_once_with(
        "PROJ", "my-repo", 1, "APPROVED", "jdoe"
    )


def test_get_pr_changes(fetcher, mock_bb_api):
    """get_pr_changes delegates to get_pull_requests_changes and returns list."""
    mock_bb_api.get_pull_requests_changes.return_value = [
        {"path": {"toString": "src/main.py"}, "type": "MODIFY"},
        {"path": {"toString": "tests/test_main.py"}, "type": "ADD"},
    ]
    result = fetcher.get_pr_changes("PROJ", "my-repo", 1)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["path"]["toString"] == "src/main.py"
    mock_bb_api.get_pull_requests_changes.assert_called_once_with(
        "PROJ", "my-repo", 1, start=0, limit=None
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/bitbucket/test_client.py -v -k "test_add_pr_comment or test_merge_pull_request or test_decline_pull_request or test_approve_pull_request or test_get_pr_changes"`
Expected: FAIL with `AttributeError: 'BitbucketFetcher' object has no attribute ...`

- [ ] **Step 3: Implement client methods**

Add to `src/mcp_atlassian/bitbucket/client.py` after `get_file_content`:

```python
    # --- PR Review & Lifecycle ---

    def add_pr_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Add a comment to a pull request. Use parent_id for threaded replies."""
        return self.bb.add_pull_request_comment(
            project_key, repo_slug, pr_id, text, parent_id=parent_id
        )

    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        merge_message: str,
        close_source_branch: bool = False,
        merge_strategy: str = "merge_commit",
        pr_version: int | None = None,
    ) -> dict[str, Any]:
        """Merge a pull request. merge_strategy: merge_commit, squash, fast_forward."""
        return self.bb.merge_pull_request(
            project_key,
            repo_slug,
            pr_id,
            merge_message,
            close_source_branch=close_source_branch,
            merge_strategy=merge_strategy,
            pr_version=pr_version,
        )

    def decline_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        pr_version: int = 0,
    ) -> dict[str, Any]:
        """Decline/reject a pull request."""
        return self.bb.decline_pull_request(project_key, repo_slug, pr_id, pr_version)

    def approve_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        user_slug: str,
    ) -> dict[str, Any]:
        """Approve a pull request as a specific user."""
        return self.bb.change_reviewed_status(
            project_key, repo_slug, pr_id, "APPROVED", user_slug
        )

    def get_pr_changes(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
    ) -> list[dict[str, Any]]:
        """Get list of files changed in a pull request. Returns list of change objects."""
        result = self.bb.get_pull_requests_changes(
            project_key, repo_slug, pr_id, start=0, limit=None
        )
        return list(result) if result else []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/bitbucket/test_client.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/bitbucket/client.py tests/unit/bitbucket/test_client.py
git commit -m "feat(bitbucket): add PR review & lifecycle client methods"
```

---

### Task 2: Code Browsing Tools (client layer)

**Files:**
- Modify: `src/mcp_atlassian/bitbucket/client.py`
- Test: `tests/unit/bitbucket/test_client.py`

- [ ] **Step 1: Write failing tests for get_diff, get_file_list**

Add to `tests/unit/bitbucket/test_client.py`:

```python
def test_get_diff(fetcher, mock_bb_api):
    """get_diff delegates to bb.get_diff with path and hashes. Returns list of diff segments."""
    mock_bb_api.get_diff.return_value = [
        {"source": {"toString": "src/main.py"}, "destination": {"toString": "src/main.py"},
         "hunks": [{"segments": [{"type": "REMOVED", "lines": [{"line": "old"}]},
                                 {"type": "ADDED", "lines": [{"line": "new"}]}]}]}
    ]
    result = fetcher.get_diff("PROJ", "my-repo", "src/main.py", "abc123", "def456")
    assert isinstance(result, list)
    assert result[0]["source"]["toString"] == "src/main.py"
    mock_bb_api.get_diff.assert_called_once_with(
        "PROJ", "my-repo", "src/main.py", "abc123", "def456"
    )


def test_get_file_list(fetcher, mock_bb_api):
    """get_file_list delegates to bb.get_file_list. Returns list of file path strings."""
    mock_bb_api.get_file_list.return_value = ["src/main.py", "README.md", "setup.py"]
    result = fetcher.get_file_list("PROJ", "my-repo")
    assert len(result) == 3
    assert result[0] == "src/main.py"
    mock_bb_api.get_file_list.assert_called_once_with(
        "PROJ", "my-repo", sub_folder=None, query=None, start=0, limit=None
    )


def test_get_file_list_with_subfolder_and_ref(fetcher, mock_bb_api):
    """get_file_list can filter by sub_folder and branch ref (query param)."""
    mock_bb_api.get_file_list.return_value = ["src/main.py"]
    result = fetcher.get_file_list("PROJ", "my-repo", sub_folder="src", ref="develop")
    mock_bb_api.get_file_list.assert_called_once_with(
        "PROJ", "my-repo", sub_folder="src", query="develop", start=0, limit=None
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/bitbucket/test_client.py -v -k "test_get_diff or test_get_file_list"`
Expected: FAIL

- [ ] **Step 3: Implement client methods**

Add to `src/mcp_atlassian/bitbucket/client.py`:

```python
    # --- Code Browsing ---

    def get_diff(
        self,
        project_key: str,
        repo_slug: str,
        path: str,
        hash_oldest: str,
        hash_newest: str,
    ) -> list[dict[str, Any]] | None:
        """Get diff between two commits for a given path. Returns list of diff segment dicts."""
        return self.bb.get_diff(project_key, repo_slug, path, hash_oldest, hash_newest)

    def get_file_list(
        self,
        project_key: str,
        repo_slug: str,
        sub_folder: str | None = None,
        ref: str | None = None,
    ) -> list[str]:
        """List file paths in a repository directory. ref is a branch/tag/commit to list at."""
        result = self.bb.get_file_list(
            project_key, repo_slug, sub_folder=sub_folder, query=ref, start=0, limit=None
        )
        return list(result) if result else []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/bitbucket/test_client.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/bitbucket/client.py tests/unit/bitbucket/test_client.py
git commit -m "feat(bitbucket): add code browsing client methods (diff, file list)"
```

---

### Task 3: Branch, Tag & File Management (client layer)

**Files:**
- Modify: `src/mcp_atlassian/bitbucket/client.py`
- Test: `tests/unit/bitbucket/test_client.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/bitbucket/test_client.py`:

```python
def test_create_branch(fetcher, mock_bb_api):
    """create_branch delegates to bb.create_branch."""
    mock_bb_api.create_branch.return_value = {"displayId": "feature/new", "type": "BRANCH"}
    result = fetcher.create_branch("PROJ", "my-repo", "feature/new", "main")
    assert result["displayId"] == "feature/new"
    mock_bb_api.create_branch.assert_called_once_with(
        "PROJ", "my-repo", "feature/new", "main", message=""
    )


def test_delete_branch(fetcher, mock_bb_api):
    """delete_branch delegates to bb.delete_branch."""
    mock_bb_api.delete_branch.return_value = None
    fetcher.delete_branch("PROJ", "my-repo", "feature/old")
    mock_bb_api.delete_branch.assert_called_once_with(
        "PROJ", "my-repo", "feature/old", end_point=None
    )


def test_get_tags(fetcher, mock_bb_api):
    """get_tags delegates to bb.get_tags."""
    mock_bb_api.get_tags.return_value = [{"displayId": "v1.0.0", "latestCommit": "abc123"}]
    result = fetcher.get_tags("PROJ", "my-repo", limit=25)
    assert result[0]["displayId"] == "v1.0.0"
    mock_bb_api.get_tags.assert_called_once_with(
        "PROJ", "my-repo", filter="", limit=25, order_by=None, start=0
    )


def test_create_tag(fetcher, mock_bb_api):
    """create_tag delegates to bb.set_tag."""
    mock_bb_api.set_tag.return_value = {"displayId": "v2.0.0", "latestCommit": "def456"}
    result = fetcher.create_tag("PROJ", "my-repo", "v2.0.0", "def456", description="Release")
    assert result["displayId"] == "v2.0.0"
    mock_bb_api.set_tag.assert_called_once_with(
        "PROJ", "my-repo", "v2.0.0", "def456", description="Release"
    )


def test_update_file(fetcher, mock_bb_api):
    """update_file delegates to bb.update_file."""
    mock_bb_api.update_file.return_value = {"id": "new_commit_hash"}
    result = fetcher.update_file(
        "PROJ", "my-repo", "README.md", "# Updated", "Update readme", "main", "abc123"
    )
    assert result["id"] == "new_commit_hash"
    mock_bb_api.update_file.assert_called_once_with(
        "PROJ", "my-repo", "# Updated", "Update readme", "main", "README.md", "abc123"
    )


def test_get_pr_tasks(fetcher, mock_bb_api):
    """get_pr_tasks delegates to bb.get_tasks."""
    mock_bb_api.get_tasks.return_value = [{"id": 1, "text": "Fix tests", "state": "OPEN"}]
    result = fetcher.get_pr_tasks("PROJ", "my-repo", 1)
    assert result[0]["text"] == "Fix tests"
    mock_bb_api.get_tasks.assert_called_once_with("PROJ", "my-repo", 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/bitbucket/test_client.py -v -k "test_create_branch or test_delete_branch or test_get_tags or test_create_tag or test_update_file or test_get_pr_tasks"`
Expected: FAIL

- [ ] **Step 3: Implement client methods**

Add to `src/mcp_atlassian/bitbucket/client.py`:

```python
    # --- Branch & Tag Management ---

    def create_branch(
        self,
        project_key: str,
        repo_slug: str,
        name: str,
        start_point: str,
        message: str = "",
    ) -> dict[str, Any]:
        """Create a new branch from a start point (branch name or commit hash)."""
        return self.bb.create_branch(
            project_key, repo_slug, name, start_point, message=message
        )

    def delete_branch(
        self,
        project_key: str,
        repo_slug: str,
        name: str,
    ) -> None:
        """Delete a branch."""
        self.bb.delete_branch(project_key, repo_slug, name, end_point=None)

    def get_tags(
        self,
        project_key: str,
        repo_slug: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """List tags in a repository."""
        result = self.bb.get_tags(
            project_key, repo_slug, filter="", limit=limit, order_by=None, start=0
        )
        return list(result) if result else []

    def create_tag(
        self,
        project_key: str,
        repo_slug: str,
        tag_name: str,
        commit_id: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create an annotated tag at a specific commit."""
        return self.bb.set_tag(
            project_key, repo_slug, tag_name, commit_id, description=description
        )

    # --- File Editing ---

    def update_file(
        self,
        project_key: str,
        repo_slug: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
        source_commit_id: str,
    ) -> dict[str, Any]:
        """Edit a file and commit the change. source_commit_id prevents conflicting updates."""
        return self.bb.update_file(
            project_key, repo_slug, content, commit_message, branch, file_path, source_commit_id
        )

    # --- PR Tasks ---

    def get_pr_tasks(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
    ) -> list[dict[str, Any]]:
        """Get checklist tasks on a pull request."""
        result = self.bb.get_tasks(project_key, repo_slug, pr_id)
        # get_tasks uses self.get() directly; handle both list and paginated dict responses
        if isinstance(result, dict):
            return result.get("values", [])
        return list(result) if result else []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/bitbucket/test_client.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/bitbucket/client.py tests/unit/bitbucket/test_client.py
git commit -m "feat(bitbucket): add branch, tag, file edit & PR task client methods"
```

---

### Task 4: Mock Data for New Tools

**Files:**
- Modify: `tests/fixtures/bitbucket_mocks.py`

- [ ] **Step 1: Add mock data constants**

Add to `tests/fixtures/bitbucket_mocks.py`:

```python
MOCK_BB_PR_COMMENT = {
    "id": 10,
    "text": "LGTM",
    "author": {"displayName": "John Doe"},
    "createdDate": 1710000000000,
}

MOCK_BB_PR_CHANGES = [
    {"path": {"toString": "src/main.py"}, "type": "MODIFY"},
    {"path": {"toString": "tests/test_main.py"}, "type": "ADD"},
]

MOCK_BB_DIFF = [
    {"source": {"toString": "src/main.py"}, "destination": {"toString": "src/main.py"},
     "hunks": [{"segments": [{"type": "REMOVED", "lines": [{"line": "old"}]},
                             {"type": "ADDED", "lines": [{"line": "new"}]}]}]}
]

MOCK_BB_FILE_LIST = ["src/main.py", "README.md", "setup.py"]

MOCK_BB_TAGS = [
    {"displayId": "v1.0.0", "latestCommit": "abc123def456", "type": "TAG"},
    {"displayId": "v0.9.0", "latestCommit": "789abc012def", "type": "TAG"},
]

MOCK_BB_PR_TASKS = [
    {"id": 1, "text": "Fix failing tests", "state": "OPEN"},
    {"id": 2, "text": "Update docs", "state": "RESOLVED"},
]
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/bitbucket_mocks.py
git commit -m "test(bitbucket): add mock data for extended tools"
```

---

### Task 5: PR Review & Lifecycle MCP Tools (server layer)

**Files:**
- Modify: `src/mcp_atlassian/servers/bitbucket.py`
- Modify: `tests/unit/servers/test_bitbucket_server.py`

- [ ] **Step 1: Write failing server tests**

Add imports to `tests/unit/servers/test_bitbucket_server.py`:

```python
from tests.fixtures.bitbucket_mocks import (
    MOCK_BB_BRANCHES,
    MOCK_BB_COMMITS,
    MOCK_BB_PROJECTS,
    MOCK_BB_PR_CHANGES,
    MOCK_BB_PR_COMMENT,
    MOCK_BB_PULL_REQUESTS,
    MOCK_BB_REPOS,
)
```

Add mock responses to `mock_bitbucket_fetcher` fixture:

```python
    mock.add_pr_comment.return_value = MOCK_BB_PR_COMMENT
    mock.merge_pull_request.return_value = {"id": 1, "state": "MERGED"}
    mock.decline_pull_request.return_value = {"id": 1, "state": "DECLINED"}
    mock.approve_pull_request.return_value = {"status": "APPROVED"}
    mock.get_pr_changes.return_value = MOCK_BB_PR_CHANGES
```

Add new tool imports in `test_bitbucket_mcp_instance` fixture:

```python
    from src.mcp_atlassian.servers.bitbucket import (
        add_pr_comment,
        approve_pull_request,
        create_pull_request,
        decline_pull_request,
        get_branches,
        get_commits,
        get_file_content,
        get_pr_changes,
        get_projects,
        get_pull_request,
        get_pull_requests,
        get_repos,
        merge_pull_request,
    )
    # ... register all new tools with test_mcp.tool()(fn)
```

Add tests:

```python
@pytest.mark.anyio
async def test_add_pr_comment(bitbucket_client, mock_bitbucket_fetcher):
    """Test add_pr_comment tool adds a comment to a PR."""
    response = await bitbucket_client.call_tool(
        "add_pr_comment",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "text": "LGTM"},
    )
    content = json.loads(response[0].text)
    assert content["id"] == 10
    mock_bitbucket_fetcher.add_pr_comment.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo", pr_id=1, text="LGTM", parent_id=None
    )


@pytest.mark.anyio
async def test_merge_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test merge_pull_request tool merges a PR."""
    response = await bitbucket_client.call_tool(
        "merge_pull_request",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "pr_id": 1,
            "merge_message": "Merging",
        },
    )
    content = json.loads(response[0].text)
    assert content["state"] == "MERGED"


@pytest.mark.anyio
async def test_decline_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test decline_pull_request tool declines a PR."""
    response = await bitbucket_client.call_tool(
        "decline_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert content["state"] == "DECLINED"


@pytest.mark.anyio
async def test_approve_pull_request(bitbucket_client, mock_bitbucket_fetcher):
    """Test approve_pull_request tool approves a PR."""
    response = await bitbucket_client.call_tool(
        "approve_pull_request",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1, "user_slug": "jdoe"},
    )
    content = json.loads(response[0].text)
    assert content["status"] == "APPROVED"


@pytest.mark.anyio
async def test_get_pr_changes(bitbucket_client, mock_bitbucket_fetcher):
    """Test get_pr_changes tool returns files changed in a PR as a list."""
    response = await bitbucket_client.call_tool(
        "get_pr_changes",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["path"]["toString"] == "src/main.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/servers/test_bitbucket_server.py -v -k "test_add_pr_comment or test_merge_pull_request or test_decline_pull_request or test_approve_pull_request or test_get_pr_changes"`
Expected: FAIL

- [ ] **Step 3: Add MCP tool definitions**

Add to `src/mcp_atlassian/servers/bitbucket.py` after `get_file_content`:

```python
# --- PR Review & Lifecycle Tools ---


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def add_pr_comment(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    text: Annotated[str, Field(description="Comment text (Markdown supported)")],
    parent_id: Annotated[
        int | None,
        Field(description="Parent comment ID for threaded replies", default=None),
    ] = None,
) -> str:
    """Add a comment to a pull request. Use parent_id to reply to an existing comment."""
    bb = await get_bitbucket_fetcher(ctx)
    comment = bb.add_pr_comment(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id,
        text=text, parent_id=parent_id,
    )
    return json.dumps(comment, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def merge_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    merge_message: Annotated[str, Field(description="Merge commit message")],
    close_source_branch: Annotated[
        bool, Field(description="Delete source branch after merge", default=False)
    ] = False,
    merge_strategy: Annotated[
        str,
        Field(
            description="Merge strategy: merge_commit, squash, or fast_forward",
            default="merge_commit",
        ),
    ] = "merge_commit",
    pr_version: Annotated[
        int | None,
        Field(
            description="PR version number (from PR details 'version' field) to prevent merging stale PR. Optional.",
            default=None,
        ),
    ] = None,
) -> str:
    """Merge a pull request with the specified strategy."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.merge_pull_request(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id,
        merge_message=merge_message, close_source_branch=close_source_branch,
        merge_strategy=merge_strategy, pr_version=pr_version,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def decline_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    pr_version: Annotated[
        int,
        Field(
            description="PR version number (from PR details 'version' field) to prevent stale updates",
            default=0,
        ),
    ] = 0,
) -> str:
    """Decline/reject a pull request."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.decline_pull_request(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id, pr_version=pr_version
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def approve_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    user_slug: Annotated[str, Field(description="Username/slug of the approving user")],
) -> str:
    """Approve a pull request as a specific user."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.approve_pull_request(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id, user_slug=user_slug
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pr_changes(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
) -> str:
    """Get list of files changed in a pull request with change types (ADD, MODIFY, DELETE)."""
    bb = await get_bitbucket_fetcher(ctx)
    changes = bb.get_pr_changes(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id
    )
    return json.dumps(changes, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/servers/test_bitbucket_server.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/servers/bitbucket.py tests/unit/servers/test_bitbucket_server.py
git commit -m "feat(bitbucket): add PR review & lifecycle MCP tools"
```

---

### Task 6: Code Browsing MCP Tools (server layer)

**Files:**
- Modify: `src/mcp_atlassian/servers/bitbucket.py`
- Modify: `tests/unit/servers/test_bitbucket_server.py`

- [ ] **Step 1: Write failing server tests**

Add mock responses to `mock_bitbucket_fetcher` fixture:

```python
    mock.get_diff.return_value = MOCK_BB_DIFF
    mock.get_file_list.return_value = MOCK_BB_FILE_LIST
```

Add imports for `MOCK_BB_DIFF`, `MOCK_BB_FILE_LIST`.

Add tests:

```python
@pytest.mark.anyio
async def test_get_diff(bitbucket_client, mock_bitbucket_fetcher):
    """Test get_diff tool returns diff segments as JSON."""
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
    assert content[0]["source"]["toString"] == "src/main.py"
    mock_bitbucket_fetcher.get_diff.assert_called_once_with(
        project_key="PROJ", repo_slug="my-repo",
        path="src/main.py", hash_oldest="abc123", hash_newest="def456"
    )


@pytest.mark.anyio
async def test_get_file_list(bitbucket_client, mock_bitbucket_fetcher):
    """Test get_file_list tool returns list of file path strings."""
    response = await bitbucket_client.call_tool(
        "get_file_list",
        {"project_key": "PROJ", "repo_slug": "my-repo"},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert len(content) == 3
    assert content[0] == "src/main.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/servers/test_bitbucket_server.py -v -k "test_get_diff or test_get_file_list"`
Expected: FAIL

- [ ] **Step 3: Add MCP tool definitions**

Add to `src/mcp_atlassian/servers/bitbucket.py`:

```python
# --- Code Browsing Tools ---


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_diff(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    path: Annotated[str, Field(description="File path to get diff for (e.g. 'src/main.py')")],
    hash_oldest: Annotated[str, Field(description="Older commit hash or branch name")],
    hash_newest: Annotated[str, Field(description="Newer commit hash or branch name")],
) -> str:
    """Get the diff of a file between two commits or branches. Returns diff segments with hunks."""
    bb = await get_bitbucket_fetcher(ctx)
    diff = bb.get_diff(
        project_key=project_key, repo_slug=repo_slug,
        path=path, hash_oldest=hash_oldest, hash_newest=hash_newest,
    )
    return json.dumps(diff, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_file_list(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    sub_folder: Annotated[
        str | None,
        Field(description="Sub-folder path to list (e.g. 'src/main'). Lists root if omitted.", default=None),
    ] = None,
    ref: Annotated[
        str | None,
        Field(description="Branch name, tag, or commit hash to list files at. Defaults to default branch.", default=None),
    ] = None,
) -> str:
    """List file paths in a repository directory at a specific branch or commit."""
    bb = await get_bitbucket_fetcher(ctx)
    files = bb.get_file_list(
        project_key=project_key, repo_slug=repo_slug,
        sub_folder=sub_folder, ref=ref,
    )
    return json.dumps(files, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/servers/test_bitbucket_server.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/servers/bitbucket.py tests/unit/servers/test_bitbucket_server.py
git commit -m "feat(bitbucket): add code browsing MCP tools (diff, file list)"
```

---

### Task 7: Branch, Tag, File & Task MCP Tools (server layer)

**Files:**
- Modify: `src/mcp_atlassian/servers/bitbucket.py`
- Modify: `tests/unit/servers/test_bitbucket_server.py`

- [ ] **Step 1: Write failing server tests**

Add mock responses to `mock_bitbucket_fetcher` fixture:

```python
    mock.create_branch.return_value = {"displayId": "feature/new", "type": "BRANCH"}
    mock.delete_branch.return_value = None
    mock.get_tags.return_value = MOCK_BB_TAGS
    mock.create_tag.return_value = {"displayId": "v2.0.0", "latestCommit": "def456"}
    mock.update_file.return_value = {"id": "new_commit_hash"}
    mock.get_pr_tasks.return_value = MOCK_BB_PR_TASKS
```

Add imports for `MOCK_BB_TAGS`, `MOCK_BB_PR_TASKS`.

Add tests:

```python
@pytest.mark.anyio
async def test_create_branch(bitbucket_client, mock_bitbucket_fetcher):
    """Test create_branch tool creates a new branch."""
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
    assert content["displayId"] == "feature/new"


@pytest.mark.anyio
async def test_delete_branch(bitbucket_client, mock_bitbucket_fetcher):
    """Test delete_branch tool deletes a branch."""
    response = await bitbucket_client.call_tool(
        "delete_branch",
        {"project_key": "PROJ", "repo_slug": "my-repo", "name": "feature/old"},
    )
    content = json.loads(response[0].text)
    assert content["success"] is True


@pytest.mark.anyio
async def test_get_tags(bitbucket_client, mock_bitbucket_fetcher):
    """Test get_tags tool returns tags list."""
    response = await bitbucket_client.call_tool(
        "get_tags",
        {"project_key": "PROJ", "repo_slug": "my-repo", "limit": 25},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["displayId"] == "v1.0.0"


@pytest.mark.anyio
async def test_create_tag(bitbucket_client, mock_bitbucket_fetcher):
    """Test create_tag tool creates a tag at a commit."""
    response = await bitbucket_client.call_tool(
        "create_tag",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "tag_name": "v2.0.0",
            "commit_id": "def456",
            "description": "Release v2",
        },
    )
    content = json.loads(response[0].text)
    assert content["displayId"] == "v2.0.0"


@pytest.mark.anyio
async def test_update_file(bitbucket_client, mock_bitbucket_fetcher):
    """Test update_file tool edits a file and commits."""
    response = await bitbucket_client.call_tool(
        "update_file",
        {
            "project_key": "PROJ",
            "repo_slug": "my-repo",
            "file_path": "README.md",
            "content": "# Updated",
            "commit_message": "Update readme",
            "branch": "main",
            "source_commit_id": "abc123",
        },
    )
    content = json.loads(response[0].text)
    assert content["id"] == "new_commit_hash"


@pytest.mark.anyio
async def test_get_pr_tasks(bitbucket_client, mock_bitbucket_fetcher):
    """Test get_pr_tasks tool returns PR checklist tasks."""
    response = await bitbucket_client.call_tool(
        "get_pr_tasks",
        {"project_key": "PROJ", "repo_slug": "my-repo", "pr_id": 1},
    )
    content = json.loads(response[0].text)
    assert isinstance(content, list)
    assert content[0]["text"] == "Fix failing tests"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/servers/test_bitbucket_server.py -v -k "test_create_branch or test_delete_branch or test_get_tags or test_create_tag or test_update_file or test_get_pr_tasks"`
Expected: FAIL

- [ ] **Step 3: Add MCP tool definitions**

Add to `src/mcp_atlassian/servers/bitbucket.py`:

```python
# --- Branch & Tag Management Tools ---


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def create_branch(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    name: Annotated[str, Field(description="New branch name (e.g. 'feature/my-feature')")],
    start_point: Annotated[
        str, Field(description="Branch name or commit hash to branch from (e.g. 'main')")
    ],
) -> str:
    """Create a new branch from an existing branch or commit."""
    bb = await get_bitbucket_fetcher(ctx)
    branch = bb.create_branch(
        project_key=project_key, repo_slug=repo_slug,
        name=name, start_point=start_point,
    )
    return json.dumps(branch, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def delete_branch(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    name: Annotated[str, Field(description="Branch name to delete (e.g. 'feature/old-feature')")],
) -> str:
    """Delete a branch from a repository."""
    bb = await get_bitbucket_fetcher(ctx)
    bb.delete_branch(project_key=project_key, repo_slug=repo_slug, name=name)
    return json.dumps({"success": True, "message": f"Branch '{name}' deleted"})


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_tags(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    limit: Annotated[
        int,
        Field(description="Maximum number of tags to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
) -> str:
    """List tags in a repository, ordered by most recent."""
    bb = await get_bitbucket_fetcher(ctx)
    tags = bb.get_tags(project_key=project_key, repo_slug=repo_slug, limit=limit)
    return json.dumps(tags, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def create_tag(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    tag_name: Annotated[str, Field(description="Tag name (e.g. 'v1.0.0')")],
    commit_id: Annotated[str, Field(description="Full commit hash to tag")],
    description: Annotated[
        str | None,
        Field(description="Tag annotation message", default=None),
    ] = None,
) -> str:
    """Create an annotated tag at a specific commit."""
    bb = await get_bitbucket_fetcher(ctx)
    tag = bb.create_tag(
        project_key=project_key, repo_slug=repo_slug,
        tag_name=tag_name, commit_id=commit_id, description=description,
    )
    return json.dumps(tag, indent=2, ensure_ascii=False)


# --- File Editing Tools ---


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def update_file(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    file_path: Annotated[str, Field(description="Path to the file to edit (e.g. 'src/main.py')")],
    content: Annotated[str, Field(description="New file content (replaces entire file)")],
    commit_message: Annotated[str, Field(description="Commit message for the change")],
    branch: Annotated[str, Field(description="Branch to commit to (e.g. 'main')")],
    source_commit_id: Annotated[
        str,
        Field(description="Current HEAD commit hash of the branch (prevents conflicting updates)"),
    ],
) -> str:
    """Edit a file in-place and commit the change. Get source_commit_id from get_commits."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.update_file(
        project_key=project_key, repo_slug=repo_slug,
        file_path=file_path, content=content,
        commit_message=commit_message, branch=branch,
        source_commit_id=source_commit_id,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


# --- PR Task Tools ---


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pr_tasks(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
) -> str:
    """Get checklist tasks on a pull request (OPEN or RESOLVED)."""
    bb = await get_bitbucket_fetcher(ctx)
    tasks = bb.get_pr_tasks(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id
    )
    return json.dumps(tasks, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Update test fixture to register all new tools**

Update `test_bitbucket_mcp_instance` to import and register all 22 tools.

- [ ] **Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/unit/servers/test_bitbucket_server.py tests/unit/bitbucket/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_atlassian/servers/bitbucket.py tests/unit/servers/test_bitbucket_server.py tests/fixtures/bitbucket_mocks.py
git commit -m "feat(bitbucket): add branch, tag, file edit & task MCP tools"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/unit/bitbucket/ tests/unit/servers/test_bitbucket_server.py tests/unit/servers/test_dependencies.py tests/unit/utils/test_environment.py -v`
Expected: All PASS

- [ ] **Step 2: Verify tool count**

Run: `uv run python -c "from mcp_atlassian.servers.bitbucket import bitbucket_mcp; import asyncio; tools = asyncio.run(bitbucket_mcp.get_tools()); print(f'{len(tools)} tools: {sorted(tools.keys())}')"`
Expected: 22 tools listed

- [ ] **Step 3: Run linting**

Run: `uv run ruff check src/mcp_atlassian/bitbucket/ src/mcp_atlassian/servers/bitbucket.py`
Expected: No errors

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -u
git commit -m "fix(bitbucket): address linting issues in extended tools"
```
