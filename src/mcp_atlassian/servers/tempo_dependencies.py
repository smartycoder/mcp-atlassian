"""Dependency provider for TempoFetcher with per-request auth support."""

from __future__ import annotations

import dataclasses
import logging

from fastmcp import Context

from mcp_atlassian.jira import JiraConfig
from mcp_atlassian.servers.context import MainAppContext, user_auth_context
from mcp_atlassian.tempo import TempoConfig, TempoFetcher

logger = logging.getLogger("mcp-atlassian.servers.tempo_dependencies")


async def get_tempo_fetcher(ctx: Context) -> TempoFetcher:
    """Resolve and return a TempoFetcher for the current request context.

    Follows the same per-request auth pattern as get_jira_fetcher:
    1. Check user_auth_context for per-request token (from Authorization header)
    2. Fall back to global config from lifespan context

    Args:
        ctx: The FastMCP request context.

    Returns:
        A configured TempoFetcher instance.

    Raises:
        ValueError: If the application context is unavailable or Tempo is not configured.
    """
    lifespan_ctx_dict = ctx.request_context.lifespan_context
    app_lifespan_state: MainAppContext | None = (
        lifespan_ctx_dict.get("app_lifespan_context")
        if isinstance(lifespan_ctx_dict, dict)
        else None
    )
    if app_lifespan_state is None:
        raise ValueError("Application context is not available.")

    tempo_config: TempoConfig | None = getattr(
        app_lifespan_state, "full_tempo_config", None
    )
    if tempo_config is None:
        raise ValueError(
            "Tempo is not configured. Set TEMPO_ENABLED=true and configure Jira credentials."
        )

    # Check for per-request user auth (set by UserTokenMiddleware)
    user_auth_ctx = user_auth_context.get()
    if user_auth_ctx and user_auth_ctx.token and user_auth_ctx.auth_type == "pat":
        logger.debug(
            "get_tempo_fetcher: Found user PAT in contextvar, creating user-specific TempoFetcher"
        )
        # Clone the Jira config with the per-request token
        user_jira_config = dataclasses.replace(
            tempo_config.jira_config,
            auth_type="pat",
            personal_token=user_auth_ctx.token,
            username=None,
            api_token=None,
        )
        user_tempo_config = TempoConfig(
            jira_config=user_jira_config,
            enabled=True,
        )
        return TempoFetcher(config=user_tempo_config)

    # Fallback to global config
    logger.debug("get_tempo_fetcher: Using global TempoFetcher from lifespan context.")
    return TempoFetcher(config=tempo_config)
