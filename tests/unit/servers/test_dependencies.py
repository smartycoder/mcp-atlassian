"""Unit tests for server dependencies module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_atlassian.bitbucket import BitbucketConfig, BitbucketFetcher
from mcp_atlassian.confluence import ConfluenceConfig, ConfluenceFetcher
from mcp_atlassian.jira import JiraConfig, JiraFetcher
from mcp_atlassian.servers.context import MainAppContext, UserAuthContext, user_auth_context
from mcp_atlassian.servers.dependencies import (
    _create_user_config_for_fetcher,
    get_bitbucket_fetcher,
    get_confluence_fetcher,
    get_jira_fetcher,
)
from mcp_atlassian.utils.oauth import OAuthConfig
from tests.utils.assertions import assert_mock_called_with_partial
from tests.utils.factories import AuthConfigFactory
from tests.utils.mocks import MockFastMCP

# Configure pytest for async tests
pytestmark = pytest.mark.anyio


@pytest.fixture
def config_factory():
    """Factory for creating various configuration objects."""

    class ConfigFactory:
        @staticmethod
        def create_jira_config(auth_type="basic", **overrides):
            """Create a JiraConfig instance."""
            defaults = {
                "url": "https://test.atlassian.net",
                "auth_type": auth_type,
                "ssl_verify": True,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "socks_proxy": None,
                "projects_filter": ["TEST"],
            }

            if auth_type == "basic":
                defaults.update(
                    {"username": "test_username", "api_token": "test_token"}
                )
            elif auth_type == "oauth":
                defaults["oauth_config"] = ConfigFactory.create_oauth_config()
            elif auth_type == "pat":
                defaults["personal_token"] = "test_pat_token"

            return JiraConfig(**{**defaults, **overrides})

        @staticmethod
        def create_confluence_config(auth_type="basic", **overrides):
            """Create a ConfluenceConfig instance."""
            defaults = {
                "url": "https://test.atlassian.net",
                "auth_type": auth_type,
                "ssl_verify": True,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "socks_proxy": None,
                "spaces_filter": ["TEST"],
            }

            if auth_type == "basic":
                defaults.update(
                    {"username": "test_username", "api_token": "test_token"}
                )
            elif auth_type == "oauth":
                defaults["oauth_config"] = ConfigFactory.create_oauth_config()
            elif auth_type == "pat":
                defaults["personal_token"] = "test_pat_token"

            return ConfluenceConfig(**{**defaults, **overrides})

        @staticmethod
        def create_bitbucket_config(**overrides):
            """Create a BitbucketConfig instance."""
            defaults = {
                "url": "https://bitbucket.example.com",
                "personal_token": "global-bb-pat",
                "ssl_verify": True,
            }
            return BitbucketConfig(**{**defaults, **overrides})

        @staticmethod
        def create_oauth_config(**overrides):
            """Create an OAuthConfig instance."""
            oauth_data = AuthConfigFactory.create_oauth_config(**overrides)
            return OAuthConfig(
                client_id=oauth_data["client_id"],
                client_secret=oauth_data["client_secret"],
                redirect_uri=oauth_data["redirect_uri"],
                scope=oauth_data["scope"],
                cloud_id=oauth_data["cloud_id"],
                access_token=oauth_data["access_token"],
                refresh_token=oauth_data["refresh_token"],
                expires_at=9999999999.0,
            )

        @staticmethod
        def create_app_context(
            jira_config=None,
            confluence_config=None,
            bitbucket_config=None,
            **overrides,
        ):
            """Create a MainAppContext instance."""
            defaults = {
                "full_jira_config": jira_config or ConfigFactory.create_jira_config(),
                "full_confluence_config": confluence_config
                or ConfigFactory.create_confluence_config(),
                "full_bitbucket_config": bitbucket_config,
                "read_only": False,
                "enabled_tools": ["jira_get_issue", "confluence_get_page"],
            }
            return MainAppContext(**{**defaults, **overrides})

    return ConfigFactory()


@pytest.fixture
def mock_context():
    """Create a mock Context instance."""
    return MockFastMCP.create_context()


@pytest.fixture
def mock_request():
    """Create a mock Request instance."""
    return MockFastMCP.create_request()


@pytest.fixture
def auth_scenarios():
    """Common authentication scenarios for testing."""
    return {
        "oauth": {
            "auth_type": "oauth",
            "token": "user-oauth-token",
            "email": "user@example.com",
            "credential_key": "oauth_access_token",
        },
        "pat": {
            "auth_type": "pat",
            "token": "user-pat-token",
            "email": "user@example.com",
            "credential_key": "personal_access_token",
        },
    }


def _create_user_credentials(auth_type, token, email="user@example.com"):
    """Helper to create user credentials for testing."""
    credentials = {"user_email_context": email}

    if auth_type == "oauth":
        credentials["oauth_access_token"] = token
    elif auth_type == "pat":
        credentials["personal_access_token"] = token

    return credentials


def _assert_config_attributes(
    config, expected_type, expected_auth_type, expected_token=None
):
    """Helper to assert configuration attributes."""
    assert isinstance(config, expected_type)
    assert config.auth_type == expected_auth_type

    if expected_auth_type == "oauth":
        assert config.oauth_config is not None
        assert config.oauth_config.access_token == expected_token
        assert config.username == "user@example.com"
        assert config.api_token is None
        assert config.personal_token is None
    elif expected_auth_type == "pat":
        assert config.personal_token == expected_token
        assert config.username is None
        assert config.api_token is None
        assert config.oauth_config is None


def _set_user_auth_context(auth_type=None, token=None, email=None, cloud_id=None):
    """Helper to set the user_auth_context contextvar for a test."""
    ctx = UserAuthContext(
        auth_type=auth_type, token=token, email=email, cloud_id=cloud_id
    )
    return user_auth_context.set(ctx)


def _setup_mock_context(mock_context, app_context):
    """Helper to setup mock context with app context."""
    mock_context.request_context.lifespan_context = {
        "app_lifespan_context": app_context
    }


def _create_mock_fetcher(fetcher_class, validation_return=None, validation_error=None):
    """Helper to create mock fetcher with validation behavior."""
    mock_fetcher = MagicMock(spec=fetcher_class)

    if fetcher_class == JiraFetcher:
        if validation_error:
            mock_fetcher.get_current_user_account_id.side_effect = validation_error
        else:
            mock_fetcher.get_current_user_account_id.return_value = (
                validation_return or "test-account-id"
            )
    elif fetcher_class == ConfluenceFetcher:
        if validation_error:
            mock_fetcher.get_current_user_info.side_effect = validation_error
        else:
            mock_fetcher.get_current_user_info.return_value = validation_return or {
                "email": "user@example.com",
                "displayName": "Test User",
            }

    return mock_fetcher


class TestCreateUserConfigForFetcher:
    """Tests for _create_user_config_for_fetcher function."""

    @pytest.mark.parametrize(
        "config_type,auth_type,token",
        [
            ("jira", "oauth", "user-oauth-token"),
            ("jira", "pat", "user-pat-token"),
            ("confluence", "oauth", "user-oauth-token"),
            ("confluence", "pat", "user-pat-token"),
        ],
    )
    def test_create_user_config_success(
        self, config_factory, config_type, auth_type, token
    ):
        """Test creating user-specific configs with various auth types."""
        # Create base config
        if config_type == "jira":
            base_config = config_factory.create_jira_config(auth_type=auth_type)
            expected_type = JiraConfig
        else:
            base_config = config_factory.create_confluence_config(auth_type=auth_type)
            expected_type = ConfluenceConfig

        credentials = _create_user_credentials(auth_type, token)

        result = _create_user_config_for_fetcher(
            base_config=base_config,
            auth_type=auth_type,
            credentials=credentials,
        )

        _assert_config_attributes(result, expected_type, auth_type, token)

        if config_type == "jira":
            assert result.projects_filter == ["TEST"]
        else:
            assert result.spaces_filter == ["TEST"]

    def test_oauth_auth_type_minimal_config_success(self):
        """Test OAuth auth type with minimal base config (user-provided tokens mode)."""
        # Setup minimal base config (empty credentials)
        base_oauth_config = OAuthConfig(
            client_id="",  # Empty client_id (minimal config)
            client_secret="",  # Empty client_secret (minimal config)
            redirect_uri="",
            scope="",
            cloud_id="",
        )
        base_config = JiraConfig(
            url="https://base.atlassian.net",
            auth_type="oauth",
            oauth_config=base_oauth_config,
        )

        # Test with user-provided cloud_id
        credentials = {"oauth_access_token": "user-access-token"}
        result_config = _create_user_config_for_fetcher(
            base_config=base_config,
            auth_type="oauth",
            credentials=credentials,
            cloud_id="user-cloud-id",
        )

        # Verify the result
        assert isinstance(result_config, JiraConfig)
        assert result_config.auth_type == "oauth"
        assert result_config.oauth_config is not None
        assert result_config.oauth_config.access_token == "user-access-token"
        assert result_config.oauth_config.cloud_id == "user-cloud-id"
        assert (
            result_config.oauth_config.client_id == ""
        )  # Should preserve minimal config
        assert (
            result_config.oauth_config.client_secret == ""
        )  # Should preserve minimal config

    def test_multi_tenant_config_isolation(self):
        """Test that user configs are completely isolated from each other."""
        # Setup minimal base config
        base_oauth_config = OAuthConfig(
            client_id="", client_secret="", redirect_uri="", scope="", cloud_id=""
        )
        base_config = JiraConfig(
            url="https://base.atlassian.net",
            auth_type="oauth",
            oauth_config=base_oauth_config,
        )

        # Create user config for tenant 1
        tenant1_credentials = {"oauth_access_token": "tenant1-token"}
        tenant1_config = _create_user_config_for_fetcher(
            base_config=base_config,
            auth_type="oauth",
            credentials=tenant1_credentials,
            cloud_id="tenant1-cloud-id",
        )

        # Create user config for tenant 2
        tenant2_credentials = {"oauth_access_token": "tenant2-token"}
        tenant2_config = _create_user_config_for_fetcher(
            base_config=base_config,
            auth_type="oauth",
            credentials=tenant2_credentials,
            cloud_id="tenant2-cloud-id",
        )

        # Modify tenant1 config
        tenant1_config.oauth_config.access_token = "modified-tenant1-token"
        tenant1_config.oauth_config.cloud_id = "modified-tenant1-cloud-id"

        # Verify tenant2 config remains unchanged
        assert tenant2_config.oauth_config.access_token == "tenant2-token"
        assert tenant2_config.oauth_config.cloud_id == "tenant2-cloud-id"

        # Verify base config remains unchanged
        assert base_oauth_config.access_token is None
        assert base_oauth_config.cloud_id == ""

        # Verify tenant1 config has the modifications
        assert tenant1_config.oauth_config.access_token == "modified-tenant1-token"
        assert tenant1_config.oauth_config.cloud_id == "modified-tenant1-cloud-id"

    @pytest.mark.parametrize(
        "auth_type,missing_credential,expected_error",
        [
            (
                "oauth",
                "oauth_access_token",
                "OAuth access token missing in credentials",
            ),
            ("pat", "personal_access_token", "PAT missing in credentials"),
        ],
    )
    def test_missing_credentials(
        self, config_factory, auth_type, missing_credential, expected_error
    ):
        """Test error handling for missing credentials."""
        base_config = config_factory.create_jira_config(auth_type=auth_type)
        credentials = {"user_email_context": "user@example.com"}

        with pytest.raises(ValueError, match=expected_error):
            _create_user_config_for_fetcher(
                base_config=base_config,
                auth_type=auth_type,
                credentials=credentials,
            )

    def test_unsupported_auth_type(self, config_factory):
        """Test error handling for unsupported auth types."""
        base_config = config_factory.create_jira_config()
        credentials = {"user_email_context": "user@example.com"}

        with pytest.raises(ValueError, match="Unsupported auth_type 'invalid'"):
            _create_user_config_for_fetcher(
                base_config=base_config,
                auth_type="invalid",
                credentials=credentials,
            )

    def test_missing_oauth_config(self, config_factory):
        """Test error handling for missing OAuth config when auth_type is oauth."""
        base_config = config_factory.create_jira_config(
            auth_type="basic"
        )  # No OAuth config
        credentials = _create_user_credentials("oauth", "user-oauth-token")

        with pytest.raises(ValueError, match="Global OAuth config.*is missing"):
            _create_user_config_for_fetcher(
                base_config=base_config,
                auth_type="oauth",
                credentials=credentials,
            )

    def test_unsupported_base_config_type(self):
        """Test error handling for unsupported base config types."""

        class UnsupportedConfig:
            def __init__(self):
                self.url = "https://test.atlassian.net"
                self.ssl_verify = True
                self.http_proxy = None
                self.https_proxy = None
                self.no_proxy = None
                self.socks_proxy = None

        base_config = UnsupportedConfig()
        credentials = _create_user_credentials("pat", "test-token")

        with pytest.raises(TypeError, match="Unsupported base_config type"):
            _create_user_config_for_fetcher(
                base_config=base_config,
                auth_type="pat",
                credentials=credentials,
            )


class TestGetJiraFetcher:
    """Tests for get_jira_fetcher function."""

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_user_specific_fetcher_pat(
        self,
        mock_jira_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test creating user-specific JiraFetcher when PAT is in contextvar."""
        jira_config = config_factory.create_jira_config(auth_type="pat")
        app_context = config_factory.create_app_context(jira_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(JiraFetcher)
        mock_jira_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="user-pat-token", email="user@example.com")
        )
        try:
            result = await get_jira_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        mock_jira_fetcher_class.assert_called_once()
        called_config = mock_jira_fetcher_class.call_args[1]["config"]
        assert called_config.auth_type == "pat"
        assert called_config.personal_token == "user-pat-token"

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_user_specific_fetcher_oauth(
        self,
        mock_jira_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test creating user-specific JiraFetcher when OAuth token is in contextvar."""
        jira_config = config_factory.create_jira_config(auth_type="oauth")
        app_context = config_factory.create_app_context(jira_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(JiraFetcher)
        mock_jira_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(
            UserAuthContext(
                auth_type="oauth",
                token="user-oauth-token",
                email="user@example.com",
                cloud_id="test-cloud-id",
            )
        )
        try:
            result = await get_jira_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        mock_jira_fetcher_class.assert_called_once()
        called_config = mock_jira_fetcher_class.call_args[1]["config"]
        assert called_config.auth_type == "oauth"
        assert called_config.oauth_config.access_token == "user-oauth-token"

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_global_fallback_no_user_token(
        self,
        mock_jira_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test fallback to global JiraFetcher when no user token in contextvar."""
        app_context = config_factory.create_app_context()
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(JiraFetcher)
        mock_jira_fetcher_class.return_value = mock_fetcher

        # No user_auth_context set — contextvar defaults to None
        result = await get_jira_fetcher(mock_context)

        assert result == mock_fetcher
        assert_mock_called_with_partial(
            mock_jira_fetcher_class, config=app_context.full_jira_config
        )

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_global_fallback_empty_contextvar(
        self,
        mock_jira_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test fallback to global JiraFetcher when contextvar has no token."""
        app_context = config_factory.create_app_context()
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(JiraFetcher)
        mock_jira_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(UserAuthContext())  # No token/auth_type
        try:
            result = await get_jira_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        assert_mock_called_with_partial(
            mock_jira_fetcher_class, config=app_context.full_jira_config
        )

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_missing_global_config_raises(
        self,
        mock_jira_fetcher_class,
        mock_context,
    ):
        """Test ValueError raised when no Jira config in lifespan context."""
        mock_context.request_context.lifespan_context = {}

        with pytest.raises(ValueError, match="Jira client \\(fetcher\\) not available"):
            await get_jira_fetcher(mock_context)

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_missing_lifespan_context_with_user_token(
        self,
        mock_jira_fetcher_class,
        mock_context,
    ):
        """Test ValueError raised when user token present but no lifespan context."""
        mock_context.request_context.lifespan_context = {}

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="some-pat", email="user@example.com")
        )
        try:
            with pytest.raises(
                ValueError,
                match="Jira global configuration.*is not available from lifespan context",
            ):
                await get_jira_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

    @patch("mcp_atlassian.servers.dependencies.JiraFetcher")
    async def test_validation_failure_raises(
        self,
        mock_jira_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test ValueError raised when fetcher validation fails."""
        jira_config = config_factory.create_jira_config(auth_type="pat")
        app_context = config_factory.create_app_context(jira_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(
            JiraFetcher, validation_error=Exception("Invalid token")
        )
        mock_jira_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="bad-token", email="user@example.com")
        )
        try:
            with pytest.raises(ValueError, match="Invalid user Jira token or configuration"):
                await get_jira_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)


class TestGetConfluenceFetcher:
    """Tests for get_confluence_fetcher function."""

    @patch("mcp_atlassian.servers.dependencies.ConfluenceFetcher")
    async def test_user_specific_fetcher_pat(
        self,
        mock_confluence_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test creating user-specific ConfluenceFetcher when PAT is in contextvar."""
        confluence_config = config_factory.create_confluence_config(auth_type="pat")
        app_context = config_factory.create_app_context(confluence_config=confluence_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(ConfluenceFetcher)
        mock_confluence_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="user-pat-token", email="user@example.com")
        )
        try:
            result = await get_confluence_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        mock_confluence_fetcher_class.assert_called_once()
        called_config = mock_confluence_fetcher_class.call_args[1]["config"]
        assert called_config.auth_type == "pat"
        assert called_config.personal_token == "user-pat-token"

    @patch("mcp_atlassian.servers.dependencies.ConfluenceFetcher")
    async def test_user_specific_fetcher_oauth(
        self,
        mock_confluence_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test creating user-specific ConfluenceFetcher when OAuth token is in contextvar."""
        confluence_config = config_factory.create_confluence_config(auth_type="oauth")
        app_context = config_factory.create_app_context(confluence_config=confluence_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(ConfluenceFetcher)
        mock_confluence_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(
            UserAuthContext(
                auth_type="oauth",
                token="user-oauth-token",
                email="user@example.com",
                cloud_id="test-cloud-id",
            )
        )
        try:
            result = await get_confluence_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        mock_confluence_fetcher_class.assert_called_once()
        called_config = mock_confluence_fetcher_class.call_args[1]["config"]
        assert called_config.auth_type == "oauth"
        assert called_config.oauth_config.access_token == "user-oauth-token"

    @patch("mcp_atlassian.servers.dependencies.ConfluenceFetcher")
    async def test_global_fallback_no_user_token(
        self,
        mock_confluence_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test fallback to global ConfluenceFetcher when no user token in contextvar."""
        app_context = config_factory.create_app_context()
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(ConfluenceFetcher)
        mock_confluence_fetcher_class.return_value = mock_fetcher

        result = await get_confluence_fetcher(mock_context)

        assert result == mock_fetcher
        assert_mock_called_with_partial(
            mock_confluence_fetcher_class,
            config=app_context.full_confluence_config,
        )

    @patch("mcp_atlassian.servers.dependencies.ConfluenceFetcher")
    async def test_missing_global_config_raises(
        self,
        mock_confluence_fetcher_class,
        mock_context,
    ):
        """Test ValueError raised when no Confluence config in lifespan context."""
        mock_context.request_context.lifespan_context = {}

        with pytest.raises(
            ValueError, match="Confluence client \\(fetcher\\) not available"
        ):
            await get_confluence_fetcher(mock_context)

    @patch("mcp_atlassian.servers.dependencies.ConfluenceFetcher")
    async def test_missing_lifespan_context_with_user_token(
        self,
        mock_confluence_fetcher_class,
        mock_context,
    ):
        """Test ValueError raised when user token present but no lifespan context."""
        mock_context.request_context.lifespan_context = {}

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="some-pat", email="user@example.com")
        )
        try:
            with pytest.raises(
                ValueError,
                match="Confluence global configuration.*is not available from lifespan context",
            ):
                await get_confluence_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

    @patch("mcp_atlassian.servers.dependencies.ConfluenceFetcher")
    async def test_validation_failure_raises(
        self,
        mock_confluence_fetcher_class,
        mock_context,
        config_factory,
    ):
        """Test ValueError raised when fetcher validation fails."""
        confluence_config = config_factory.create_confluence_config(auth_type="pat")
        app_context = config_factory.create_app_context(confluence_config=confluence_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = _create_mock_fetcher(
            ConfluenceFetcher, validation_error=Exception("Invalid token")
        )
        mock_confluence_fetcher_class.return_value = mock_fetcher

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="bad-token", email="user@example.com")
        )
        try:
            with pytest.raises(
                ValueError, match="Invalid user Confluence token or configuration"
            ):
                await get_confluence_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)


class TestGetBitbucketFetcher:
    """Tests for get_bitbucket_fetcher function."""

    async def test_get_bitbucket_fetcher_uses_user_token(
        self,
        mock_context,
        config_factory,
    ):
        """Test that a user PAT from contextvar overrides the global token."""
        bb_config = config_factory.create_bitbucket_config()
        app_context = config_factory.create_app_context(bitbucket_config=bb_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = MagicMock(spec=BitbucketFetcher)

        token = user_auth_context.set(
            UserAuthContext(auth_type="pat", token="user-bb-pat-token")
        )
        try:
            with patch(
                "mcp_atlassian.bitbucket.BitbucketFetcher",
                return_value=mock_fetcher,
            ) as mock_bb_class:
                result = await get_bitbucket_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        mock_bb_class.assert_called_once()
        called_config = mock_bb_class.call_args[1]["config"]
        assert called_config.personal_token == "user-bb-pat-token"
        # Base URL and ssl_verify should be preserved from global config
        assert called_config.url == bb_config.url
        assert called_config.ssl_verify == bb_config.ssl_verify

    async def test_get_bitbucket_fetcher_uses_global_config(
        self,
        mock_context,
        config_factory,
    ):
        """Test that the global config is used when no user token is in contextvar."""
        bb_config = config_factory.create_bitbucket_config()
        app_context = config_factory.create_app_context(bitbucket_config=bb_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = MagicMock(spec=BitbucketFetcher)

        # No user_auth_context set — should fall back to global config
        with patch(
            "mcp_atlassian.bitbucket.BitbucketFetcher",
            return_value=mock_fetcher,
        ) as mock_bb_class:
            result = await get_bitbucket_fetcher(mock_context)

        assert result == mock_fetcher
        mock_bb_class.assert_called_once()
        called_config = mock_bb_class.call_args[1]["config"]
        assert called_config is bb_config

    async def test_get_bitbucket_fetcher_no_config_raises(
        self,
        mock_context,
        config_factory,
    ):
        """Test ValueError raised when no Bitbucket config in lifespan context."""
        # App context with no bitbucket config (full_bitbucket_config=None)
        app_context = config_factory.create_app_context()
        _setup_mock_context(mock_context, app_context)

        with pytest.raises(
            ValueError,
            match="Bitbucket global configuration.*is not available from lifespan context",
        ):
            await get_bitbucket_fetcher(mock_context)

    async def test_get_bitbucket_fetcher_ignores_oauth_token(
        self,
        mock_context,
        config_factory,
    ):
        """Test that an OAuth token in contextvar is ignored (Bitbucket is PAT-only)."""
        bb_config = config_factory.create_bitbucket_config()
        app_context = config_factory.create_app_context(bitbucket_config=bb_config)
        _setup_mock_context(mock_context, app_context)

        mock_fetcher = MagicMock(spec=BitbucketFetcher)

        # Set an OAuth token — should be ignored, global config used instead
        token = user_auth_context.set(
            UserAuthContext(auth_type="oauth", token="some-oauth-token")
        )
        try:
            with patch(
                "mcp_atlassian.bitbucket.BitbucketFetcher",
                return_value=mock_fetcher,
            ) as mock_bb_class:
                result = await get_bitbucket_fetcher(mock_context)
        finally:
            user_auth_context.reset(token)

        assert result == mock_fetcher
        called_config = mock_bb_class.call_args[1]["config"]
        # Should use global config unchanged (no oauth support)
        assert called_config is bb_config
