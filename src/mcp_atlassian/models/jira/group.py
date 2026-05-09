"""
Jira Group models.

This module provides Pydantic models for Jira group entities, including
group metadata, group members, and paginated member results.
"""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import EMPTY_STRING

logger = logging.getLogger(__name__)


class JiraGroup(ApiModel):
    """
    Model representing a Jira group.
    """

    name: str = EMPTY_STRING
    html: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "JiraGroup":
        """
        Create a JiraGroup from a Jira API response.

        Args:
            data: The group data from the Jira API, e.g.
                  {"name": "jira-users", "html": "<b>jira-users</b>"}

        Returns:
            A JiraGroup instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        return cls(
            name=str(data.get("name", EMPTY_STRING)),
            html=data.get("html"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {"name": self.name}
        if self.html is not None:
            result["html"] = self.html
        return result


class JiraGroupMember(ApiModel):
    """
    Model representing a member of a Jira group.
    """

    key: str = EMPTY_STRING
    name: str = EMPTY_STRING
    display_name: str = EMPTY_STRING
    email: str | None = None
    active: bool = True

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "JiraGroupMember":
        """
        Create a JiraGroupMember from a Jira API response.

        Args:
            data: The member data from the Jira API, e.g.
                  {"key": "jdoe", "name": "jdoe", "displayName": "John Doe",
                   "emailAddress": "jdoe@example.com", "active": true}

        Returns:
            A JiraGroupMember instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        return cls(
            key=str(data.get("key", EMPTY_STRING)),
            name=str(data.get("name", EMPTY_STRING)),
            display_name=str(data.get("displayName", EMPTY_STRING)),
            email=data.get("emailAddress"),
            active=bool(data.get("active", True)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {
            "key": self.key,
            "name": self.name,
            "display_name": self.display_name,
            "active": self.active,
        }
        if self.email is not None:
            result["email"] = self.email
        return result


class JiraGroupMembersResult(ApiModel):
    """
    Model representing a paginated list of Jira group members.
    """

    members: list[JiraGroupMember] = []
    total: int = 0
    start_at: int = 0
    max_results: int = 50
    is_last: bool = True

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "JiraGroupMembersResult":
        """
        Create a JiraGroupMembersResult from a Jira API response.

        Args:
            data: The paginated members data from the Jira API, e.g.
                  {"values": [...], "total": 2, "startAt": 0,
                   "maxResults": 50, "isLast": true}

        Returns:
            A JiraGroupMembersResult instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        members: list[JiraGroupMember] = []
        values = data.get("values", [])
        if isinstance(values, list):
            for member_data in values:
                member = JiraGroupMember.from_api_response(member_data)
                members.append(member)

        total = data.get("total", 0)
        try:
            total = int(total) if total is not None else 0
        except (ValueError, TypeError):
            total = 0

        start_at = data.get("startAt", 0)
        try:
            start_at = int(start_at) if start_at is not None else 0
        except (ValueError, TypeError):
            start_at = 0

        max_results = data.get("maxResults", 50)
        try:
            max_results = int(max_results) if max_results is not None else 50
        except (ValueError, TypeError):
            max_results = 50

        return cls(
            members=members,
            total=total,
            start_at=start_at,
            max_results=max_results,
            is_last=bool(data.get("isLast", True)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        return {
            "members": [member.to_simplified_dict() for member in self.members],
            "total": self.total,
            "start_at": self.start_at,
            "max_results": self.max_results,
            "is_last": self.is_last,
        }
