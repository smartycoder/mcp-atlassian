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
