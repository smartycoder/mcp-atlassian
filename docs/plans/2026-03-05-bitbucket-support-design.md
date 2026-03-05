# Bitbucket Server Support — Design

**Date:** 2026-03-05
**Target:** Bitbucket Server/Data Center v9.4+
**Approach:** Hybrid (single client + config + FastMCP server)

## Context

mcp-atlassian currently supports Jira and Confluence (Cloud + Server/DC). This design adds Bitbucket Server support as a third service, following the same patterns already established in the codebase.

## File Structure

```
src/mcp_atlassian/
  bitbucket/
    __init__.py          # exports BitbucketFetcher
    config.py            # BitbucketConfig dataclass
    client.py            # BitbucketFetcher with all operations
  servers/
    bitbucket.py         # FastMCP tool definitions
    main.py              # updated: mount + context + filtering
  models/
    (no new models needed initially — return raw dicts as JSON)
```

## Configuration

Environment variables (optional service — server starts without them):

```
BITBUCKET_URL              # e.g. https://bitbucket.example.com
BITBUCKET_PERSONAL_TOKEN   # fallback PAT if no Bearer header
BITBUCKET_SSL_VERIFY       # true/false (default true)
```

`BitbucketConfig` mirrors `JiraConfig` as a dataclass with `from_env()` and `is_auth_configured()` methods. Auth type is always `pat` for Server/DC.

## Authentication Flow

1. `UserTokenMiddleware` (already in `main.py`) extracts Bearer token from `Authorization` header per-request.
2. New `get_bitbucket_fetcher(ctx)` in `dependencies.py` reads the token from context and builds a `BitbucketFetcher` (with TTL cache keyed on token hash).
3. Fallback: if no Bearer token, use `BITBUCKET_PERSONAL_TOKEN` from config.

## BitbucketFetcher

Single class in `client.py` wrapping `atlassian.Bitbucket`. No mixin pattern (YAGNI — can be refactored later).

| Method | Bitbucket REST API |
|--------|--------------------|
| `get_projects(limit)` | `GET /rest/api/1.0/projects` |
| `get_repos(project_key, limit)` | `GET /rest/api/1.0/projects/{key}/repos` |
| `get_repo(project_key, repo_slug)` | `GET /rest/api/1.0/projects/{key}/repos/{slug}` |
| `get_pull_requests(project, repo, state, limit)` | `.../pull-requests?state=OPEN\|MERGED\|DECLINED` |
| `get_pull_request(project, repo, pr_id)` | `.../pull-requests/{id}` |
| `create_pull_request(project, repo, title, description, from_branch, to_branch, reviewers)` | `POST .../pull-requests` |
| `get_commits(project, repo, branch, limit)` | `.../commits?until={branch}` |
| `get_branches(project, repo, limit)` | `.../branches` |
| `get_file_content(project, repo, path, branch)` | `.../browse/{path}?at={branch}` |

## MCP Tools

Defined in `servers/bitbucket.py`, mounted at `bitbucket_mcp`:

| Tool | Tag | Description |
|------|-----|-------------|
| `bitbucket_get_projects` | read | List all accessible projects |
| `bitbucket_get_repos` | read | List repos in a project |
| `bitbucket_get_pull_requests` | read | List PRs (filter by state: OPEN/MERGED/DECLINED) |
| `bitbucket_get_pull_request` | read | Get single PR details |
| `bitbucket_create_pull_request` | write | Create a new PR |
| `bitbucket_get_commits` | read | Commit history for a repo/branch |
| `bitbucket_get_branches` | read | List branches |
| `bitbucket_get_file_content` | read | Get file content at a path/branch |

## main.py Changes

- `MainAppContext` gains `full_bitbucket_config: BitbucketConfig | None`
- `main_lifespan` loads `BitbucketConfig.from_env()` (tolerates absence — Bitbucket is optional)
- `_mcp_list_tools` adds `"bitbucket" in tool_tags` check (same pattern as jira/confluence)
- `main_mcp.mount("bitbucket", bitbucket_mcp)`
- `token_validation_cache` extended to include `BitbucketFetcher | None`

## Testing

- Unit tests: `tests/unit/servers/test_bitbucket_server.py` (mock `BitbucketFetcher`, same pattern as `test_jira_server.py`)
- Integration: `docker-compose.bitbucket.yml` with `BITBUCKET_URL` + `BITBUCKET_PERSONAL_TOKEN` env vars

## Out of Scope (for now)

- Bitbucket Cloud support (different API)
- Webhooks
- Repository admin operations (create/delete repo, manage permissions)
- Code search
