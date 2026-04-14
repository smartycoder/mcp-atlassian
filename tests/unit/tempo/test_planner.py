"""Unit tests for TempoPlannerMixin."""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.models.tempo.planner import (
    TempoAllocation,
    TempoTeam,
    TempoTeamMember,
    TempoTeamRole,
)
from mcp_atlassian.tempo.planner import TempoPlannerMixin


# ---------------------------------------------------------------------------
# Fixture: a TempoPlannerMixin instance backed by a mocked Jira client
# ---------------------------------------------------------------------------


@pytest.fixture
def planner(tempo_client):
    """Return a TempoPlannerMixin with an already-mocked jira attribute."""
    # tempo_client is a TempoClient; we re-use it as a TempoPlannerMixin by
    # patching the class on the instance (no __init__ call needed).
    tempo_client.__class__ = TempoPlannerMixin
    return tempo_client


# ---------------------------------------------------------------------------
# Team tests
# ---------------------------------------------------------------------------


class TestGetTeams:
    def test_returns_teams_from_list_response(self, planner):
        planner.jira.get.return_value = [
            {"id": 1, "name": "Alpha", "isPublic": True},
            {"id": 2, "name": "Beta", "isPublic": False},
        ]

        teams = planner.get_teams()

        planner.jira.get.assert_called_once_with(
            "rest/tempo-teams/2/team", params=None
        )
        assert len(teams) == 2
        assert all(isinstance(t, TempoTeam) for t in teams)
        assert teams[0].name == "Alpha"
        assert teams[1].id == 2

    def test_passes_expand_param(self, planner):
        planner.jira.get.return_value = []

        planner.get_teams(expand="members")

        planner.jira.get.assert_called_once_with(
            "rest/tempo-teams/2/team", params={"expand": "members"}
        )

    def test_handles_dict_wrapper_response(self, planner):
        planner.jira.get.return_value = {
            "teams": [{"id": 5, "name": "Gamma", "isPublic": True}]
        }

        teams = planner.get_teams()

        assert len(teams) == 1
        assert teams[0].id == 5

    def test_returns_empty_list_on_error(self, planner):
        planner.jira.get.side_effect = RuntimeError("connection refused")

        teams = planner.get_teams()

        assert teams == []


class TestGetTeam:
    def test_returns_team_on_success(self, planner):
        planner.jira.get.return_value = {"id": 7, "name": "Delta", "isPublic": True}

        team = planner.get_team(7)

        planner.jira.get.assert_called_once_with("rest/tempo-teams/2/team/7")
        assert isinstance(team, TempoTeam)
        assert team.id == 7

    def test_raises_value_error_on_404(self, planner):
        response_mock = MagicMock()
        response_mock.status_code = 404
        exc = HTTPError(response=response_mock)
        planner.jira.get.side_effect = exc

        with pytest.raises(ValueError, match="7"):
            planner.get_team(7)

    def test_re_raises_non_404_http_error(self, planner):
        response_mock = MagicMock()
        response_mock.status_code = 500
        exc = HTTPError(response=response_mock)
        planner.jira.get.side_effect = exc

        with pytest.raises(HTTPError):
            planner.get_team(7)


class TestCreateTeam:
    def test_creates_team_with_all_fields(self, planner):
        planner.jira.post.return_value = {
            "id": 10,
            "name": "Omega",
            "summary": "Top team",
            "lead": {"key": "jdoe"},
            "isPublic": True,
        }

        team = planner.create_team("Omega", summary="Top team", lead_user_key="jdoe")

        planner.jira.post.assert_called_once_with(
            "rest/tempo-teams/2/team",
            data={
                "name": "Omega",
                "summary": "Top team",
                "lead": {"key": "jdoe"},
            },
        )
        assert isinstance(team, TempoTeam)
        assert team.name == "Omega"
        assert team.lead_key == "jdoe"

    def test_creates_team_with_name_only(self, planner):
        planner.jira.post.return_value = {"id": 11, "name": "Solo", "isPublic": True}

        team = planner.create_team("Solo")

        _, kwargs = planner.jira.post.call_args
        assert "summary" not in kwargs["data"]
        assert "lead" not in kwargs["data"]
        assert team.name == "Solo"

    def test_re_raises_on_error(self, planner):
        planner.jira.post.side_effect = RuntimeError("forbidden")

        with pytest.raises(RuntimeError):
            planner.create_team("BadTeam")


class TestGetTeamRoles:
    def test_returns_roles(self, planner):
        planner.jira.get.return_value = [
            {"id": 1, "name": "Developer"},
            {"id": 2, "name": "Tester"},
        ]

        roles = planner.get_team_roles()

        planner.jira.get.assert_called_once_with("rest/tempo-teams/2/role")
        assert len(roles) == 2
        assert all(isinstance(r, TempoTeamRole) for r in roles)
        assert roles[0].name == "Developer"

    def test_returns_empty_list_on_error(self, planner):
        planner.jira.get.side_effect = RuntimeError("oops")

        assert planner.get_team_roles() == []


# ---------------------------------------------------------------------------
# Team member tests
# ---------------------------------------------------------------------------


class TestGetTeamMembers:
    def test_returns_members(self, planner):
        planner.jira.get.return_value = [
            {
                "id": 42,
                "member": {"name": "jdoe", "type": "USER", "displayName": "John Doe"},
                "membership": {"availability": 80, "status": "ACTIVE"},
            }
        ]

        members = planner.get_team_members(3)

        planner.jira.get.assert_called_once_with(
            "rest/tempo-teams/2/team/3/member",
            params={"onlyActive": "true"},
        )
        assert len(members) == 1
        assert isinstance(members[0], TempoTeamMember)
        assert members[0].member_key == "jdoe"

    def test_passes_optional_params(self, planner):
        planner.jira.get.return_value = []

        planner.get_team_members(3, member_type="GROUP", only_active=False)

        _, kwargs = planner.jira.get.call_args
        assert kwargs["params"]["type"] == "GROUP"
        assert kwargs["params"]["onlyActive"] == "false"

    def test_returns_empty_list_on_error(self, planner):
        planner.jira.get.side_effect = RuntimeError("network error")

        assert planner.get_team_members(3) == []


class TestAddTeamMember:
    def test_adds_member_with_defaults(self, planner):
        planner.jira.post.return_value = {
            "id": 99,
            "member": {"name": "jsmith", "type": "USER", "displayName": "Jane Smith"},
            "membership": {"availability": 100, "status": "ACTIVE"},
        }

        member = planner.add_team_member(3, "jsmith")

        planner.jira.post.assert_called_once_with(
            "rest/tempo-teams/2/team/3/member",
            data={
                "member": {"name": "jsmith", "type": "USER"},
                "membership": {"availability": 100},
            },
        )
        assert member.member_key == "jsmith"

    def test_adds_member_with_all_options(self, planner):
        planner.jira.post.return_value = {
            "id": 100,
            "member": {"name": "grp1", "type": "GROUP", "displayName": "Group One"},
            "membership": {
                "role": {"name": "Dev"},
                "availability": 50,
                "dateFrom": "2026-01-01",
                "dateTo": "2026-06-30",
                "status": "ACTIVE",
            },
        }

        member = planner.add_team_member(
            3, "grp1", member_type="GROUP", role_id=2, availability=50,
            date_from="2026-01-01", date_to="2026-06-30"
        )

        _, kwargs = planner.jira.post.call_args
        assert kwargs["data"]["membership"]["role"] == {"id": 2}
        assert kwargs["data"]["membership"]["dateFrom"] == "2026-01-01"
        assert member.availability == 50

    def test_re_raises_on_error(self, planner):
        planner.jira.post.side_effect = RuntimeError("bad request")

        with pytest.raises(RuntimeError):
            planner.add_team_member(3, "jdoe")


class TestUpdateTeamMember:
    def test_updates_with_provided_fields(self, planner):
        planner.jira.put.return_value = {
            "id": 42,
            "member": {"name": "jdoe", "type": "USER", "displayName": "John Doe"},
            "membership": {"availability": 60, "status": "ACTIVE"},
        }

        member = planner.update_team_member(3, 42, availability=60)

        planner.jira.put.assert_called_once_with(
            "rest/tempo-teams/2/team/3/member/42",
            data={"membership": {"availability": 60}},
        )
        assert member.availability == 60

    def test_sends_only_provided_fields(self, planner):
        planner.jira.put.return_value = {
            "id": 42,
            "member": {"name": "jdoe", "type": "USER", "displayName": "John Doe"},
            "membership": {"availability": 100, "status": "ACTIVE"},
        }

        planner.update_team_member(3, 42, role_id=5, date_from="2026-03-01")

        _, kwargs = planner.jira.put.call_args
        membership = kwargs["data"]["membership"]
        assert membership["role"] == {"id": 5}
        assert membership["dateFrom"] == "2026-03-01"
        assert "availability" not in membership

    def test_re_raises_on_error(self, planner):
        planner.jira.put.side_effect = RuntimeError("server error")

        with pytest.raises(RuntimeError):
            planner.update_team_member(3, 42, availability=50)


class TestRemoveTeamMember:
    def test_calls_delete(self, planner):
        planner.jira.delete.return_value = None

        planner.remove_team_member(3, 42)

        planner.jira.delete.assert_called_once_with(
            "rest/tempo-teams/2/team/3/member/42"
        )

    def test_re_raises_on_error(self, planner):
        planner.jira.delete.side_effect = RuntimeError("forbidden")

        with pytest.raises(RuntimeError):
            planner.remove_team_member(3, 42)


# ---------------------------------------------------------------------------
# Allocation tests
# ---------------------------------------------------------------------------


class TestSearchAllocations:
    def test_returns_allocations_with_no_filters(self, planner):
        planner.jira.get.return_value = [
            {
                "id": 1,
                "assignee": {"key": "jdoe", "type": "USER"},
                "planItem": {"id": 10, "type": "ISSUE"},
                "commitment": 28800,
                "secondsPerDay": 28800,
                "startDate": "2026-01-01",
                "endDate": "2026-01-31",
            }
        ]

        allocations = planner.search_allocations()

        planner.jira.get.assert_called_once_with(
            "rest/tempo-planning/1/allocation", params=None
        )
        assert len(allocations) == 1
        assert isinstance(allocations[0], TempoAllocation)
        assert allocations[0].assignee_key == "jdoe"

    def test_passes_filters_as_params(self, planner):
        planner.jira.get.return_value = []

        planner.search_allocations(
            assignee_keys=["jdoe", "jsmith"],
            assignee_type="USER",
            plan_item_id=10,
            plan_item_type="ISSUE",
            start_date="2026-01-01",
            end_date="2026-12-31",
        )

        _, kwargs = planner.jira.get.call_args
        params = kwargs["params"]
        assert params["assigneeKey"] == "jdoe,jsmith"
        assert params["assigneeType"] == "USER"
        assert params["planItemId"] == 10
        assert params["planItemType"] == "ISSUE"
        assert params["from"] == "2026-01-01"
        assert params["to"] == "2026-12-31"

    def test_returns_empty_list_on_error(self, planner):
        planner.jira.get.side_effect = RuntimeError("timeout")

        assert planner.search_allocations() == []


class TestCreateAllocation:
    def test_creates_allocation_with_required_fields(self, planner):
        planner.jira.post.return_value = {
            "id": 55,
            "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 10, "type": "ISSUE"},
            "commitment": 28800,
            "secondsPerDay": 28800,
            "startDate": "2026-01-01",
            "endDate": "2026-01-31",
        }

        allocation = planner.create_allocation(
            assignee_key="jdoe",
            assignee_type="USER",
            plan_item_id=10,
            plan_item_type="ISSUE",
            commitment=28800,
            seconds_per_day=28800,
            start="2026-01-01",
            end="2026-01-31",
        )

        planner.jira.post.assert_called_once_with(
            "rest/tempo-planning/1/allocation",
            data={
                "assignee": {"key": "jdoe", "type": "USER"},
                "planItem": {"id": 10, "type": "ISSUE"},
                "commitment": 28800,
                "secondsPerDay": 28800,
                "start": "2026-01-01",
                "end": "2026-01-31",
                "includeNonWorkingDays": False,
            },
        )
        assert isinstance(allocation, TempoAllocation)
        assert allocation.id == 55

    def test_includes_optional_description(self, planner):
        planner.jira.post.return_value = {
            "id": 56,
            "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 10, "type": "ISSUE"},
            "commitment": 0,
            "secondsPerDay": 0,
            "startDate": "2026-01-01",
            "endDate": "2026-01-31",
            "description": "Sprint work",
        }

        planner.create_allocation(
            assignee_key="jdoe",
            assignee_type="USER",
            plan_item_id=10,
            plan_item_type="ISSUE",
            commitment=0,
            seconds_per_day=0,
            start="2026-01-01",
            end="2026-01-31",
            description="Sprint work",
            include_non_working_days=True,
        )

        _, kwargs = planner.jira.post.call_args
        assert kwargs["data"]["description"] == "Sprint work"
        assert kwargs["data"]["includeNonWorkingDays"] is True

    def test_re_raises_on_error(self, planner):
        planner.jira.post.side_effect = RuntimeError("bad data")

        with pytest.raises(RuntimeError):
            planner.create_allocation(
                "jdoe", "USER", 1, "ISSUE", 0, 0, "2026-01-01", "2026-01-31"
            )


class TestUpdateAllocation:
    def test_updates_provided_fields(self, planner):
        planner.jira.put.return_value = {
            "id": 55,
            "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 10, "type": "ISSUE"},
            "commitment": 14400,
            "secondsPerDay": 14400,
            "startDate": "2026-02-01",
            "endDate": "2026-02-28",
        }

        allocation = planner.update_allocation(
            55, commitment=14400, seconds_per_day=14400,
            start="2026-02-01", end="2026-02-28"
        )

        planner.jira.put.assert_called_once_with(
            "rest/tempo-planning/1/allocation/55",
            data={
                "commitment": 14400,
                "secondsPerDay": 14400,
                "start": "2026-02-01",
                "end": "2026-02-28",
            },
        )
        assert allocation.commitment == 14400

    def test_sends_only_provided_fields(self, planner):
        planner.jira.put.return_value = {
            "id": 55,
            "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 10, "type": "ISSUE"},
            "commitment": 0,
            "secondsPerDay": 0,
            "startDate": "",
            "endDate": "",
        }

        planner.update_allocation(55, description="updated desc")

        _, kwargs = planner.jira.put.call_args
        body = kwargs["data"]
        assert "description" in body
        assert "commitment" not in body
        assert "start" not in body

    def test_re_raises_on_error(self, planner):
        planner.jira.put.side_effect = RuntimeError("not found")

        with pytest.raises(RuntimeError):
            planner.update_allocation(55, commitment=100)


class TestDeleteAllocation:
    def test_calls_delete(self, planner):
        planner.jira.delete.return_value = None

        planner.delete_allocation(55)

        planner.jira.delete.assert_called_once_with(
            "rest/tempo-planning/1/allocation/55"
        )

    def test_re_raises_on_error(self, planner):
        planner.jira.delete.side_effect = RuntimeError("forbidden")

        with pytest.raises(RuntimeError):
            planner.delete_allocation(55)
