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
            logger.error(f"Error creating PR '{title}' in {project_key}/{repo_slug}: {e}")
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
        """Get the content of a file at a given path and branch."""
        return self.bb.get_content_of_file(
            project_key, repo_slug, file_path, at=branch
        )
