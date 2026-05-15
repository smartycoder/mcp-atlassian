"""Bitbucket FastMCP server instance and tool definitions."""
import json
import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from mcp_atlassian.servers.dependencies import get_bitbucket_fetcher
from mcp_atlassian.utils.decorators import check_write_access

logger = logging.getLogger(__name__)

bitbucket_mcp = FastMCP(
    name="Bitbucket MCP Service",
    description="Provides tools for interacting with Bitbucket Server/DC.",
)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_projects(
    ctx: Context,
    limit: Annotated[
        int,
        Field(description="Maximum number of projects to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
) -> str:
    """List all accessible Bitbucket projects.

    Returns a JSON list of project objects with key, name, and description.
    """
    bb = await get_bitbucket_fetcher(ctx)
    projects = bb.get_projects(limit=limit)
    return json.dumps(projects, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_repo(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
) -> str:
    """Get details of a single repository including default branch, clone URLs, and permissions."""
    bb = await get_bitbucket_fetcher(ctx)
    repo = bb.get_repo(project_key=project_key, repo_slug=repo_slug)
    if repo is None:
        return json.dumps({"error": f"Repository {project_key}/{repo_slug} not found"})
    return json.dumps(repo, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_repos(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    limit: Annotated[
        int,
        Field(description="Maximum number of repos to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
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
    state: Annotated[
        str,
        Field(description="PR state filter: OPEN, MERGED, DECLINED, or ALL", default="OPEN"),
    ] = "OPEN",
    limit: Annotated[
        int,
        Field(description="Maximum number of PRs to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
) -> str:
    """List pull requests in a repository.

    Returns PRs ordered newest first. Use state='ALL' to see all PRs regardless of status.
    """
    bb = await get_bitbucket_fetcher(ctx)
    prs = bb.get_pull_requests(
        project_key=project_key, repo_slug=repo_slug, state=state, limit=limit
    )
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
@check_write_access
async def create_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    title: Annotated[str, Field(description="Title of the pull request")],
    from_branch: Annotated[
        str, Field(description="Source branch name (e.g. 'feature/my-feature')")
    ],
    to_branch: Annotated[str, Field(description="Target branch name (e.g. 'main')")],
    description: Annotated[
        str, Field(description="Description of the pull request", default="")
    ] = "",
    reviewers: Annotated[
        list[str] | None, Field(description="List of reviewer usernames", default=None)
    ] = None,
) -> str:
    """Create a new pull request in a repository."""
    bb = await get_bitbucket_fetcher(ctx)
    try:
        pr = bb.create_pull_request(
            project_key=project_key,
            repo_slug=repo_slug,
            title=title,
            description=description,
            from_branch=from_branch,
            to_branch=to_branch,
            reviewers=reviewers or [],
        )
        return json.dumps(pr, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(
            f"Error creating pull request in {project_key}/{repo_slug}: {str(e)}",
            exc_info=True,
        )
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_commits(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    branch: Annotated[
        str | None,
        Field(
            description="Branch name to get commits from. Defaults to default branch.",
            default=None,
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Maximum number of commits to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
) -> str:
    """Get commit history for a repository, optionally filtered to a branch."""
    bb = await get_bitbucket_fetcher(ctx)
    commits = bb.get_commits(
        project_key=project_key, repo_slug=repo_slug, branch=branch, limit=limit
    )
    return json.dumps(commits, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_branches(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    limit: Annotated[
        int,
        Field(description="Maximum number of branches to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
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
    file_path: Annotated[
        str, Field(description="Path to the file (e.g. 'src/main.py' or 'README.md')")
    ],
    branch: Annotated[
        str | None,
        Field(
            description="Branch or commit hash to read from. Defaults to default branch.",
            default=None,
        ),
    ] = None,
) -> str:
    """Get the content of a file from a repository at a specific branch or commit."""
    bb = await get_bitbucket_fetcher(ctx)
    content = bb.get_file_content(
        project_key=project_key, repo_slug=repo_slug, file_path=file_path, branch=branch
    )
    return content


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pr_comments(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    limit: Annotated[
        int,
        Field(description="Maximum number of comments to return (1-100)", default=100, ge=1, le=100),
    ] = 100,
) -> str:
    """Get all comments on a pull request, including threaded replies."""
    bb = await get_bitbucket_fetcher(ctx)
    comments = bb.get_pr_comments(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id, limit=limit
    )
    return json.dumps(comments, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def add_pr_comment(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    text: Annotated[str, Field(description="The comment text")],
    parent_id: Annotated[
        int | None,
        Field(description="ID of the parent comment to reply to", default=None),
    ] = None,
) -> str:
    """Add a comment to a pull request. Use parent_id to reply to an existing comment."""
    bb = await get_bitbucket_fetcher(ctx)
    comment = bb.add_pr_comment(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        text=text,
        parent_id=parent_id,
    )
    return json.dumps(comment, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def update_pr_comment(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    comment_id: Annotated[int, Field(description="The ID of the comment to update")],
    text: Annotated[str, Field(description="The new comment text")],
    comment_version: Annotated[
        int,
        Field(description="Expected comment version for optimistic locking", default=0),
    ] = 0,
) -> str:
    """Update an existing comment on a pull request."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.update_pr_comment(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        comment_id=comment_id,
        text=text,
        comment_version=comment_version,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def merge_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    merge_message: Annotated[str, Field(description="The commit message for the merge commit")],
    close_source_branch: Annotated[
        bool,
        Field(description="Delete the source branch after merging", default=False),
    ] = False,
    merge_strategy: Annotated[
        str,
        Field(description="Merge strategy: 'merge_commit', 'squash', or 'fast_forward'", default="merge_commit"),
    ] = "merge_commit",
    pr_version: Annotated[
        int | None,
        Field(description="Expected PR version for optimistic locking", default=None),
    ] = None,
) -> str:
    """Merge a pull request with the specified strategy."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.merge_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        merge_message=merge_message,
        close_source_branch=close_source_branch,
        merge_strategy=merge_strategy,
        pr_version=pr_version,
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
        Field(description="Expected PR version for optimistic locking", default=0),
    ] = 0,
) -> str:
    """Decline/reject a pull request."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.decline_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        pr_version=pr_version,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def approve_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    user_slug: Annotated[str, Field(description="The slug of the user approving the PR")],
) -> str:
    """Approve a pull request as a specific user."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.approve_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        user_slug=user_slug,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def reopen_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    pr_version: Annotated[
        int,
        Field(description="Expected PR version for optimistic locking", default=0),
    ] = 0,
) -> str:
    """Re-open a previously declined pull request."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.reopen_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        pr_version=pr_version,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def unapprove_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    user_slug: Annotated[str, Field(description="The slug of the user removing their approval")],
) -> str:
    """Remove approval from a pull request."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.unapprove_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        user_slug=user_slug,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def add_pr_reviewer(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    reviewer_slug: Annotated[str, Field(description="Username slug of the reviewer to add")],
) -> str:
    """Add a reviewer to an existing pull request."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.add_pr_reviewer(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        reviewer_slug=reviewer_slug,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def delete_pr_comment(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    comment_id: Annotated[int, Field(description="The ID of the comment to delete")],
    comment_version: Annotated[
        int,
        Field(description="Expected comment version for optimistic locking", default=0),
    ] = 0,
) -> str:
    """Delete a comment from a pull request. Only the comment author or repo admin can delete."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.delete_pr_comment(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        comment_id=comment_id,
        comment_version=comment_version,
    )
    return json.dumps(
        result if result else {"success": True, "message": f"Comment {comment_id} deleted"},
        indent=2,
        ensure_ascii=False,
    )


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def delete_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    pr_version: Annotated[
        int,
        Field(description="Expected PR version for optimistic locking", default=0),
    ] = 0,
) -> str:
    """Delete a pull request permanently. This action cannot be undone."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.delete_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        pr_version=pr_version,
    )
    return json.dumps(
        result if result else {"success": True, "message": f"Pull request {pr_id} deleted"},
        indent=2,
        ensure_ascii=False,
    )


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def update_pull_request(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    title: Annotated[
        str | None,
        Field(description="New title for the pull request. Leave empty to keep current.", default=None),
    ] = None,
    description: Annotated[
        str | None,
        Field(description="New description for the pull request. Leave empty to keep current.", default=None),
    ] = None,
    pr_version: Annotated[
        int | None,
        Field(description="Expected PR version for optimistic locking. Auto-detected if omitted.", default=None),
    ] = None,
) -> str:
    """Update a pull request's title and/or description."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.update_pull_request(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        title=title,
        description=description,
        pr_version=pr_version,
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
    changes = bb.get_pr_changes(project_key=project_key, repo_slug=repo_slug, pr_id=pr_id)
    return json.dumps(changes, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pr_diff(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    context_lines: Annotated[
        int,
        Field(description="Number of context lines around changes", default=10, ge=0, le=100),
    ] = 10,
) -> str:
    """Get the full unified diff of a pull request across all changed files."""
    bb = await get_bitbucket_fetcher(ctx)
    diff = bb.get_pr_diff(
        project_key=project_key, repo_slug=repo_slug, pr_id=pr_id, context_lines=context_lines
    )
    if isinstance(diff, bytes):
        return diff.decode("utf-8", errors="replace")
    return str(diff)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_diff(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    path: Annotated[str, Field(description="File path to diff (e.g. 'src/main.py')")],
    hash_oldest: Annotated[str, Field(description="Oldest commit hash or branch for the diff base")],
    hash_newest: Annotated[str, Field(description="Newest commit hash or branch for the diff head")],
) -> str:
    """Get the diff of a file between two commits or branches. Returns diff segments with hunks."""
    bb = await get_bitbucket_fetcher(ctx)
    diff = bb.get_diff(
        project_key=project_key,
        repo_slug=repo_slug,
        path=path,
        hash_oldest=hash_oldest,
        hash_newest=hash_newest,
    )
    return json.dumps(diff, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_file_list(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    sub_folder: Annotated[
        str | None,
        Field(description="Subdirectory path to list files in. Lists root if omitted.", default=None),
    ] = None,
    ref: Annotated[
        str | None,
        Field(description="Branch name or commit hash to list files at. Defaults to default branch.", default=None),
    ] = None,
) -> str:
    """List file paths in a repository directory at a specific branch or commit."""
    bb = await get_bitbucket_fetcher(ctx)
    files = bb.get_file_list(
        project_key=project_key,
        repo_slug=repo_slug,
        sub_folder=sub_folder,
        ref=ref,
    )
    return json.dumps(files, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_commit(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    commit_id: Annotated[str, Field(description="The commit hash (SHA)")],
) -> str:
    """Get details of a single commit including message, author, date, and parent commits."""
    bb = await get_bitbucket_fetcher(ctx)
    commit = bb.get_commit(project_key=project_key, repo_slug=repo_slug, commit_id=commit_id)
    return json.dumps(commit, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def search_code(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    query: Annotated[str, Field(description="Search query string")],
    limit: Annotated[
        int,
        Field(description="Maximum number of results to return (1-100)", default=25, ge=1, le=100),
    ] = 25,
) -> str:
    """Search for code in a repository. Requires Bitbucket Server search service to be enabled."""
    bb = await get_bitbucket_fetcher(ctx)
    results = bb.search_code(
        project_key=project_key, repo_slug=repo_slug, query=query, limit=limit
    )
    return json.dumps(results, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def create_branch(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    name: Annotated[str, Field(description="Name for the new branch (e.g. 'feature/my-feature')")],
    start_point: Annotated[
        str, Field(description="Branch name or commit hash to create the branch from")
    ],
) -> str:
    """Create a new branch from an existing branch or commit."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.create_branch(
        project_key=project_key,
        repo_slug=repo_slug,
        name=name,
        start_point=start_point,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def delete_branch(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    name: Annotated[str, Field(description="Name of the branch to delete")],
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
    tag_name: Annotated[str, Field(description="Name for the new tag (e.g. 'v1.0.0')")],
    commit_id: Annotated[str, Field(description="Commit hash to tag")],
    description: Annotated[
        str | None,
        Field(description="Optional annotation message for the tag", default=None),
    ] = None,
) -> str:
    """Create an annotated tag at a specific commit."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.create_tag(
        project_key=project_key,
        repo_slug=repo_slug,
        tag_name=tag_name,
        commit_id=commit_id,
        description=description,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def delete_tag(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    tag_name: Annotated[str, Field(description="Name of the tag to delete (e.g. 'v1.0.0')")],
) -> str:
    """Delete a tag from a repository."""
    bb = await get_bitbucket_fetcher(ctx)
    bb.delete_tag(project_key=project_key, repo_slug=repo_slug, tag_name=tag_name)
    return json.dumps({"success": True, "message": f"Tag '{tag_name}' deleted"})


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def update_file(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    file_path: Annotated[str, Field(description="Path to the file to update (e.g. 'src/main.py')")],
    content: Annotated[str, Field(description="New content for the file")],
    commit_message: Annotated[str, Field(description="Commit message for the change")],
    branch: Annotated[str, Field(description="Branch to commit the change to")],
    source_commit_id: Annotated[
        str,
        Field(description="Current commit hash of the file. Obtain from get_commits to prevent conflicts."),
    ],
) -> str:
    """Edit a file in-place and commit the change. Get source_commit_id from get_commits."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.update_file(
        project_key=project_key,
        repo_slug=repo_slug,
        file_path=file_path,
        content=content,
        commit_message=commit_message,
        branch=branch,
        source_commit_id=source_commit_id,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "read"})
async def get_pr_tasks(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
) -> str:
    """Get checklist tasks on a pull request (OPEN or RESOLVED)."""
    bb = await get_bitbucket_fetcher(ctx)
    tasks = bb.get_pr_tasks(project_key=project_key, repo_slug=repo_slug, pr_id=pr_id)
    return json.dumps(tasks, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def add_pr_task(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    text: Annotated[str, Field(description="The task description text")],
    parent_id: Annotated[
        int | None,
        Field(
            description=(
                "Optional ID of an existing PR comment to thread the task under. "
                "Without it, the task is a top-level blocker comment."
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Add a PR task (a BLOCKER-severity comment) to a pull request.

    Bitbucket Server 7.2+ models tasks as comments with severity=BLOCKER;
    'task_id' returned here is the comment id used by update/delete.
    """
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.add_pr_task(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        text=text,
        parent_id=parent_id,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@bitbucket_mcp.tool(tags={"bitbucket", "write"})
@check_write_access
async def update_pr_task(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key (e.g. 'PROJ')")],
    repo_slug: Annotated[str, Field(description="The repository slug (e.g. 'my-repo')")],
    pr_id: Annotated[int, Field(description="The pull request ID")],
    task_id: Annotated[int, Field(description="The ID of the task to update")],
    text: Annotated[
        str | None,
        Field(description="New text for the task. Leave empty to keep current.", default=None),
    ] = None,
    state: Annotated[
        str | None,
        Field(description="New state: OPEN or RESOLVED", default=None),
    ] = None,
    task_version: Annotated[
        int,
        Field(description="Expected task (comment) version for optimistic locking", default=0),
    ] = 0,
) -> str:
    """Update a PR task's text and/or state (OPEN or RESOLVED)."""
    bb = await get_bitbucket_fetcher(ctx)
    result = bb.update_pr_task(
        project_key=project_key,
        repo_slug=repo_slug,
        pr_id=pr_id,
        task_id=task_id,
        text=text,
        state=state,
        task_version=task_version,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)
