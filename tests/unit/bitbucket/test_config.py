import pytest
from mcp_atlassian.bitbucket.config import BitbucketConfig


def test_from_env_with_pat(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com")
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "my-pat")
    config = BitbucketConfig.from_env()
    assert config.url == "https://bitbucket.example.com"
    assert config.personal_token == "my-pat"
    assert config.ssl_verify is True


def test_from_env_ssl_verify_false(monkeypatch):
    monkeypatch.setenv("BITBUCKET_URL", "https://bitbucket.example.com")
    monkeypatch.setenv("BITBUCKET_PERSONAL_TOKEN", "my-pat")
    monkeypatch.setenv("BITBUCKET_SSL_VERIFY", "false")
    config = BitbucketConfig.from_env()
    assert config.ssl_verify is False


def test_from_env_missing_url_raises(monkeypatch):
    monkeypatch.delenv("BITBUCKET_URL", raising=False)
    monkeypatch.delenv("BITBUCKET_PERSONAL_TOKEN", raising=False)
    with pytest.raises(ValueError, match="BITBUCKET_URL"):
        BitbucketConfig.from_env()


def test_is_auth_configured_with_pat():
    config = BitbucketConfig(
        url="https://bitbucket.example.com",
        personal_token="my-pat",
    )
    assert config.is_auth_configured() is True


def test_is_auth_configured_url_only():
    """URL-only mode is valid for per-request token auth."""
    config = BitbucketConfig(url="https://bitbucket.example.com")
    assert config.is_auth_configured() is True


def test_is_auth_configured_no_url():
    config = BitbucketConfig()
    assert config.is_auth_configured() is False
