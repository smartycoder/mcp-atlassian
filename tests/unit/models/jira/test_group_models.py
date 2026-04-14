"""
Tests for the Jira Group Pydantic models.

These tests validate the conversion of Jira API group responses to structured
models and the simplified dictionary conversion for API responses.
"""

import pytest

from src.mcp_atlassian.models.constants import EMPTY_STRING
from src.mcp_atlassian.models.jira.group import (
    JiraGroup,
    JiraGroupMember,
    JiraGroupMembersResult,
)


class TestJiraGroup:
    """Tests for the JiraGroup model."""

    def test_from_api_response_with_valid_data(self):
        """Test creating a JiraGroup from valid API data."""
        data = {"name": "jira-users", "html": "<b>jira-users</b>"}
        group = JiraGroup.from_api_response(data)
        assert group.name == "jira-users"
        assert group.html == "<b>jira-users</b>"

    def test_from_api_response_without_html(self):
        """Test creating a JiraGroup when html field is absent."""
        data = {"name": "jira-admins"}
        group = JiraGroup.from_api_response(data)
        assert group.name == "jira-admins"
        assert group.html is None

    def test_from_api_response_with_empty_dict(self):
        """Test creating a JiraGroup from an empty dict returns defaults."""
        group = JiraGroup.from_api_response({})
        assert group.name == EMPTY_STRING
        assert group.html is None

    def test_from_api_response_with_none(self):
        """Test creating a JiraGroup from None returns defaults."""
        group = JiraGroup.from_api_response(None)
        assert group.name == EMPTY_STRING
        assert group.html is None

    def test_from_api_response_with_non_dict(self):
        """Test creating a JiraGroup from a non-dict returns defaults."""
        group = JiraGroup.from_api_response("not-a-dict")
        assert group.name == EMPTY_STRING
        assert group.html is None

    def test_to_simplified_dict_with_html(self):
        """Test to_simplified_dict includes html when present."""
        group = JiraGroup(name="jira-users", html="<b>jira-users</b>")
        result = group.to_simplified_dict()
        assert result == {"name": "jira-users", "html": "<b>jira-users</b>"}

    def test_to_simplified_dict_without_html(self):
        """Test to_simplified_dict omits html when None."""
        group = JiraGroup(name="jira-users")
        result = group.to_simplified_dict()
        assert result == {"name": "jira-users"}
        assert "html" not in result

    def test_to_simplified_dict_roundtrip(self):
        """Test that from_api_response followed by to_simplified_dict preserves data."""
        data = {"name": "jira-developers", "html": "<b>jira-developers</b>"}
        group = JiraGroup.from_api_response(data)
        result = group.to_simplified_dict()
        assert result["name"] == data["name"]
        assert result["html"] == data["html"]


class TestJiraGroupMember:
    """Tests for the JiraGroupMember model."""

    def test_from_api_response_with_valid_data(self):
        """Test creating a JiraGroupMember from valid API data."""
        data = {
            "key": "jdoe",
            "name": "jdoe",
            "displayName": "John Doe",
            "emailAddress": "jdoe@example.com",
            "active": True,
        }
        member = JiraGroupMember.from_api_response(data)
        assert member.key == "jdoe"
        assert member.name == "jdoe"
        assert member.display_name == "John Doe"
        assert member.email == "jdoe@example.com"
        assert member.active is True

    def test_from_api_response_inactive_member(self):
        """Test creating a JiraGroupMember with active=False."""
        data = {
            "key": "jdoe",
            "name": "jdoe",
            "displayName": "John Doe",
            "emailAddress": "jdoe@example.com",
            "active": False,
        }
        member = JiraGroupMember.from_api_response(data)
        assert member.active is False

    def test_from_api_response_without_email(self):
        """Test creating a JiraGroupMember when emailAddress is absent."""
        data = {
            "key": "jdoe",
            "name": "jdoe",
            "displayName": "John Doe",
            "active": True,
        }
        member = JiraGroupMember.from_api_response(data)
        assert member.email is None

    def test_from_api_response_active_defaults_to_true(self):
        """Test that active defaults to True when not provided."""
        data = {"key": "jdoe", "name": "jdoe", "displayName": "John Doe"}
        member = JiraGroupMember.from_api_response(data)
        assert member.active is True

    def test_from_api_response_with_empty_dict(self):
        """Test creating a JiraGroupMember from an empty dict returns defaults."""
        member = JiraGroupMember.from_api_response({})
        assert member.key == EMPTY_STRING
        assert member.name == EMPTY_STRING
        assert member.display_name == EMPTY_STRING
        assert member.email is None
        assert member.active is True

    def test_from_api_response_with_none(self):
        """Test creating a JiraGroupMember from None returns defaults."""
        member = JiraGroupMember.from_api_response(None)
        assert member.key == EMPTY_STRING
        assert member.name == EMPTY_STRING
        assert member.display_name == EMPTY_STRING
        assert member.email is None
        assert member.active is True

    def test_from_api_response_with_non_dict(self):
        """Test creating a JiraGroupMember from a non-dict returns defaults."""
        member = JiraGroupMember.from_api_response(42)
        assert member.key == EMPTY_STRING
        assert member.name == EMPTY_STRING
        assert member.active is True

    def test_to_simplified_dict_with_email(self):
        """Test to_simplified_dict includes all fields when email is present."""
        member = JiraGroupMember(
            key="jdoe",
            name="jdoe",
            display_name="John Doe",
            email="jdoe@example.com",
            active=True,
        )
        result = member.to_simplified_dict()
        assert result["key"] == "jdoe"
        assert result["name"] == "jdoe"
        assert result["display_name"] == "John Doe"
        assert result["email"] == "jdoe@example.com"
        assert result["active"] is True

    def test_to_simplified_dict_without_email(self):
        """Test to_simplified_dict omits email when None."""
        member = JiraGroupMember(
            key="jdoe", name="jdoe", display_name="John Doe", active=True
        )
        result = member.to_simplified_dict()
        assert "email" not in result
        assert result["key"] == "jdoe"


class TestJiraGroupMembersResult:
    """Tests for the JiraGroupMembersResult model."""

    def test_from_api_response_with_valid_data(self):
        """Test creating a JiraGroupMembersResult from valid API data."""
        data = {
            "values": [
                {
                    "key": "jdoe",
                    "name": "jdoe",
                    "displayName": "John Doe",
                    "emailAddress": "jdoe@example.com",
                    "active": True,
                },
                {
                    "key": "jsmith",
                    "name": "jsmith",
                    "displayName": "Jane Smith",
                    "emailAddress": "jsmith@example.com",
                    "active": True,
                },
            ],
            "total": 2,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,
        }
        result = JiraGroupMembersResult.from_api_response(data)
        assert result.total == 2
        assert result.start_at == 0
        assert result.max_results == 50
        assert result.is_last is True
        assert len(result.members) == 2
        assert result.members[0].key == "jdoe"
        assert result.members[0].display_name == "John Doe"
        assert result.members[1].key == "jsmith"
        assert result.members[1].display_name == "Jane Smith"

    def test_from_api_response_with_empty_values(self):
        """Test creating a JiraGroupMembersResult when values list is empty."""
        data = {
            "values": [],
            "total": 0,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,
        }
        result = JiraGroupMembersResult.from_api_response(data)
        assert result.total == 0
        assert len(result.members) == 0
        assert result.is_last is True

    def test_from_api_response_pagination_not_last(self):
        """Test parsing paginated result where isLast is False."""
        data = {
            "values": [
                {
                    "key": "jdoe",
                    "name": "jdoe",
                    "displayName": "John Doe",
                    "active": True,
                }
            ],
            "total": 100,
            "startAt": 0,
            "maxResults": 1,
            "isLast": False,
        }
        result = JiraGroupMembersResult.from_api_response(data)
        assert result.total == 100
        assert result.max_results == 1
        assert result.is_last is False
        assert len(result.members) == 1

    def test_from_api_response_with_empty_dict(self):
        """Test creating a JiraGroupMembersResult from an empty dict returns defaults."""
        result = JiraGroupMembersResult.from_api_response({})
        assert result.total == 0
        assert result.start_at == 0
        assert result.max_results == 50
        assert result.is_last is True
        assert result.members == []

    def test_from_api_response_with_none(self):
        """Test creating a JiraGroupMembersResult from None returns defaults."""
        result = JiraGroupMembersResult.from_api_response(None)
        assert result.total == 0
        assert result.start_at == 0
        assert result.max_results == 50
        assert result.is_last is True
        assert result.members == []

    def test_from_api_response_with_non_dict(self):
        """Test creating a JiraGroupMembersResult from a non-dict returns defaults."""
        result = JiraGroupMembersResult.from_api_response(["not", "a", "dict"])
        assert result.total == 0
        assert result.members == []

    def test_from_api_response_missing_values_key(self):
        """Test parsing when the values key is missing entirely."""
        data = {"total": 0, "startAt": 0, "maxResults": 50, "isLast": True}
        result = JiraGroupMembersResult.from_api_response(data)
        assert result.members == []
        assert result.total == 0

    def test_to_simplified_dict(self):
        """Test to_simplified_dict includes members and pagination metadata."""
        data = {
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
        result = JiraGroupMembersResult.from_api_response(data)
        simplified = result.to_simplified_dict()

        assert simplified["total"] == 1
        assert simplified["start_at"] == 0
        assert simplified["max_results"] == 50
        assert simplified["is_last"] is True
        assert isinstance(simplified["members"], list)
        assert len(simplified["members"]) == 1
        assert simplified["members"][0]["key"] == "jdoe"
        assert simplified["members"][0]["display_name"] == "John Doe"
        assert simplified["members"][0]["email"] == "jdoe@example.com"

    def test_to_simplified_dict_empty_members(self):
        """Test to_simplified_dict with no members."""
        result = JiraGroupMembersResult()
        simplified = result.to_simplified_dict()
        assert simplified["members"] == []
        assert simplified["total"] == 0
        assert simplified["is_last"] is True
