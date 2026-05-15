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
        result = self.bb.project_list(limit=limit)
        return list(result) if result else []

    def get_repos(self, project_key: str, limit: int = 25) -> list[dict[str, Any]]:
        """List repositories in a project."""
        result = self.bb.repo_list(project_key, limit=limit)
        return list(result) if result else []

    def get_repo(self, project_key: str, repo_slug: str) -> dict[str, Any] | None:
        """Get a single repository."""
        return self.bb.get_repo(project_key, repo_slug)

    def get_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str = "OPEN",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """List pull requests. state: OPEN, MERGED, DECLINED, ALL."""
        result = self.bb.get_pull_requests(
            project_key, repo_slug, state=state, order="newest", limit=limit
        )
        return list(result) if result else []

    def get_pull_request(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict[str, Any] | None:
        """Get a single pull request by ID."""
        return self.bb.get_pull_request(project_key, repo_slug, pr_id)

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
        try:
            return self.bb.open_pull_request(
                source_project=project_key,
                source_repo=repo_slug,
                dest_project=project_key,
                dest_repo=repo_slug,
                title=title,
                description=description,
                source_branch=from_branch,
                destination_branch=to_branch,
                reviewers=reviewers or [],
            )
        except Exception as e:
            logger.error(
                f"Error creating PR '{title}' in {project_key}/{repo_slug}: {e}"
            )
            raise

    def get_commits(
        self,
        project_key: str,
        repo_slug: str,
        branch: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Get commit history for a repository/branch."""
        result = self.bb.get_commits(
            project_key,
            repo_slug,
            hash_newest=branch,
            limit=limit,
        )
        return list(result) if result else []

    def get_branches(
        self, project_key: str, repo_slug: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        """List branches in a repository."""
        result = self.bb.get_branches(project_key, repo_slug, limit=limit)
        return list(result) if result else []

    def get_file_content(
        self,
        project_key: str,
        repo_slug: str,
        file_path: str,
        branch: str | None = None,
    ) -> str:
        """Get the content of a file at a given path and branch.

        atlassian-python-api returns the raw HTTP body as bytes; decode here so
        the MCP tool can JSON-serialize the result.
        """
        content = self.bb.get_content_of_file(
            project_key, repo_slug, file_path, at=branch
        )
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return content

    # --- PR Review & Lifecycle ---

    def get_pr_comments(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all comments on a pull request, including inline comments and threaded replies.

        Uses the PR activities endpoint because Bitbucket Server's /comments endpoint
        requires a `path` query parameter and only returns inline comments for that path.
        Activities expose every comment (general + inline) with its reply tree intact.
        """
        activities = self.bb.get_pull_requests_activities(
            project_key, repo_slug, pr_id, limit=limit
        )
        comments: list[dict[str, Any]] = []
        for activity in activities:
            if activity.get("action") != "COMMENTED":
                continue
            comment = activity.get("comment")
            if not comment:
                continue
            anchor = activity.get("commentAnchor")
            if anchor:
                comment = {**comment, "commentAnchor": anchor}
            comments.append(comment)
            if len(comments) >= limit:
                break
        return comments

    def add_pr_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Add a comment to a pull request, optionally as a reply to another comment."""
        return self.bb.add_pull_request_comment(
            project_key, repo_slug, pr_id, text, parent_id=parent_id
        )

    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        merge_message: str,
        *,
        close_source_branch: bool = False,
        merge_strategy: str = "merge_commit",
        pr_version: int | None = None,
    ) -> dict[str, Any]:
        """Merge a pull request."""
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
        """Decline (reject) a pull request."""
        return self.bb.decline_pull_request(project_key, repo_slug, pr_id, pr_version)

    def approve_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        user_slug: str,
    ) -> dict[str, Any]:
        """Approve a pull request on behalf of a user."""
        return self.bb.change_reviewed_status(
            project_key, repo_slug, pr_id, "APPROVED", user_slug
        )

    def update_pr_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: int,
        text: str,
        comment_version: int = 0,
    ) -> dict[str, Any]:
        """Update an existing comment on a pull request."""
        return self.bb.update_pull_request_comment(
            project_key, repo_slug, pr_id, comment_id, text, comment_version
        )

    def delete_pr_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: int,
        comment_version: int = 0,
    ) -> dict[str, Any] | None:
        """Delete a comment from a pull request."""
        return self.bb.delete_pull_request_comment(
            project_key, repo_slug, pr_id, comment_id, comment_version
        )

    def delete_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        pr_version: int = 0,
    ) -> dict[str, Any]:
        """Delete a pull request permanently."""
        return self.bb.delete_pull_request(project_key, repo_slug, pr_id, pr_version)

    def update_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        title: str | None = None,
        description: str | None = None,
        pr_version: int | None = None,
    ) -> dict[str, Any]:
        """Update a pull request's title and/or description.

        The Bitbucket REST API requires the full PR payload for updates,
        so we first fetch the current PR data and merge in the changes.
        If pr_version is not supplied, the current version from the server is used.
        """
        current = self.bb.get_pull_request(project_key, repo_slug, pr_id)
        data = {
            "version": pr_version if pr_version is not None else current.get("version", 0),
            "title": title if title is not None else current["title"],
            "description": description if description is not None else current.get("description", ""),
            "reviewers": current.get("reviewers", []),
            "toRef": current["toRef"],
            "fromRef": current["fromRef"],
        }
        return self.bb.update_pull_request(project_key, repo_slug, pr_id, data)

    def reopen_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        pr_version: int = 0,
    ) -> dict[str, Any]:
        """Re-open a declined pull request."""
        return self.bb.reopen_pull_request(project_key, repo_slug, pr_id, pr_version)

    def unapprove_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        user_slug: str,
    ) -> dict[str, Any]:
        """Remove approval from a pull request."""
        return self.bb.change_reviewed_status(
            project_key, repo_slug, pr_id, "UNAPPROVED", user_slug
        )

    def add_pr_reviewer(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        reviewer_slug: str,
    ) -> dict[str, Any]:
        """Add a reviewer to a pull request."""
        current = self.bb.get_pull_request(project_key, repo_slug, pr_id)
        reviewers = current.get("reviewers", [])
        existing = {r.get("user", {}).get("name") for r in reviewers}
        if reviewer_slug not in existing:
            reviewers.append({"user": {"name": reviewer_slug}})
        data = {
            "version": current.get("version", 0),
            "title": current["title"],
            "description": current.get("description", ""),
            "reviewers": reviewers,
            "toRef": current["toRef"],
            "fromRef": current["fromRef"],
        }
        return self.bb.update_pull_request(project_key, repo_slug, pr_id, data)

    def get_pr_diff(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        context_lines: int = 10,
    ) -> str:
        """Get the full unified diff of a pull request.

        With `not_json_response=True` the underlying client returns the raw
        bytes of the HTTP response; decode so the MCP tool returns str.
        """
        url = (
            f"{self.bb._url_pull_request(project_key, repo_slug, pr_id)}/diff"
        )
        result = self.bb.get(
            url, params={"contextLines": context_lines}, not_json_response=True
        )
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return result

    def get_pr_changes(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
    ) -> list[dict[str, Any]]:
        """Get the list of file changes in a pull request."""
        result = self.bb.get_pull_requests_changes(
            project_key, repo_slug, pr_id, start=0, limit=None
        )
        return list(result) if result else []

    def get_commit(
        self,
        project_key: str,
        repo_slug: str,
        commit_id: str,
    ) -> dict[str, Any]:
        """Get details of a single commit by its ID (SHA)."""
        return self.bb.get_commit_info(project_key, repo_slug, commit_id)

    def search_code(
        self,
        project_key: str,
        repo_slug: str,
        query: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Search for code in a repository using Bitbucket Server code search.

        Uses POST /rest/search/latest/search with a JSON body. Project/repo
        scoping goes into the query string itself (`project:KEY repo:slug`),
        which is the Bitbucket Server search-syntax convention; the request
        body only accepts `query`, `entities`, and `limits`.

        Requires the Bitbucket Server search service to be enabled.
        """
        # Use a relative path — self.bb.post prepends the base URL.
        path = "rest/search/latest/search"
        scoped_query = f"project:{project_key} repo:{repo_slug} {query}"
        body = {
            "query": scoped_query,
            "entities": {"code": {}},
            "limits": {"primary": limit, "secondary": limit},
        }
        # atlassian-python-api passes `data=` as form-encoded; the search API
        # requires a JSON body, so pass it via `json=` (the underlying requests
        # call serializes and sets Content-Type: application/json).
        result = self.bb.post(path, json=body)
        if isinstance(result, dict):
            return result.get("code", {}).get("values", [])
        return []

    # --- Code Browsing ---

    def get_diff(
        self,
        project_key: str,
        repo_slug: str,
        path: str,
        hash_oldest: str,
        hash_newest: str,
    ) -> list[dict[str, Any]] | None:
        """Get diff segments for a file between two commits.

        Returns a list of diff segment dicts as provided by the upstream API.
        """
        return self.bb.get_diff(project_key, repo_slug, path, hash_oldest, hash_newest)

    def get_file_list(
        self,
        project_key: str,
        repo_slug: str,
        sub_folder: str | None = None,
        ref: str | None = None,
    ) -> list[str]:
        """List files in a repository directory.

        Args:
            project_key: The project key.
            repo_slug: The repository slug.
            sub_folder: Optional subdirectory path to list.
            ref: Optional branch name or commit hash to browse at.
        """
        result = self.bb.get_file_list(
            project_key,
            repo_slug,
            sub_folder=sub_folder,
            query=ref,
            start=0,
            limit=None,
        )
        return list(result) if result else []

    # --- Branch & Tag Management ---

    def create_branch(
        self,
        project_key: str,
        repo_slug: str,
        name: str,
        start_point: str,
        message: str = "",
    ) -> dict[str, Any]:
        """Create a new branch in a repository."""
        return self.bb.create_branch(
            project_key, repo_slug, name, start_point, message=message
        )

    def delete_branch(
        self,
        project_key: str,
        repo_slug: str,
        name: str,
    ) -> None:
        """Delete a branch from a repository."""
        self.bb.delete_branch(project_key, repo_slug, name, end_point=None)

    def get_tags(
        self,
        project_key: str,
        repo_slug: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """List tags in a repository."""
        result = self.bb.get_tags(
            project_key,
            repo_slug,
            filter="",
            limit=limit,
            order_by=None,
            start=0,
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
        """Create a new tag at a given commit."""
        return self.bb.set_tag(
            project_key, repo_slug, tag_name, commit_id, description=description
        )

    def delete_tag(
        self,
        project_key: str,
        repo_slug: str,
        tag_name: str,
    ) -> None:
        """Delete a tag from a repository."""
        self.bb.delete_tag(project_key, repo_slug, tag_name)

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
        """Update a file in a repository with a new commit.

        Note: the upstream update_file parameter order differs from this method's
        signature; arguments are passed explicitly by position to avoid confusion.
        """
        return self.bb.update_file(
            project_key,
            repo_slug,
            content,
            commit_message,
            branch,
            file_path,
            source_commit_id,
        )

    # --- PR Tasks (Blocker Comments) ---
    #
    # Bitbucket Server 7.2 removed the legacy /tasks REST endpoints. A "task"
    # is now a PR comment with `severity: BLOCKER` and a `state` of OPEN or
    # RESOLVED, sharing the comment lifecycle endpoints:
    #
    #   GET    /pull-requests/{id}/blocker-comments   -- list
    #   POST   /pull-requests/{id}/comments           -- create (severity=BLOCKER)
    #   PUT    /pull-requests/{id}/comments/{id}      -- update text/state
    #   DELETE /pull-requests/{id}/comments/{id}      -- delete

    def get_pr_tasks(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
    ) -> list[dict[str, Any]]:
        """List PR tasks (BLOCKER-severity comments) on a pull request."""
        url = (
            f"{self.bb._url_pull_request(project_key, repo_slug, pr_id)}"
            "/blocker-comments"
        )
        result = self.bb.get(url)
        if isinstance(result, dict):
            return result.get("values", [])
        return list(result) if result else []

    def add_pr_task(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a PR task (BLOCKER-severity comment) on a pull request.

        Pass `parent_id` to thread the task as a reply to an existing comment.
        Without it, the task is a top-level blocker comment.
        """
        url = self.bb._url_pull_request_comments(project_key, repo_slug, pr_id)
        body: dict[str, Any] = {"text": text, "severity": "BLOCKER"}
        if parent_id is not None:
            body["parent"] = {"id": parent_id}
        return self.bb.post(url, json=body)

    def update_pr_task(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        task_id: int,
        text: str | None = None,
        state: str | None = None,
        task_version: int = 0,
    ) -> dict[str, Any]:
        """Update a PR task's text and/or state (OPEN or RESOLVED)."""
        url = (
            f"{self.bb._url_pull_request_comments(project_key, repo_slug, pr_id)}"
            f"/{task_id}"
        )
        body: dict[str, Any] = {"version": task_version}
        if text is not None:
            body["text"] = text
        if state is not None:
            body["state"] = state
        # atlassian-python-api's `put` JSON-encodes a dict `data` argument
        # internally (rest_client.py:412 — `data = dumps(data)`). Pass the
        # dict directly; pre-serializing here would double-encode the body.
        return self.bb.put(url, data=body)
