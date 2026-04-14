class MCPAtlassianAuthenticationError(Exception):
    """Raised when Atlassian API authentication fails (401/403)."""

    pass


class TempoNotAvailableError(Exception):
    """Raised when Tempo plugin is not available on the Jira instance."""

    pass
