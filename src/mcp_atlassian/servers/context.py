from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_atlassian.bitbucket.config import BitbucketConfig
    from mcp_atlassian.confluence.config import ConfluenceConfig
    from mcp_atlassian.jira.config import JiraConfig
    from mcp_atlassian.tempo.config import TempoConfig


@dataclass
class UserAuthContext:
    """Per-request user authentication context for multi-user PAT/OAuth support."""

    auth_type: str | None = None  # 'pat' or 'oauth'
    token: str | None = None
    email: str | None = None
    cloud_id: str | None = None


# ContextVar to store per-request user authentication
user_auth_context: ContextVar[UserAuthContext | None] = ContextVar(
    "user_auth_context", default=None
)


@dataclass(frozen=True)
class MainAppContext:
    """
    Context holding fully configured Jira, Confluence, and Bitbucket configurations
    loaded from environment variables at server startup.
    These configurations include any global/default authentication details.
    """

    full_jira_config: JiraConfig | None = None
    full_confluence_config: ConfluenceConfig | None = None
    full_bitbucket_config: BitbucketConfig | None = None
    full_tempo_config: TempoConfig | None = None
    read_only: bool = False
    enabled_tools: list[str] | None = None
