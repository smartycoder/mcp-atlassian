"""Configuration for Bitbucket Server/DC API interactions."""
import os
from dataclasses import dataclass

from ..utils.env import is_env_ssl_verify


@dataclass
class BitbucketConfig:
    """Bitbucket Server/DC API configuration.

    Authentication: Personal Access Token (PAT) only.
    PAT can come from environment (global fallback) or per-request Bearer header.
    """

    url: str = ""
    personal_token: str | None = None
    ssl_verify: bool = True

    @classmethod
    def from_env(cls) -> "BitbucketConfig":
        """Create configuration from environment variables.

        Raises:
            ValueError: If BITBUCKET_URL is missing.
        """
        url = os.getenv("BITBUCKET_URL")
        if not url:
            raise ValueError("Missing required BITBUCKET_URL environment variable")

        personal_token = os.getenv("BITBUCKET_PERSONAL_TOKEN")
        ssl_verify = is_env_ssl_verify("BITBUCKET_SSL_VERIFY")

        return cls(url=url, personal_token=personal_token, ssl_verify=ssl_verify)

    def is_auth_configured(self) -> bool:
        """Check if authentication is configured.

        Returns True if URL is set (supports per-request tokens via headers).
        """
        return bool(self.url)
