"""Base client module for Tempo API interactions."""

import logging

from atlassian import Jira

from mcp_atlassian.utils.logging import mask_sensitive
from mcp_atlassian.utils.ssl import configure_ssl_verification

from .config import TempoConfig

logger = logging.getLogger("mcp-tempo")


class TempoClient:
    """Base client for Tempo API interactions.

    Tempo on Jira Data Center is accessed via the standard Jira DC URL.
    This class initialises an ``atlassian.Jira`` instance that Tempo mixin
    classes reuse for HTTP calls to the Tempo REST endpoints.

    Only PAT and Basic Auth are supported — OAuth is not available on DC.
    """

    config: TempoConfig

    def __init__(self, config: TempoConfig | None = None) -> None:
        """Initialise the Tempo client.

        Args:
            config: Optional configuration object; reads from environment when
                not provided.

        Raises:
            ValueError: If the configuration is missing required credentials.
        """
        self.config = config or TempoConfig.from_env()
        jc = self.config.jira_config

        if jc.auth_type == "pat":
            logger.debug(
                "Initialising Tempo/Jira client with PAT auth. "
                "URL: %s, Token (masked): %s",
                jc.url,
                mask_sensitive(str(jc.personal_token)),
            )
            self.jira = Jira(
                url=jc.url,
                token=jc.personal_token,
                cloud=jc.is_cloud,
                verify_ssl=jc.ssl_verify,
            )
        else:  # basic auth
            logger.debug(
                "Initialising Tempo/Jira client with Basic auth. "
                "URL: %s, Username: %s, API Token present: %s",
                jc.url,
                jc.username,
                bool(jc.api_token),
            )
            self.jira = Jira(
                url=jc.url,
                username=jc.username,
                password=jc.api_token,
                cloud=jc.is_cloud,
                verify_ssl=jc.ssl_verify,
            )

        configure_ssl_verification(
            service_name="Tempo",
            url=jc.url,
            session=self.jira._session,
            ssl_verify=jc.ssl_verify,
        )
