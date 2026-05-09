"""
Tempo Planner entity models.

This module provides Pydantic models for Tempo Planner entities including
teams, team roles, team members, and allocations (plans).
"""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import EMPTY_STRING

logger = logging.getLogger(__name__)


def _safe_int(value: Any, default: int | None) -> int | None:
    """
    Safely coerce a value to int, returning default on failure.

    Args:
        value: The value to coerce
        default: The fallback value when coercion fails or value is None

    Returns:
        The coerced integer or the default
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class TempoTeam(ApiModel):
    """
    Model representing a Tempo Planner team.

    Maps to the Tempo Planner team resource. The ``lead`` field is returned
    as a nested object ``{"key": "jdoe"}`` and is flattened to ``lead_key``.
    """

    id: int = -1
    name: str = EMPTY_STRING
    summary: str | None = None
    lead_key: str | None = None
    is_public: bool = True

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoTeam":
        """
        Create a TempoTeam from a Tempo API response.

        Handles nested ``lead`` object: ``lead.key`` → ``lead_key``.

        Args:
            data: The team data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoTeam instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # Resolve lead key — API may return a string or nested dict
        lead_key: str | None = None
        lead_data = data.get("lead")
        if isinstance(lead_data, str):
            lead_key = lead_data if lead_data else None
        elif isinstance(lead_data, dict):
            raw_key = lead_data.get("key")
            if raw_key is not None:
                lead_key = str(raw_key)

        return cls(
            id=_safe_int(data.get("id"), -1),
            name=str(data.get("name", EMPTY_STRING)),
            summary=data.get("summary"),
            lead_key=lead_key,
            is_public=bool(data.get("isPublic", True)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "is_public": self.is_public,
        }

        if self.summary is not None:
            result["summary"] = self.summary

        if self.lead_key is not None:
            result["lead_key"] = self.lead_key

        return result


class TempoTeamRole(ApiModel):
    """
    Model representing a role within a Tempo Planner team.

    Roles define the capacity in which a member participates in a team
    (e.g. Developer, Tester, Architect).
    """

    id: int = -1
    name: str = EMPTY_STRING

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoTeamRole":
        """
        Create a TempoTeamRole from a Tempo API response.

        Args:
            data: The role data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoTeamRole instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        return cls(
            id=_safe_int(data.get("id"), -1),
            name=str(data.get("name", EMPTY_STRING)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
        }


class TempoTeamMember(ApiModel):
    """
    Model representing a member of a Tempo Planner team.

    The API returns a deeply nested structure with ``member`` and ``membership``
    sub-objects. This model flattens them into a single, easy-to-use structure.

    API shape::

        {
            "id": 42,
            "member": {"name": "jdoe", "type": "USER", "displayName": "John Doe"},
            "membership": {
                "role": {"name": "Developer"},
                "availability": 80,
                "dateFrom": "2026-01-01",
                "dateTo": "2026-12-31",
                "status": "ACTIVE"
            }
        }
    """

    id: int = -1
    member_key: str = EMPTY_STRING
    member_type: str = "USER"  # USER | GROUP | GROUP_USER
    display_name: str = EMPTY_STRING
    role: str | None = None
    availability: int = 100
    date_from: str | None = None
    date_to: str | None = None
    status: str = EMPTY_STRING

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "TempoTeamMember":
        """
        Create a TempoTeamMember from a Tempo API response.

        Handles nested objects:
        - ``member.name`` → ``member_key``
        - ``member.type`` → ``member_type``
        - ``member.displayName`` → ``display_name``
        - ``membership.role.name`` → ``role``
        - ``membership.availability`` → ``availability``
        - ``membership.dateFrom`` → ``date_from``
        - ``membership.dateTo`` → ``date_to``
        - ``membership.status`` → ``status``

        Args:
            data: The team member data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoTeamMember instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # Resolve member fields from nested member object
        member_key = EMPTY_STRING
        member_type = "USER"
        display_name = EMPTY_STRING
        member_data = data.get("member")
        if isinstance(member_data, dict):
            member_key = str(member_data.get("name", EMPTY_STRING))
            member_type = str(member_data.get("type", "USER"))
            display_name = str(member_data.get("displayName", EMPTY_STRING))

        # Resolve membership fields from nested membership object
        role: str | None = None
        availability = 100
        date_from: str | None = None
        date_to: str | None = None
        status = EMPTY_STRING
        membership_data = data.get("membership")
        if isinstance(membership_data, dict):
            # Role is itself nested one level deeper
            role_data = membership_data.get("role")
            if isinstance(role_data, dict):
                raw_role_name = role_data.get("name")
                if raw_role_name is not None:
                    role = str(raw_role_name)

            availability = _safe_int(membership_data.get("availability"), 100)
            date_from_raw = membership_data.get("dateFrom")
            date_from = str(date_from_raw) if date_from_raw is not None else None
            date_to_raw = membership_data.get("dateTo")
            date_to = str(date_to_raw) if date_to_raw is not None else None
            status = str(membership_data.get("status", EMPTY_STRING))

        return cls(
            id=_safe_int(data.get("id"), -1),
            member_key=member_key,
            member_type=member_type,
            display_name=display_name,
            role=role,
            availability=availability,
            date_from=date_from,
            date_to=date_to,
            status=status,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {
            "id": self.id,
            "member_key": self.member_key,
            "member_type": self.member_type,
            "display_name": self.display_name,
            "availability": self.availability,
            "status": self.status,
        }

        if self.role is not None:
            result["role"] = self.role

        if self.date_from is not None:
            result["date_from"] = self.date_from

        if self.date_to is not None:
            result["date_to"] = self.date_to

        return result


class TempoAllocation(ApiModel):
    """
    Model representing a Tempo Planner allocation (plan entry).

    An allocation records how much time a user or team is assigned to a
    particular plan item (issue, project, epic, sprint, version, or component)
    over a date range.

    The API returns nested ``assignee`` and ``planItem`` objects which are
    flattened by ``from_api_response``.
    """

    id: int = -1
    assignee_key: str = EMPTY_STRING
    assignee_type: str = EMPTY_STRING  # USER | TEAM
    plan_item_id: int = -1
    plan_item_type: str = EMPTY_STRING  # ISSUE | PROJECT | EPIC | SPRINT | VERSION | COMPONENT
    commitment: int = 0
    seconds_per_day: int = 0
    start: str = EMPTY_STRING
    end: str = EMPTY_STRING
    description: str | None = None
    created: str = EMPTY_STRING
    updated: str = EMPTY_STRING

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "TempoAllocation":
        """
        Create a TempoAllocation from a Tempo API response.

        Handles nested objects:
        - ``assignee.key`` → ``assignee_key``
        - ``assignee.type`` → ``assignee_type``
        - ``planItem.id`` → ``plan_item_id``
        - ``planItem.type`` → ``plan_item_type``

        Args:
            data: The allocation data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoAllocation instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # Resolve assignee fields from nested assignee object
        assignee_key = EMPTY_STRING
        assignee_type = EMPTY_STRING
        assignee_data = data.get("assignee")
        if isinstance(assignee_data, dict):
            assignee_key = str(assignee_data.get("key", EMPTY_STRING))
            assignee_type = str(assignee_data.get("type", EMPTY_STRING))

        # Resolve plan item fields from nested planItem object
        plan_item_id = -1
        plan_item_type = EMPTY_STRING
        plan_item_data = data.get("planItem")
        if isinstance(plan_item_data, dict):
            plan_item_id = _safe_int(plan_item_data.get("id"), -1)
            plan_item_type = str(plan_item_data.get("type", EMPTY_STRING))

        return cls(
            id=_safe_int(data.get("id"), -1),
            assignee_key=assignee_key,
            assignee_type=assignee_type,
            plan_item_id=plan_item_id,
            plan_item_type=plan_item_type,
            commitment=_safe_int(data.get("commitment"), 0),
            seconds_per_day=_safe_int(data.get("secondsPerDay"), 0),
            start=str(data.get("startDate", data.get("start", EMPTY_STRING))),
            end=str(data.get("endDate", data.get("end", EMPTY_STRING))),
            description=data.get("description"),
            created=str(data.get("dateCreated", data.get("created", EMPTY_STRING))),
            updated=str(data.get("dateUpdated", data.get("updated", EMPTY_STRING))),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {
            "id": self.id,
            "assignee_key": self.assignee_key,
            "assignee_type": self.assignee_type,
            "plan_item_id": self.plan_item_id,
            "plan_item_type": self.plan_item_type,
            "commitment": self.commitment,
            "seconds_per_day": self.seconds_per_day,
            "start": self.start,
            "end": self.end,
        }

        if self.description is not None:
            result["description"] = self.description

        if self.created:
            result["created"] = self.created

        if self.updated:
            result["updated"] = self.updated

        return result
