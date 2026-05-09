"""Tests for the Jira Groups mixin."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.jira.groups import GroupsMixin
from mcp_atlassian.models.jira import JiraGroup, JiraGroupMembersResult


def _make_http_error(status_code: int) -> HTTPError:
    """Create an HTTPError with a mocked response for the given status code."""
    response = MagicMock()
    response.status_code = status_code
    error = HTTPError(response=response)
    return error


class TestGroupsMixin:
    """Tests for the GroupsMixin class."""

    @pytest.fixture
    def groups_mixin(self, jira_client):
        """Create a GroupsMixin instance with mocked dependencies."""
        mixin = GroupsMixin(config=jira_client.config)
        mixin.jira = jira_client.jira
        return mixin

    # -------------------------------------------------------------------------
    # search_groups
    # -------------------------------------------------------------------------

    def test_search_groups_returns_list_of_jira_group(self, groups_mixin):
        """Happy path: search_groups parses groups from the API response."""
        groups_mixin.jira.get.return_value = {
            "groups": [
                {"name": "jira-users", "html": "<b>jira-users</b>"},
                {"name": "jira-admins", "html": "<b>jira-admins</b>"},
            ],
            "total": 2,
        }

        result = groups_mixin.search_groups("jira")

        groups_mixin.jira.get.assert_called_once_with(
            "rest/api/2/groups/picker",
            params={"query": "jira", "maxResults": 50},
        )
        assert len(result) == 2
        assert all(isinstance(g, JiraGroup) for g in result)
        assert result[0].name == "jira-users"
        assert result[1].name == "jira-admins"

    def test_search_groups_respects_max_results(self, groups_mixin):
        """search_groups passes max_results correctly to the API."""
        groups_mixin.jira.get.return_value = {"groups": []}

        groups_mixin.search_groups("test", max_results=10)

        groups_mixin.jira.get.assert_called_once_with(
            "rest/api/2/groups/picker",
            params={"query": "test", "maxResults": 10},
        )

    def test_search_groups_returns_empty_list_on_exception(self, groups_mixin):
        """search_groups returns an empty list and logs a warning on error."""
        groups_mixin.jira.get.side_effect = Exception("network error")

        result = groups_mixin.search_groups("fail")

        assert result == []

    def test_search_groups_returns_empty_list_on_unexpected_type(self, groups_mixin):
        """search_groups returns an empty list when the API returns a non-dict."""
        groups_mixin.jira.get.return_value = "unexpected string"

        result = groups_mixin.search_groups("test")

        assert result == []

    def test_search_groups_empty_result(self, groups_mixin):
        """search_groups returns an empty list when groups array is empty."""
        groups_mixin.jira.get.return_value = {"groups": [], "total": 0}

        result = groups_mixin.search_groups("nomatch")

        assert result == []

    # -------------------------------------------------------------------------
    # get_group_members
    # -------------------------------------------------------------------------

    def test_get_group_members_returns_members_result(self, groups_mixin):
        """Happy path: get_group_members returns a populated JiraGroupMembersResult."""
        groups_mixin.jira.get.return_value = {
            "values": [
                {
                    "key": "jdoe",
                    "name": "jdoe",
                    "displayName": "John Doe",
                    "emailAddress": "jdoe@example.com",
                    "active": True,
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,
        }

        result = groups_mixin.get_group_members("jira-users")

        groups_mixin.jira.get.assert_called_once_with(
            "rest/api/2/group/member",
            params={
                "groupname": "jira-users",
                "includeInactiveUsers": False,
                "startAt": 0,
                "maxResults": 50,
            },
        )
        assert isinstance(result, JiraGroupMembersResult)
        assert result.total == 1
        assert len(result.members) == 1
        assert result.members[0].name == "jdoe"
        assert result.members[0].display_name == "John Doe"

    def test_get_group_members_pagination_params(self, groups_mixin):
        """get_group_members passes pagination and filter params correctly."""
        groups_mixin.jira.get.return_value = {
            "values": [],
            "total": 0,
            "startAt": 25,
            "maxResults": 25,
            "isLast": True,
        }

        groups_mixin.get_group_members(
            "my-group", include_inactive=True, start_at=25, max_results=25
        )

        groups_mixin.jira.get.assert_called_once_with(
            "rest/api/2/group/member",
            params={
                "groupname": "my-group",
                "includeInactiveUsers": True,
                "startAt": 25,
                "maxResults": 25,
            },
        )

    def test_get_group_members_raises_value_error_on_404(self, groups_mixin):
        """get_group_members raises ValueError when the group is not found (404)."""
        groups_mixin.jira.get.side_effect = _make_http_error(404)

        with pytest.raises(ValueError, match="Group 'missing-group' not found."):
            groups_mixin.get_group_members("missing-group")

    def test_get_group_members_raises_auth_error_on_401(self, groups_mixin):
        """get_group_members raises MCPAtlassianAuthenticationError on 401."""
        groups_mixin.jira.get.side_effect = _make_http_error(401)

        with pytest.raises(MCPAtlassianAuthenticationError):
            groups_mixin.get_group_members("some-group")

    def test_get_group_members_raises_auth_error_on_403(self, groups_mixin):
        """get_group_members raises MCPAtlassianAuthenticationError on 403."""
        groups_mixin.jira.get.side_effect = _make_http_error(403)

        with pytest.raises(MCPAtlassianAuthenticationError):
            groups_mixin.get_group_members("some-group")

    # -------------------------------------------------------------------------
    # create_group
    # -------------------------------------------------------------------------

    def test_create_group_calls_post_and_returns_dict(self, groups_mixin):
        """Happy path: create_group posts to the API and returns the response dict."""
        groups_mixin.jira.post.return_value = {"name": "new-group", "self": "http://..."}

        result = groups_mixin.create_group("new-group")

        groups_mixin.jira.post.assert_called_once_with(
            "rest/api/2/group", data={"name": "new-group"}
        )
        assert result["name"] == "new-group"

    def test_create_group_reraises_on_error(self, groups_mixin):
        """create_group logs the error and re-raises any exception."""
        groups_mixin.jira.post.side_effect = Exception("creation failed")

        with pytest.raises(Exception, match="creation failed"):
            groups_mixin.create_group("bad-group")

    # -------------------------------------------------------------------------
    # delete_group
    # -------------------------------------------------------------------------

    def test_delete_group_calls_delete_with_groupname(self, groups_mixin):
        """Happy path: delete_group calls the API with the correct groupname param."""
        groups_mixin.jira.delete.return_value = None

        groups_mixin.delete_group("old-group")

        groups_mixin.jira.delete.assert_called_once_with(
            "rest/api/2/group", params={"groupname": "old-group"}
        )

    def test_delete_group_with_swap_group(self, groups_mixin):
        """delete_group includes swapGroup param when provided."""
        groups_mixin.jira.delete.return_value = None

        groups_mixin.delete_group("old-group", swap_group="replacement-group")

        groups_mixin.jira.delete.assert_called_once_with(
            "rest/api/2/group",
            params={"groupname": "old-group", "swapGroup": "replacement-group"},
        )

    def test_delete_group_without_swap_group_omits_param(self, groups_mixin):
        """delete_group does not include swapGroup when not provided."""
        groups_mixin.jira.delete.return_value = None

        groups_mixin.delete_group("old-group")

        call_params = groups_mixin.jira.delete.call_args[1]["params"]
        assert "swapGroup" not in call_params

    # -------------------------------------------------------------------------
    # add_user_to_group
    # -------------------------------------------------------------------------

    def test_add_user_to_group_calls_post(self, groups_mixin):
        """Happy path: add_user_to_group posts to the correct endpoint."""
        groups_mixin.jira.post.return_value = None

        groups_mixin.add_user_to_group("jira-users", "jdoe")

        groups_mixin.jira.post.assert_called_once_with(
            "rest/api/2/group/user",
            params={"groupname": "jira-users"},
            data={"name": "jdoe"},
        )

    # -------------------------------------------------------------------------
    # remove_user_from_group
    # -------------------------------------------------------------------------

    def test_remove_user_from_group_calls_delete(self, groups_mixin):
        """Happy path: remove_user_from_group deletes with the correct params."""
        groups_mixin.jira.delete.return_value = None

        groups_mixin.remove_user_from_group("jira-users", "jdoe")

        groups_mixin.jira.delete.assert_called_once_with(
            "rest/api/2/group/user",
            params={"groupname": "jira-users", "username": "jdoe"},
        )
