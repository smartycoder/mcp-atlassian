"""Shared fixtures for Tempo unit tests."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_atlassian.tempo import TempoClient, TempoConfig


@pytest.fixture
def tempo_config() -> TempoConfig:
    """Return a TempoConfig built from a minimal fake environment."""
    with patch.dict(
        os.environ,
        {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_PERSONAL_TOKEN": "fake-token",
            "TEMPO_ENABLED": "true",
        },
    ):
        return TempoConfig.from_env()


@pytest.fixture
def tempo_client(tempo_config: TempoConfig) -> TempoClient:
    """Return a TempoClient with a mocked atlassian.Jira instance."""
    with patch("mcp_atlassian.tempo.client.Jira") as MockJira:
        mock_jira = MagicMock()
        MockJira.return_value = mock_jira
        client = TempoClient(config=tempo_config)
        # Ensure the attribute points at the mock regardless of constructor path
        client.jira = mock_jira
        return client
