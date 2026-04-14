"""
Tests for the Tempo Planner Pydantic models.

These tests validate the conversion of Tempo Planner API responses to structured
models and the simplified dictionary conversion for tool output.
"""

from typing import Any

import pytest

from src.mcp_atlassian.models.constants import EMPTY_STRING
from src.mcp_atlassian.models.tempo import (
    TempoAllocation,
    TempoTeam,
    TempoTeamMember,
    TempoTeamRole,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def make_team_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 7,
        "name": "Backend Team",
        "summary": "Handles all backend work",
        "lead": {"key": "jdoe"},
        "isPublic": False,
    }
    base.update(overrides)
    return base


def make_member_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 42,
        "member": {
            "name": "jdoe",
            "type": "USER",
            "displayName": "John Doe",
        },
        "membership": {
            "role": {"name": "Developer"},
            "availability": 80,
            "dateFrom": "2026-01-01",
            "dateTo": "2026-12-31",
            "status": "ACTIVE",
        },
    }
    base.update(overrides)
    return base


def make_allocation_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 101,
        "assignee": {"key": "jdoe", "type": "USER"},
        "planItem": {"id": 200, "type": "ISSUE"},
        "commitment": 40,
        "secondsPerDay": 28800,
        "startDate": "2026-01-01",
        "endDate": "2026-01-31",
        "description": "Feature work",
        "dateCreated": "2026-01-01T08:00:00",
        "dateUpdated": "2026-01-02T09:00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TempoTeam
# ---------------------------------------------------------------------------


class TestTempoTeam:
    """Tests for TempoTeam.from_api_response and to_simplified_dict."""

    def test_from_api_response_full(self) -> None:
        """All fields including nested lead are correctly extracted."""
        team = TempoTeam.from_api_response(make_team_payload())

        assert team.id == 7
        assert team.name == "Backend Team"
        assert team.summary == "Handles all backend work"
        assert team.lead_key == "jdoe"
        assert team.is_public is False

    def test_from_api_response_no_lead(self) -> None:
        """Missing lead object results in lead_key being None."""
        payload = make_team_payload()
        del payload["lead"]
        team = TempoTeam.from_api_response(payload)

        assert team.lead_key is None

    def test_from_api_response_lead_without_key(self) -> None:
        """Lead object present but has no key field results in lead_key being None."""
        payload = make_team_payload(lead={})
        team = TempoTeam.from_api_response(payload)

        assert team.lead_key is None

    def test_from_api_response_no_summary(self) -> None:
        """Missing summary field defaults to None."""
        payload = make_team_payload()
        del payload["summary"]
        team = TempoTeam.from_api_response(payload)

        assert team.summary is None

    def test_from_api_response_empty_dict(self) -> None:
        """Empty dict returns a default-valued instance."""
        team = TempoTeam.from_api_response({})

        assert team.id == -1
        assert team.name == EMPTY_STRING
        assert team.summary is None
        assert team.lead_key is None
        assert team.is_public is True

    def test_from_api_response_public_defaults_true(self) -> None:
        """isPublic defaults to True when absent."""
        payload = make_team_payload()
        del payload["isPublic"]
        team = TempoTeam.from_api_response(payload)

        assert team.is_public is True

    def test_to_simplified_dict_full(self) -> None:
        """to_simplified_dict contains all expected keys for a populated model."""
        team = TempoTeam.from_api_response(make_team_payload())
        result = team.to_simplified_dict()

        assert result["id"] == 7
        assert result["name"] == "Backend Team"
        assert result["is_public"] is False
        assert result["summary"] == "Handles all backend work"
        assert result["lead_key"] == "jdoe"

    def test_to_simplified_dict_omits_none_optional_fields(self) -> None:
        """to_simplified_dict omits summary and lead_key when they are None."""
        team = TempoTeam.from_api_response({})
        result = team.to_simplified_dict()

        assert "summary" not in result
        assert "lead_key" not in result


# ---------------------------------------------------------------------------
# TempoTeamRole
# ---------------------------------------------------------------------------


class TestTempoTeamRole:
    """Tests for TempoTeamRole.from_api_response and to_simplified_dict."""

    def test_from_api_response_full(self) -> None:
        """Both id and name are correctly extracted."""
        role = TempoTeamRole.from_api_response({"id": 3, "name": "Developer"})

        assert role.id == 3
        assert role.name == "Developer"

    def test_from_api_response_empty_dict(self) -> None:
        """Empty dict returns a default-valued instance."""
        role = TempoTeamRole.from_api_response({})

        assert role.id == -1
        assert role.name == EMPTY_STRING

    def test_to_simplified_dict(self) -> None:
        """to_simplified_dict returns id and name."""
        role = TempoTeamRole.from_api_response({"id": 5, "name": "Tester"})
        result = role.to_simplified_dict()

        assert result == {"id": 5, "name": "Tester"}


# ---------------------------------------------------------------------------
# TempoTeamMember
# ---------------------------------------------------------------------------


class TestTempoTeamMember:
    """Tests for TempoTeamMember.from_api_response and to_simplified_dict."""

    def test_from_api_response_full(self) -> None:
        """All nested fields from member and membership are correctly flattened."""
        member = TempoTeamMember.from_api_response(make_member_payload())

        assert member.id == 42
        assert member.member_key == "jdoe"
        assert member.member_type == "USER"
        assert member.display_name == "John Doe"
        assert member.role == "Developer"
        assert member.availability == 80
        assert member.date_from == "2026-01-01"
        assert member.date_to == "2026-12-31"
        assert member.status == "ACTIVE"

    def test_from_api_response_group_type(self) -> None:
        """GROUP member type is preserved correctly."""
        payload = make_member_payload()
        payload["member"]["type"] = "GROUP"
        member = TempoTeamMember.from_api_response(payload)

        assert member.member_type == "GROUP"

    def test_from_api_response_group_user_type(self) -> None:
        """GROUP_USER member type is preserved correctly."""
        payload = make_member_payload()
        payload["member"]["type"] = "GROUP_USER"
        member = TempoTeamMember.from_api_response(payload)

        assert member.member_type == "GROUP_USER"

    def test_from_api_response_no_role(self) -> None:
        """Missing role in membership results in role being None."""
        payload = make_member_payload()
        del payload["membership"]["role"]
        member = TempoTeamMember.from_api_response(payload)

        assert member.role is None

    def test_from_api_response_role_without_name(self) -> None:
        """Role object present but has no name results in role being None."""
        payload = make_member_payload()
        payload["membership"]["role"] = {}
        member = TempoTeamMember.from_api_response(payload)

        assert member.role is None

    def test_from_api_response_no_dates(self) -> None:
        """Missing dateFrom and dateTo result in None values."""
        payload = make_member_payload()
        del payload["membership"]["dateFrom"]
        del payload["membership"]["dateTo"]
        member = TempoTeamMember.from_api_response(payload)

        assert member.date_from is None
        assert member.date_to is None

    def test_from_api_response_empty_dict(self) -> None:
        """Empty dict returns a default-valued instance."""
        member = TempoTeamMember.from_api_response({})

        assert member.id == -1
        assert member.member_key == EMPTY_STRING
        assert member.member_type == "USER"
        assert member.display_name == EMPTY_STRING
        assert member.role is None
        assert member.availability == 100
        assert member.date_from is None
        assert member.date_to is None
        assert member.status == EMPTY_STRING

    def test_from_api_response_no_member_object(self) -> None:
        """Missing member sub-object produces default member fields."""
        payload = make_member_payload()
        del payload["member"]
        member = TempoTeamMember.from_api_response(payload)

        assert member.member_key == EMPTY_STRING
        assert member.member_type == "USER"
        assert member.display_name == EMPTY_STRING

    def test_from_api_response_no_membership_object(self) -> None:
        """Missing membership sub-object produces default membership fields."""
        payload = make_member_payload()
        del payload["membership"]
        member = TempoTeamMember.from_api_response(payload)

        assert member.role is None
        assert member.availability == 100
        assert member.date_from is None
        assert member.date_to is None
        assert member.status == EMPTY_STRING

    def test_to_simplified_dict_full(self) -> None:
        """to_simplified_dict contains all populated fields."""
        member = TempoTeamMember.from_api_response(make_member_payload())
        result = member.to_simplified_dict()

        assert result["id"] == 42
        assert result["member_key"] == "jdoe"
        assert result["member_type"] == "USER"
        assert result["display_name"] == "John Doe"
        assert result["role"] == "Developer"
        assert result["availability"] == 80
        assert result["date_from"] == "2026-01-01"
        assert result["date_to"] == "2026-12-31"
        assert result["status"] == "ACTIVE"

    def test_to_simplified_dict_omits_none_optional_fields(self) -> None:
        """to_simplified_dict omits role and dates when they are None."""
        member = TempoTeamMember.from_api_response({})
        result = member.to_simplified_dict()

        assert "role" not in result
        assert "date_from" not in result
        assert "date_to" not in result


# ---------------------------------------------------------------------------
# TempoAllocation
# ---------------------------------------------------------------------------


class TestTempoAllocation:
    """Tests for TempoAllocation.from_api_response and to_simplified_dict."""

    def test_from_api_response_full(self) -> None:
        """All fields including nested assignee and planItem are correctly extracted."""
        allocation = TempoAllocation.from_api_response(make_allocation_payload())

        assert allocation.id == 101
        assert allocation.assignee_key == "jdoe"
        assert allocation.assignee_type == "USER"
        assert allocation.plan_item_id == 200
        assert allocation.plan_item_type == "ISSUE"
        assert allocation.commitment == 40
        assert allocation.seconds_per_day == 28800
        assert allocation.start == "2026-01-01"
        assert allocation.end == "2026-01-31"
        assert allocation.description == "Feature work"
        assert allocation.created == "2026-01-01T08:00:00"
        assert allocation.updated == "2026-01-02T09:00:00"

    def test_from_api_response_team_assignee_type(self) -> None:
        """TEAM assignee type is preserved correctly."""
        payload = make_allocation_payload()
        payload["assignee"]["type"] = "TEAM"
        allocation = TempoAllocation.from_api_response(payload)

        assert allocation.assignee_type == "TEAM"

    def test_from_api_response_project_plan_item_type(self) -> None:
        """PROJECT plan item type is preserved correctly."""
        payload = make_allocation_payload()
        payload["planItem"]["type"] = "PROJECT"
        allocation = TempoAllocation.from_api_response(payload)

        assert allocation.plan_item_type == "PROJECT"

    def test_from_api_response_no_description(self) -> None:
        """Missing description defaults to None."""
        payload = make_allocation_payload()
        del payload["description"]
        allocation = TempoAllocation.from_api_response(payload)

        assert allocation.description is None

    def test_from_api_response_empty_dict(self) -> None:
        """Empty dict returns a default-valued instance."""
        allocation = TempoAllocation.from_api_response({})

        assert allocation.id == -1
        assert allocation.assignee_key == EMPTY_STRING
        assert allocation.assignee_type == EMPTY_STRING
        assert allocation.plan_item_id == -1
        assert allocation.plan_item_type == EMPTY_STRING
        assert allocation.commitment == 0
        assert allocation.seconds_per_day == 0
        assert allocation.start == EMPTY_STRING
        assert allocation.end == EMPTY_STRING
        assert allocation.description is None
        assert allocation.created == EMPTY_STRING
        assert allocation.updated == EMPTY_STRING

    def test_from_api_response_no_assignee_object(self) -> None:
        """Missing assignee sub-object produces empty assignee fields."""
        payload = make_allocation_payload()
        del payload["assignee"]
        allocation = TempoAllocation.from_api_response(payload)

        assert allocation.assignee_key == EMPTY_STRING
        assert allocation.assignee_type == EMPTY_STRING

    def test_from_api_response_no_plan_item_object(self) -> None:
        """Missing planItem sub-object produces default plan item fields."""
        payload = make_allocation_payload()
        del payload["planItem"]
        allocation = TempoAllocation.from_api_response(payload)

        assert allocation.plan_item_id == -1
        assert allocation.plan_item_type == EMPTY_STRING

    def test_from_api_response_alternate_field_names(self) -> None:
        """Flat 'start'/'end'/'created'/'updated' field names are also accepted."""
        payload: dict[str, Any] = {
            "id": 5,
            "assignee": {"key": "asmith", "type": "USER"},
            "planItem": {"id": 10, "type": "SPRINT"},
            "commitment": 20,
            "secondsPerDay": 14400,
            "start": "2026-03-01",
            "end": "2026-03-31",
            "created": "2026-02-28T10:00:00",
            "updated": "2026-02-28T11:00:00",
        }
        allocation = TempoAllocation.from_api_response(payload)

        assert allocation.start == "2026-03-01"
        assert allocation.end == "2026-03-31"
        assert allocation.created == "2026-02-28T10:00:00"
        assert allocation.updated == "2026-02-28T11:00:00"

    def test_to_simplified_dict_full(self) -> None:
        """to_simplified_dict contains all populated fields."""
        allocation = TempoAllocation.from_api_response(make_allocation_payload())
        result = allocation.to_simplified_dict()

        assert result["id"] == 101
        assert result["assignee_key"] == "jdoe"
        assert result["assignee_type"] == "USER"
        assert result["plan_item_id"] == 200
        assert result["plan_item_type"] == "ISSUE"
        assert result["commitment"] == 40
        assert result["seconds_per_day"] == 28800
        assert result["start"] == "2026-01-01"
        assert result["end"] == "2026-01-31"
        assert result["description"] == "Feature work"
        assert result["created"] == "2026-01-01T08:00:00"
        assert result["updated"] == "2026-01-02T09:00:00"

    def test_to_simplified_dict_omits_none_description(self) -> None:
        """to_simplified_dict omits description when it is None."""
        allocation = TempoAllocation.from_api_response({})
        result = allocation.to_simplified_dict()

        assert "description" not in result

    def test_to_simplified_dict_omits_empty_timestamps(self) -> None:
        """to_simplified_dict omits created/updated when they are empty strings."""
        allocation = TempoAllocation.from_api_response({})
        result = allocation.to_simplified_dict()

        assert "created" not in result
        assert "updated" not in result
