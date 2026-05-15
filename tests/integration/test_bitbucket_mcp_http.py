"""End-to-end MCP-over-HTTP tests for the Bitbucket tools.

Targets a *running* MCP server (the DEV container or any deployment) over the
JSON-RPC streamable-http transport, exercising the full path:

    JSON-RPC client → FastMCP dispatcher → @check_write_access decorators
                   → BitbucketFetcher → Bitbucket REST API

This complements `test_bitbucket_real_api.py`, which imports BitbucketFetcher
directly and skips the entire MCP serialization layer. Bugs that only surface
through serialization (bytes that can't be JSON-encoded, schema validation,
missing tool registration) only show up here.

Skipped by default. Enable with:

    uv run pytest tests/integration/test_bitbucket_mcp_http.py \
        --integration --use-real-data -v

Required environment:
    MCP_HTTP_URL             base URL of the MCP server, default http://localhost:9998
    BITBUCKET_TEST_PROJECT_KEY  optional, defaults to "TEST"
    BITBUCKET_TEST_REPO_SLUG    optional, defaults to "test"
    BITBUCKET_TEST_USER_SLUG    optional, defaults to "matjazz"
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any

import pytest
import requests


# --------------------------------------------------------------------------
# Minimal JSON-RPC over streamable-http client
# --------------------------------------------------------------------------


class McpHttpClient:
    """Tiny JSON-RPC client for FastMCP's streamable-http transport.

    Handshake is `initialize` → `notifications/initialized`. Tool calls are
    `tools/call`, returning SSE-framed JSON the server emits as a single
    `event: message\\ndata: <json>` chunk.
    """

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.url = base_url.rstrip("/") + "/mcp/"
        self.timeout = timeout
        self.session_id: str | None = None
        self._rpc_id = 0

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _post(self, payload: dict[str, Any], *, expect_response: bool) -> requests.Response:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return requests.post(
            self.url, json=payload, headers=headers, timeout=self.timeout
        )

    @staticmethod
    def _parse_sse(text: str) -> dict[str, Any]:
        # FastMCP wraps a single JSON-RPC response in one SSE chunk:
        #   event: message\r\ndata: {...}\r\n\r\n
        m = re.search(r"^data: (.+)$", text, re.MULTILINE)
        if not m:
            raise AssertionError(f"No SSE 'data:' line in response: {text!r}")
        return json.loads(m.group(1))

    def initialize(self) -> None:
        r = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-http-integration", "version": "1.0"},
                },
            },
            expect_response=True,
        )
        r.raise_for_status()
        self.session_id = r.headers.get("mcp-session-id")
        assert self.session_id, "Server did not return a session id"
        # MCP spec requires the initialized notification before further calls.
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            expect_response=False,
        )

    def list_tool_names(self) -> set[str]:
        r = self._post(
            {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list"},
            expect_response=True,
        )
        r.raise_for_status()
        obj = self._parse_sse(r.text)
        return {t["name"] for t in obj["result"]["tools"]}

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool. Returns the parsed payload, or raises if isError."""
        r = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            expect_response=True,
        )
        r.raise_for_status()
        obj = self._parse_sse(r.text)
        result = obj.get("result", {})
        if result.get("isError"):
            text = result["content"][0]["text"] if result.get("content") else "<no content>"
            raise McpToolError(f"{name}: {text}")
        # Tools return either a single text-content entry containing JSON, or
        # a single text-content entry containing the raw string (file content).
        if not result.get("content"):
            return None
        text = result["content"][0]["text"]
        # Tools that emit raw strings (get_file_content, get_pr_diff) return
        # text as-is; otherwise the text is JSON the tool serialized with
        # json.dumps. Try JSON first, fall back to raw text.
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text


class McpToolError(RuntimeError):
    """Raised when a tool returns isError=True."""


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.mark.integration
class TestBitbucketMcpHttp:
    """End-to-end tests of every Bitbucket MCP tool over JSON-RPC HTTP."""

    @pytest.fixture(autouse=True)
    def _gate(self, request):
        if not request.config.getoption("--use-real-data", default=False):
            pytest.skip("Live MCP tests require --use-real-data")

    @pytest.fixture(scope="class")
    def mcp_url(self) -> str:
        return os.getenv("MCP_HTTP_URL", "http://localhost:9998")

    @pytest.fixture(scope="class")
    def project_key(self) -> str:
        return os.getenv("BITBUCKET_TEST_PROJECT_KEY", "TEST")

    @pytest.fixture(scope="class")
    def repo_slug(self) -> str:
        return os.getenv("BITBUCKET_TEST_REPO_SLUG", "test")

    @pytest.fixture(scope="class")
    def user_slug(self) -> str:
        return os.getenv("BITBUCKET_TEST_USER_SLUG", "matjazz")

    @pytest.fixture(scope="class")
    def run_id(self) -> str:
        return f"{int(time.time())}-{uuid.uuid4().hex[:6]}"

    @pytest.fixture(scope="class")
    def mcp(self, mcp_url) -> McpHttpClient:
        client = McpHttpClient(mcp_url)
        try:
            client.initialize()
        except requests.RequestException as e:
            pytest.skip(f"MCP server at {mcp_url} unreachable: {e!r}")
        return client

    @pytest.fixture(scope="class")
    def default_branch_head(self, mcp, project_key, repo_slug) -> tuple[str, str]:
        branches = mcp.call_tool(
            "bitbucket_get_branches",
            {"project_key": project_key, "repo_slug": repo_slug, "limit": 50},
        )
        default = next((b for b in branches if b.get("isDefault")), branches[0])
        return default["displayId"], default["latestCommit"]

    # ----------------------------------------------------------------------
    # Registration sanity
    # ----------------------------------------------------------------------

    def test_all_36_bitbucket_tools_registered(self, mcp):
        names = mcp.list_tool_names()
        expected = {
            # read
            "bitbucket_get_projects", "bitbucket_get_repo", "bitbucket_get_repos",
            "bitbucket_get_pull_requests", "bitbucket_get_pull_request",
            "bitbucket_get_commits", "bitbucket_get_branches",
            "bitbucket_get_file_content", "bitbucket_get_pr_comments",
            "bitbucket_get_pr_changes", "bitbucket_get_pr_diff",
            "bitbucket_get_diff", "bitbucket_get_file_list",
            "bitbucket_get_commit", "bitbucket_search_code",
            "bitbucket_get_tags", "bitbucket_get_pr_tasks",
            # write
            "bitbucket_create_pull_request", "bitbucket_add_pr_comment",
            "bitbucket_update_pr_comment", "bitbucket_delete_pr_comment",
            "bitbucket_merge_pull_request", "bitbucket_decline_pull_request",
            "bitbucket_approve_pull_request", "bitbucket_reopen_pull_request",
            "bitbucket_unapprove_pull_request", "bitbucket_add_pr_reviewer",
            "bitbucket_delete_pull_request", "bitbucket_update_pull_request",
            "bitbucket_create_branch", "bitbucket_delete_branch",
            "bitbucket_create_tag", "bitbucket_delete_tag",
            "bitbucket_update_file", "bitbucket_add_pr_task",
            "bitbucket_update_pr_task",
        }
        missing = expected - names
        assert not missing, f"Tools missing from MCP server: {missing}"

    # ----------------------------------------------------------------------
    # Read tools that serialize their return through MCP (the layer where
    # bytes-vs-str bugs surface)
    # ----------------------------------------------------------------------

    def test_get_file_content_returns_string_through_mcp(
        self, mcp, project_key, repo_slug
    ):
        """If get_file_content returned bytes, MCP could not JSON-encode it."""
        files = mcp.call_tool(
            "bitbucket_get_file_list",
            {"project_key": project_key, "repo_slug": repo_slug},
        )
        first = files[0]
        content = mcp.call_tool(
            "bitbucket_get_file_content",
            {"project_key": project_key, "repo_slug": repo_slug, "file_path": first},
        )
        assert isinstance(content, str)

    def test_get_pr_diff_through_mcp_does_not_crash_on_bytes(
        self, mcp, project_key, repo_slug
    ):
        """Regression: get_pr_diff used to return bytes that MCP couldn't serialize.

        Bitbucket Server's /diff endpoint returns a structured JSON document
        (with `fromHash`, `toHash`, `diffs`); the tool returns the JSON-as-text
        body. The MCP client here auto-parses it back to a dict — what we
        care about for the bytes regression is that the call succeeds and
        the payload has the diff shape.
        """
        prs = mcp.call_tool(
            "bitbucket_get_pull_requests",
            {"project_key": project_key, "repo_slug": repo_slug, "state": "ALL", "limit": 1},
        )
        if not prs:
            pytest.skip("no PRs exist in test repo")
        pr_id = prs[0]["id"]
        diff = mcp.call_tool(
            "bitbucket_get_pr_diff",
            {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
        )
        # Whether MCP delivers the raw JSON string (which our helper parses)
        # or some future change moves to a different shape, both `str` and
        # `dict` are acceptable; `bytes` was the bug.
        assert isinstance(diff, (str, dict))
        if isinstance(diff, dict):
            assert "fromHash" in diff and "toHash" in diff

    def test_get_pr_comments_uses_activities_endpoint(
        self, mcp, project_key, repo_slug
    ):
        """Regression: the old /comments path crashed without `path` param."""
        prs = mcp.call_tool(
            "bitbucket_get_pull_requests",
            {"project_key": project_key, "repo_slug": repo_slug, "state": "ALL", "limit": 1},
        )
        if not prs:
            pytest.skip("no PRs exist in test repo")
        pr_id = prs[0]["id"]
        comments = mcp.call_tool(
            "bitbucket_get_pr_comments",
            {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
        )
        assert isinstance(comments, list)

    def test_search_code_uses_post(self, mcp, project_key, repo_slug):
        """Regression: prior GET form returned 405 from Bitbucket Server."""
        try:
            result = mcp.call_tool(
                "bitbucket_search_code",
                {"project_key": project_key, "repo_slug": repo_slug, "query": "test", "limit": 5},
            )
        except McpToolError as e:
            pytest.skip(f"code search service not enabled: {e}")
        assert isinstance(result, list)

    def test_baseline_read_tools_all_succeed(
        self, mcp, project_key, repo_slug, default_branch_head
    ):
        """One call per remaining read tool to confirm registration + dispatch."""
        _, head = default_branch_head
        files = mcp.call_tool(
            "bitbucket_get_file_list",
            {"project_key": project_key, "repo_slug": repo_slug},
        )
        first = files[0]
        cases: list[tuple[str, dict[str, Any]]] = [
            ("bitbucket_get_projects", {"limit": 5}),
            ("bitbucket_get_repo", {"project_key": project_key, "repo_slug": repo_slug}),
            ("bitbucket_get_repos", {"project_key": project_key, "limit": 5}),
            ("bitbucket_get_branches", {"project_key": project_key, "repo_slug": repo_slug, "limit": 5}),
            ("bitbucket_get_tags", {"project_key": project_key, "repo_slug": repo_slug, "limit": 5}),
            ("bitbucket_get_commits", {"project_key": project_key, "repo_slug": repo_slug, "limit": 5}),
            ("bitbucket_get_commit", {"project_key": project_key, "repo_slug": repo_slug, "commit_id": head}),
            ("bitbucket_get_diff", {
                "project_key": project_key, "repo_slug": repo_slug,
                "path": first, "hash_oldest": head, "hash_newest": head,
            }),
            ("bitbucket_get_pull_requests", {"project_key": project_key, "repo_slug": repo_slug, "state": "ALL", "limit": 5}),
        ]
        for name, args in cases:
            result = mcp.call_tool(name, args)
            # All read tools return JSON (list or dict) — no string-payload
            # tools (those have dedicated tests above).
            assert result is not None, f"{name} returned None"

    # ----------------------------------------------------------------------
    # Write-tool lifecycles: each test creates unique resources and cleans up.
    # ----------------------------------------------------------------------

    def _open_temp_pr(
        self,
        mcp: McpHttpClient,
        project_key: str,
        repo_slug: str,
        run_id: str,
        head: str,
        label: str,
    ) -> tuple[dict[str, Any], str]:
        branch = f"mcp-http-{label}-{run_id}"
        mcp.call_tool(
            "bitbucket_create_branch",
            {
                "project_key": project_key, "repo_slug": repo_slug,
                "name": branch, "start_point": head,
            },
        )
        mcp.call_tool(
            "bitbucket_update_file",
            {
                "project_key": project_key, "repo_slug": repo_slug,
                "file_path": f"mcp-http-{label}-{run_id}.txt",
                "content": f"mcp-http {label} {run_id}\n",
                "commit_message": f"mcp-http: add {label} file",
                "branch": branch,
                "source_commit_id": "",
            },
        )
        pr = mcp.call_tool(
            "bitbucket_create_pull_request",
            {
                "project_key": project_key, "repo_slug": repo_slug,
                "title": f"mcp-http PR {label} {run_id}",
                "description": f"MCP HTTP test PR ({label}).",
                "from_branch": branch, "to_branch": "master",
            },
        )
        return pr, branch

    def _close_temp_pr(self, mcp, project_key, repo_slug, pr_id, branch):
        try:
            current = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            if current.get("state") == "OPEN":
                try:
                    mcp.call_tool(
                        "bitbucket_decline_pull_request",
                        {
                            "project_key": project_key, "repo_slug": repo_slug,
                            "pr_id": pr_id, "pr_version": current.get("version", 0),
                        },
                    )
                except McpToolError:
                    pass
            current = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            try:
                mcp.call_tool(
                    "bitbucket_delete_pull_request",
                    {
                        "project_key": project_key, "repo_slug": repo_slug,
                        "pr_id": pr_id, "pr_version": current.get("version", 0),
                    },
                )
            except McpToolError:
                pass
        except McpToolError:
            pass
        try:
            mcp.call_tool(
                "bitbucket_delete_branch",
                {"project_key": project_key, "repo_slug": repo_slug, "name": branch},
            )
        except McpToolError:
            pass

    def test_branch_and_tag_lifecycle(
        self, mcp, project_key, repo_slug, run_id, default_branch_head
    ):
        _, head = default_branch_head
        branch = f"mcp-http-branch-{run_id}"
        tag = f"mcp-http-tag-{run_id}"
        try:
            created = mcp.call_tool(
                "bitbucket_create_branch",
                {
                    "project_key": project_key, "repo_slug": repo_slug,
                    "name": branch, "start_point": head,
                },
            )
            assert created["displayId"] == branch

            mcp.call_tool(
                "bitbucket_create_tag",
                {
                    "project_key": project_key, "repo_slug": repo_slug,
                    "tag_name": tag, "commit_id": head,
                    "description": "mcp-http test tag",
                },
            )
            tags = mcp.call_tool(
                "bitbucket_get_tags",
                {"project_key": project_key, "repo_slug": repo_slug, "limit": 50},
            )
            assert any(t.get("displayId") == tag for t in tags)
        finally:
            try:
                mcp.call_tool(
                    "bitbucket_delete_branch",
                    {"project_key": project_key, "repo_slug": repo_slug, "name": branch},
                )
            except McpToolError:
                pass
            try:
                mcp.call_tool(
                    "bitbucket_delete_tag",
                    {"project_key": project_key, "repo_slug": repo_slug, "tag_name": tag},
                )
            except McpToolError:
                pass

    def test_pr_full_lifecycle(
        self, mcp, project_key, repo_slug, run_id, user_slug, default_branch_head
    ):
        """Covers create / get / update / pr_changes / add_reviewer /
        approve / unapprove / decline / reopen / delete."""
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(mcp, project_key, repo_slug, run_id, head, "lifecycle")
        pr_id = pr["id"]
        try:
            fetched = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            assert fetched["id"] == pr_id
            assert fetched["state"] == "OPEN"

            updated = mcp.call_tool(
                "bitbucket_update_pull_request",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "title": f"mcp-http PR lifecycle {run_id} (updated)",
                    "description": "updated via MCP HTTP",
                    "pr_version": fetched["version"],
                },
            )
            assert "updated" in updated["title"]

            mcp.call_tool(
                "bitbucket_get_pr_changes",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )

            try:
                mcp.call_tool(
                    "bitbucket_add_pr_reviewer",
                    {
                        "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                        "reviewer_slug": user_slug,
                    },
                )
                # approve+unapprove may be forbidden for the author by server
                # policy — wrap individually to keep coverage of decline/reopen.
                for op_name in ("approve_pull_request", "unapprove_pull_request"):
                    try:
                        mcp.call_tool(
                            f"bitbucket_{op_name}",
                            {
                                "project_key": project_key, "repo_slug": repo_slug,
                                "pr_id": pr_id, "user_slug": user_slug,
                            },
                        )
                    except McpToolError as e:
                        print(f"  [info] {op_name} rejected by server: {e}")
            except McpToolError as e:
                pytest.fail(f"add_pr_reviewer failed unexpectedly: {e}")

            current = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            mcp.call_tool(
                "bitbucket_decline_pull_request",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "pr_version": current["version"],
                },
            )
            after_decline = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            assert after_decline["state"] == "DECLINED"

            mcp.call_tool(
                "bitbucket_reopen_pull_request",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "pr_version": after_decline["version"],
                },
            )
            after_reopen = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            assert after_reopen["state"] == "OPEN"
        finally:
            self._close_temp_pr(mcp, project_key, repo_slug, pr_id, branch)

    def test_pr_merge_lifecycle(
        self, mcp, project_key, repo_slug, run_id, default_branch_head
    ):
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(mcp, project_key, repo_slug, run_id, head, "merge")
        pr_id = pr["id"]
        try:
            current = mcp.call_tool(
                "bitbucket_get_pull_request",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            try:
                merged = mcp.call_tool(
                    "bitbucket_merge_pull_request",
                    {
                        "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                        "merge_message": f"mcp-http merge {run_id}",
                        "pr_version": current["version"],
                    },
                )
            except McpToolError as e:
                pytest.skip(f"server policy blocked merge: {e}")
            assert merged.get("state") == "MERGED" or merged.get("merged") is True
        finally:
            self._close_temp_pr(mcp, project_key, repo_slug, pr_id, branch)

    def test_pr_comment_lifecycle(
        self, mcp, project_key, repo_slug, run_id, default_branch_head
    ):
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(mcp, project_key, repo_slug, run_id, head, "comment")
        pr_id = pr["id"]
        try:
            created = mcp.call_tool(
                "bitbucket_add_pr_comment",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "text": f"mcp-http top-level {run_id}",
                },
            )
            top_id = created["id"]

            reply = mcp.call_tool(
                "bitbucket_add_pr_comment",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "text": f"mcp-http reply {run_id}",
                    "parent_id": top_id,
                },
            )

            comments = mcp.call_tool(
                "bitbucket_get_pr_comments",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            top = next(c for c in comments if c["id"] == top_id)
            assert any(r["id"] == reply["id"] for r in top.get("comments", [])), (
                "reply not threaded under parent comment in MCP response"
            )

            mcp.call_tool(
                "bitbucket_update_pr_comment",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "comment_id": top_id,
                    "text": f"mcp-http top-level {run_id} (edited)",
                    "comment_version": created["version"],
                },
            )

            # Re-fetch versions before delete (each update bumps version).
            comments = mcp.call_tool(
                "bitbucket_get_pr_comments",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            top = next(c for c in comments if c["id"] == top_id)
            reply_now = next(r for r in top["comments"] if r["id"] == reply["id"])

            mcp.call_tool(
                "bitbucket_delete_pr_comment",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "comment_id": reply["id"],
                    "comment_version": reply_now["version"],
                },
            )
            top_now = next(
                c
                for c in mcp.call_tool(
                    "bitbucket_get_pr_comments",
                    {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
                )
                if c["id"] == top_id
            )
            mcp.call_tool(
                "bitbucket_delete_pr_comment",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "comment_id": top_id,
                    "comment_version": top_now["version"],
                },
            )
        finally:
            self._close_temp_pr(mcp, project_key, repo_slug, pr_id, branch)

    def test_pr_task_lifecycle_blocker_comments(
        self, mcp, project_key, repo_slug, run_id, default_branch_head
    ):
        """Regression: tasks migrated to /blocker-comments in Bitbucket 7.2+."""
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(mcp, project_key, repo_slug, run_id, head, "task")
        pr_id = pr["id"]
        try:
            task = mcp.call_tool(
                "bitbucket_add_pr_task",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "text": f"mcp-http task {run_id}",
                },
            )
            assert task.get("severity") == "BLOCKER"
            assert task.get("state") == "OPEN"
            task_id = task["id"]

            tasks = mcp.call_tool(
                "bitbucket_get_pr_tasks",
                {"project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id},
            )
            assert any(t["id"] == task_id for t in tasks)
            assert all(t.get("severity") == "BLOCKER" for t in tasks)

            resolved = mcp.call_tool(
                "bitbucket_update_pr_task",
                {
                    "project_key": project_key, "repo_slug": repo_slug, "pr_id": pr_id,
                    "task_id": task_id, "state": "RESOLVED",
                    "task_version": task["version"],
                },
            )
            assert resolved["state"] == "RESOLVED"
        finally:
            self._close_temp_pr(mcp, project_key, repo_slug, pr_id, branch)
