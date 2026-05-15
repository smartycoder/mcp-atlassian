"""Integration tests for Bitbucket tools against a real Bitbucket Server.

Skipped by default. Enable with:

    uv run pytest tests/integration/test_bitbucket_real_api.py \
        --integration --use-real-data -v

Required environment:
    BITBUCKET_URL              base URL of the Bitbucket Server
    BITBUCKET_PERSONAL_TOKEN   PAT for the test user
    BITBUCKET_TEST_PROJECT_KEY optional, defaults to "TEST"
    BITBUCKET_TEST_REPO_SLUG   optional, defaults to "test"
    BITBUCKET_TEST_USER_SLUG   optional, defaults to "matjazz"
                               (used for self-add_reviewer / approve)

Each lifecycle test creates uniquely-named resources (branch / tag / PR)
under a per-session prefix and cleans them up in a try/finally block,
so successful AND failing runs leave the repository tidy.
"""

import os
import time
import uuid
from typing import Any

import pytest

from mcp_atlassian.bitbucket.client import BitbucketFetcher
from mcp_atlassian.bitbucket.config import BitbucketConfig


def _suppress(fn, *args, **kwargs) -> None:
    """Best-effort cleanup helper: swallow exceptions so teardown is robust."""
    try:
        fn(*args, **kwargs)
    except Exception:
        pass


@pytest.mark.integration
class TestRealBitbucketAPI:
    """Live tests against a real Bitbucket Server.

    Coverage: all 36 Bitbucket tools registered in servers/bitbucket.py.
    """

    @pytest.fixture(autouse=True)
    def skip_without_real_data(self, request):
        if not request.config.getoption("--use-real-data", default=False):
            pytest.skip("Real API tests require --use-real-data flag")
        if not os.getenv("BITBUCKET_URL"):
            pytest.skip("BITBUCKET_URL not set")
        if not os.getenv("BITBUCKET_PERSONAL_TOKEN"):
            pytest.skip("BITBUCKET_PERSONAL_TOKEN not set")

    @pytest.fixture(scope="class")
    def bb(self) -> BitbucketFetcher:
        """Real BitbucketFetcher built from the environment."""
        return BitbucketFetcher(config=BitbucketConfig.from_env())

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
    def default_branch_head(self, bb, project_key, repo_slug) -> tuple[str, str]:
        """Return (default_branch_name, head_commit_id) for the test repo."""
        branches = bb.get_branches(project_key, repo_slug, limit=50)
        default = next((b for b in branches if b.get("isDefault")), branches[0])
        return default["displayId"], default["latestCommit"]

    # ------------------------------------------------------------------
    # Read-only tools (12 tests, 12 tools)
    # ------------------------------------------------------------------

    def test_get_projects(self, bb, project_key):
        projects = bb.get_projects(limit=100)
        assert isinstance(projects, list)
        assert any(p["key"] == project_key for p in projects), (
            f"Project {project_key} not visible to the test PAT"
        )

    def test_get_repo(self, bb, project_key, repo_slug):
        repo = bb.get_repo(project_key, repo_slug)
        assert repo is not None
        assert repo["slug"] == repo_slug
        assert repo["project"]["key"] == project_key

    def test_get_repos(self, bb, project_key, repo_slug):
        repos = bb.get_repos(project_key, limit=100)
        assert any(r["slug"] == repo_slug for r in repos)

    def test_get_branches(self, bb, project_key, repo_slug):
        branches = bb.get_branches(project_key, repo_slug, limit=50)
        assert any(b.get("isDefault") for b in branches), "no default branch found"

    def test_get_tags(self, bb, project_key, repo_slug):
        tags = bb.get_tags(project_key, repo_slug, limit=10)
        # The shared TEST/test repo may or may not have tags; we only assert shape.
        assert isinstance(tags, list)

    def test_get_file_list(self, bb, project_key, repo_slug):
        files = bb.get_file_list(project_key, repo_slug)
        assert isinstance(files, list)
        assert len(files) > 0, "expected at least one file in TEST/test"

    def test_get_file_content(self, bb, project_key, repo_slug):
        files = bb.get_file_list(project_key, repo_slug)
        first = files[0]
        content = bb.get_file_content(project_key, repo_slug, first)
        # Must be str — MCP cannot JSON-serialize bytes.
        assert isinstance(content, str), (
            f"get_file_content returned {type(content).__name__}, expected str"
        )

    def test_get_commits(self, bb, project_key, repo_slug, default_branch_head):
        branch, _ = default_branch_head
        commits = bb.get_commits(project_key, repo_slug, branch=branch, limit=5)
        assert len(commits) > 0
        assert all("id" in c for c in commits)

    def test_get_commit(self, bb, project_key, repo_slug, default_branch_head):
        _, head = default_branch_head
        commit = bb.get_commit(project_key, repo_slug, head)
        assert commit["id"] == head

    def test_get_diff(self, bb, project_key, repo_slug, default_branch_head):
        _, head = default_branch_head
        files = bb.get_file_list(project_key, repo_slug)
        first = files[0]
        # Same commit on both sides → empty diff but a valid response shape.
        diff = bb.get_diff(
            project_key, repo_slug, path=first, hash_oldest=head, hash_newest=head
        )
        # Upstream may return a dict (with "diffs" key) or None for empty diff.
        assert diff is None or isinstance(diff, (dict, list))

    def test_search_code(self, bb, project_key, repo_slug):
        try:
            result = bb.search_code(project_key, repo_slug, "test", limit=5)
        except Exception as e:
            pytest.skip(f"Bitbucket code search service unavailable: {e!r}")
        # Returns list of result dicts; the test repo contains at least "test.txt"
        # with the word "test" so a result is expected. Some indexes lag — accept
        # empty as well, but the call must succeed and return a list.
        assert isinstance(result, list)

    def test_get_pull_requests(self, bb, project_key, repo_slug):
        prs = bb.get_pull_requests(project_key, repo_slug, state="ALL", limit=10)
        assert isinstance(prs, list)

    # ------------------------------------------------------------------
    # Lifecycle: branch (2 tools)
    # ------------------------------------------------------------------

    def test_branch_lifecycle(self, bb, project_key, repo_slug, run_id, default_branch_head):
        """create_branch + delete_branch."""
        _, head = default_branch_head
        name = f"int-test-branch-{run_id}"
        try:
            created = bb.create_branch(project_key, repo_slug, name, head)
            assert created["displayId"] == name
            assert created["latestCommit"] == head

            branches = bb.get_branches(project_key, repo_slug, limit=100)
            assert any(b["displayId"] == name for b in branches)
        finally:
            _suppress(bb.delete_branch, project_key, repo_slug, name)

        branches = bb.get_branches(project_key, repo_slug, limit=100)
        assert not any(b["displayId"] == name for b in branches), (
            "delete_branch did not remove the branch"
        )

    # ------------------------------------------------------------------
    # Lifecycle: tag (2 tools)
    # ------------------------------------------------------------------

    def test_tag_lifecycle(self, bb, project_key, repo_slug, run_id, default_branch_head):
        """create_tag + delete_tag (+ get_tags coverage)."""
        _, head = default_branch_head
        name = f"int-test-tag-{run_id}"
        try:
            created = bb.create_tag(
                project_key, repo_slug, name, head, description="integration test tag"
            )
            # set_tag may return None or a tag dict depending on the lib version.
            if created is not None:
                assert created.get("displayId", name) in (name, f"refs/tags/{name}")

            tags = bb.get_tags(project_key, repo_slug, limit=50)
            assert any(t.get("displayId") == name for t in tags), (
                "created tag not visible via get_tags"
            )
        finally:
            _suppress(bb.delete_tag, project_key, repo_slug, name)

    # ------------------------------------------------------------------
    # Lifecycle: file update (1 tool, + uses branch lifecycle)
    # ------------------------------------------------------------------

    def test_update_file_lifecycle(
        self, bb, project_key, repo_slug, run_id, default_branch_head
    ):
        """update_file on a throwaway branch."""
        _, head = default_branch_head
        branch = f"int-test-file-{run_id}"
        file_path = f"int-test-{run_id}.txt"
        try:
            bb.create_branch(project_key, repo_slug, branch, head)

            # Update a NEW file on the throwaway branch.
            result = bb.update_file(
                project_key=project_key,
                repo_slug=repo_slug,
                file_path=file_path,
                content=f"integration test content {run_id}\n",
                commit_message=f"int-test: add {file_path}",
                branch=branch,
                source_commit_id="",  # empty -> create new file
            )
            assert result is not None

            fetched = bb.get_file_content(project_key, repo_slug, file_path, branch=branch)
            assert run_id in fetched
        finally:
            _suppress(bb.delete_branch, project_key, repo_slug, branch)

    # ------------------------------------------------------------------
    # Lifecycle: pull request (10 tools)
    # ------------------------------------------------------------------

    def _open_temp_pr(
        self, bb, project_key, repo_slug, run_id, head, label: str
    ) -> tuple[dict[str, Any], str]:
        """Create a unique branch + commit + PR. Returns (pr, branch_name)."""
        branch = f"int-test-pr-{label}-{run_id}"
        bb.create_branch(project_key, repo_slug, branch, head)
        bb.update_file(
            project_key=project_key,
            repo_slug=repo_slug,
            file_path=f"int-test-{label}-{run_id}.txt",
            content=f"int-test {label} {run_id}\n",
            commit_message=f"int-test: add file for {label}",
            branch=branch,
            source_commit_id="",
        )
        pr = bb.create_pull_request(
            project_key=project_key,
            repo_slug=repo_slug,
            title=f"int-test PR {label} {run_id}",
            description=f"Integration test PR ({label}). Run id: {run_id}.",
            from_branch=branch,
            to_branch="master",
        )
        return pr, branch

    def _close_temp_pr(self, bb, project_key, repo_slug, pr_id, branch):
        # PR must be declined (or merged) before it can be deleted.
        try:
            current = bb.get_pull_request(project_key, repo_slug, pr_id)
            if current.get("state") == "OPEN":
                _suppress(
                    bb.decline_pull_request,
                    project_key,
                    repo_slug,
                    pr_id,
                    current.get("version", 0),
                )
        except Exception:
            pass
        # Re-read for fresh version before delete.
        try:
            current = bb.get_pull_request(project_key, repo_slug, pr_id)
            _suppress(
                bb.delete_pull_request,
                project_key,
                repo_slug,
                pr_id,
                current.get("version", 0),
            )
        except Exception:
            pass
        _suppress(bb.delete_branch, project_key, repo_slug, branch)

    def test_pr_full_lifecycle(
        self, bb, project_key, repo_slug, run_id, user_slug, default_branch_head
    ):
        """
        Covers: create_pull_request, get_pull_request, update_pull_request,
                get_pr_diff, get_pr_changes, add_pr_reviewer,
                approve_pull_request, unapprove_pull_request,
                decline_pull_request, reopen_pull_request, delete_pull_request.
        """
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(bb, project_key, repo_slug, run_id, head, "full")
        pr_id = pr["id"]
        try:
            fetched = bb.get_pull_request(project_key, repo_slug, pr_id)
            assert fetched["id"] == pr_id
            assert fetched["state"] == "OPEN"

            updated = bb.update_pull_request(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                title=f"int-test PR full {run_id} (updated)",
                description="updated",
                pr_version=fetched["version"],
            )
            assert "updated" in updated["title"]

            diff = bb.get_pr_diff(project_key, repo_slug, pr_id)
            assert isinstance(diff, str), (
                f"get_pr_diff returned {type(diff).__name__}, expected str"
            )
            assert len(diff) > 0

            changes = bb.get_pr_changes(project_key, repo_slug, pr_id)
            # changes may be {"values": [...]} or a list
            assert changes is not None

            # Reviewer + approve flow. Bitbucket Server typically forbids
            # self-approval of one's own PR; we exercise the tools regardless
            # and accept either success or a server-side rejection.
            reviewer_added = False
            try:
                bb.add_pr_reviewer(
                    project_key=project_key,
                    repo_slug=repo_slug,
                    pr_id=pr_id,
                    reviewer_slug=user_slug,
                )
                reviewer_added = True
            except Exception as e:
                # Real failure to call the tool — surface it.
                pytest.fail(f"add_pr_reviewer raised: {e!r}")

            if reviewer_added:
                for op_name, op in (
                    ("approve", bb.approve_pull_request),
                    ("unapprove", bb.unapprove_pull_request),
                ):
                    try:
                        op(
                            project_key=project_key,
                            repo_slug=repo_slug,
                            pr_id=pr_id,
                            user_slug=user_slug,
                        )
                    except Exception as e:
                        # Server policy may forbid self-approve — that's not a
                        # tool bug, log and continue with decline/reopen.
                        print(f"  [info] {op_name}_pull_request rejected: {e!r}")

            # Decline + reopen.
            current = bb.get_pull_request(project_key, repo_slug, pr_id)
            bb.decline_pull_request(
                project_key, repo_slug, pr_id, current["version"]
            )
            assert bb.get_pull_request(project_key, repo_slug, pr_id)["state"] == "DECLINED"

            current = bb.get_pull_request(project_key, repo_slug, pr_id)
            bb.reopen_pull_request(project_key, repo_slug, pr_id, current["version"])
            assert bb.get_pull_request(project_key, repo_slug, pr_id)["state"] == "OPEN"
        finally:
            self._close_temp_pr(bb, project_key, repo_slug, pr_id, branch)

    def test_pr_merge_lifecycle(
        self, bb, project_key, repo_slug, run_id, default_branch_head
    ):
        """Covers: merge_pull_request."""
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(bb, project_key, repo_slug, run_id, head, "merge")
        pr_id = pr["id"]
        try:
            current = bb.get_pull_request(project_key, repo_slug, pr_id)
            try:
                merged = bb.merge_pull_request(
                    project_key=project_key,
                    repo_slug=repo_slug,
                    pr_id=pr_id,
                    merge_message=f"int-test merge {run_id}",
                    pr_version=current["version"],
                )
            except Exception as e:
                # Some Bitbucket installs require approval before merge; surface
                # that as a skip rather than a failure of the merge tool itself.
                pytest.skip(f"Merge rejected by server policy: {e}")
            assert merged.get("state") == "MERGED" or merged.get("merged") is True
        finally:
            self._close_temp_pr(bb, project_key, repo_slug, pr_id, branch)

    # ------------------------------------------------------------------
    # Lifecycle: PR comments (4 tools)
    # ------------------------------------------------------------------

    def test_pr_comment_lifecycle(
        self, bb, project_key, repo_slug, run_id, default_branch_head
    ):
        """Covers: add_pr_comment, get_pr_comments, update_pr_comment, delete_pr_comment."""
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(bb, project_key, repo_slug, run_id, head, "comment")
        pr_id = pr["id"]
        try:
            created = bb.add_pr_comment(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                text=f"top-level comment {run_id}",
            )
            top_id = created["id"]
            top_v = created["version"]

            reply = bb.add_pr_comment(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                text=f"reply {run_id}",
                parent_id=top_id,
            )
            assert reply["id"] != top_id

            # The fixed get_pr_comments (now using /activities) must return
            # both the top-level comment and surface the reply on its `comments`.
            comments = bb.get_pr_comments(project_key, repo_slug, pr_id)
            top = next(c for c in comments if c["id"] == top_id)
            assert any(r["id"] == reply["id"] for r in top.get("comments", [])), (
                "reply not threaded under parent in get_pr_comments output"
            )

            updated = bb.update_pr_comment(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                comment_id=top_id,
                text=f"top-level comment {run_id} (edited)",
                comment_version=top_v,
            )
            assert "edited" in updated["text"]

            # Delete reply first, then top. Use current version each time.
            reply_now = next(
                r
                for r in bb.get_pr_comments(project_key, repo_slug, pr_id)
                for r in r.get("comments", [])
                if r["id"] == reply["id"]
            )
            bb.delete_pr_comment(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                comment_id=reply["id"],
                comment_version=reply_now["version"],
            )
            top_now = next(
                c
                for c in bb.get_pr_comments(project_key, repo_slug, pr_id)
                if c["id"] == top_id
            )
            bb.delete_pr_comment(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                comment_id=top_id,
                comment_version=top_now["version"],
            )
        finally:
            self._close_temp_pr(bb, project_key, repo_slug, pr_id, branch)

    # ------------------------------------------------------------------
    # Lifecycle: PR tasks (3 tools)
    # ------------------------------------------------------------------

    def test_pr_task_lifecycle(
        self, bb, project_key, repo_slug, run_id, default_branch_head
    ):
        """Covers: get_pr_tasks, add_pr_task, update_pr_task.

        Modeled as Bitbucket Server 7.2+ blocker comments: severity=BLOCKER on
        a regular PR comment with OPEN/RESOLVED state lifecycle.
        """
        _, head = default_branch_head
        pr, branch = self._open_temp_pr(bb, project_key, repo_slug, run_id, head, "task")
        pr_id = pr["id"]
        try:
            # 1. Top-level task.
            top_task = bb.add_pr_task(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                text=f"int-test task {run_id}",
            )
            assert top_task.get("severity") == "BLOCKER"
            assert top_task.get("state") == "OPEN"
            top_id = top_task["id"]

            # 2. Threaded task (reply to an existing comment).
            anchor = bb.add_pr_comment(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                text=f"task anchor {run_id}",
            )
            reply_task = bb.add_pr_task(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                text=f"int-test threaded task {run_id}",
                parent_id=anchor["id"],
            )
            assert reply_task.get("severity") == "BLOCKER"
            reply_id = reply_task["id"]

            # 3. List — both tasks visible, regular anchor comment NOT included.
            tasks = bb.get_pr_tasks(project_key, repo_slug, pr_id)
            task_ids = {t["id"] for t in tasks}
            assert top_id in task_ids
            assert reply_id in task_ids
            assert anchor["id"] not in task_ids, (
                "Non-BLOCKER comment leaked into get_pr_tasks output"
            )
            assert all(t.get("severity") == "BLOCKER" for t in tasks)

            # 4. Resolve.
            resolved = bb.update_pr_task(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                task_id=top_id,
                state="RESOLVED",
                task_version=top_task["version"],
            )
            assert resolved["state"] == "RESOLVED"

            # 5. Reopen + edit text in one call.
            reopened = bb.update_pr_task(
                project_key=project_key,
                repo_slug=repo_slug,
                pr_id=pr_id,
                task_id=top_id,
                text=f"int-test task {run_id} (edited)",
                state="OPEN",
                task_version=resolved["version"],
            )
            assert reopened["state"] == "OPEN"
            assert "edited" in reopened["text"]
        finally:
            self._close_temp_pr(bb, project_key, repo_slug, pr_id, branch)
