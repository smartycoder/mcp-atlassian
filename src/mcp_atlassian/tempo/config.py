"""Configuration module for Tempo API interactions."""

import os
from dataclasses import dataclass

from mcp_atlassian.jira.config import JiraConfig


@dataclass
class TempoConfig:
    """Tempo API configuration.

    Tempo on Jira Data Center is accessed via the same Jira DC URL.
    Authentication is delegated entirely to JiraConfig (PAT or Basic Auth).
    """

    jira_config: JiraConfig
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "TempoConfig":
        """Create configuration from environment variables.

        Returns:
            TempoConfig with values from environment variables.

        Raises:
            ValueError: If the underlying JiraConfig cannot be constructed.
        """
        enabled = os.getenv("TEMPO_ENABLED", "").lower() in ("true", "1", "yes")
        jira_config = JiraConfig.from_env()
        return cls(jira_config=jira_config, enabled=enabled)

    def is_auth_configured(self) -> bool:
        """Check if Tempo is enabled and auth credentials are present.

        Returns:
            True if Tempo is enabled and the underlying Jira auth is configured.
        """
        return self.enabled and self.jira_config.is_auth_configured()

    @property
    def url(self) -> str:
        """Base URL, delegated from JiraConfig.

        Returns:
            The Jira base URL used for Tempo REST calls.
        """
        return self.jira_config.url

    @property
    def ssl_verify(self) -> bool:
        """SSL verification flag, delegated from JiraConfig.

        Returns:
            Whether SSL certificates should be verified.
        """
        return self.jira_config.ssl_verify
