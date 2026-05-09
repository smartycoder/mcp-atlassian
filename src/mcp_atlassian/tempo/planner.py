"""Tempo Planner mixin — teams, members, and allocations."""

import logging
from typing import Any

from requests.exceptions import HTTPError

from mcp_atlassian.models.tempo.planner import (
    TempoAllocation,
    TempoTeam,
    TempoTeamMember,
    TempoTeamRole,
)

from .client import TempoClient

logger = logging.getLogger("mcp-tempo")

# Tempo REST API base paths
_TEAMS_BASE = "rest/tempo-teams/2"
_PLANNING_BASE = "rest/tempo-planning/1"


class TempoPlannerMixin(TempoClient):
    """Mixin providing Tempo Planner operations: teams, members, and allocations.

    All read operations return an empty list (and log a warning) on error.
    All write operations log the error and re-raise the exception.
    """

    # ------------------------------------------------------------------
    # Team methods
    # ------------------------------------------------------------------

    def get_teams(self, expand: str | None = None) -> list[TempoTeam]:
        """Return all Tempo Planner teams.

        Args:
            expand: Optional comma-separated list of fields to expand.

        Returns:
            A list of TempoTeam instances; empty list on error.
        """
        params: dict[str, Any] = {}
        if expand is not None:
            params["expand"] = expand

        try:
            data = self.jira.get(f"{_TEAMS_BASE}/team", params=params or None)
            logger.info("Tempo get_teams raw response type=%s, data=%s", type(data).__name__, str(data)[:500])
            if not isinstance(data, list):
                data = data.get("teams", []) if isinstance(data, dict) else []
            return [TempoTeam.from_api_response(item) for item in data]
        except Exception as exc:
            logger.warning("Failed to fetch Tempo teams: %s", exc)
            return []

    def get_team(self, team_id: int) -> TempoTeam:
        """Return a single Tempo Planner team by ID.

        Args:
            team_id: The numeric identifier of the team.

        Returns:
            A TempoTeam instance.

        Raises:
            ValueError: If the team is not found (404).
            Exception: For any other error from the upstream API.
        """
        try:
            data = self.jira.get(f"{_TEAMS_BASE}/team/{team_id}")
            return TempoTeam.from_api_response(data)
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise ValueError(f"Tempo team {team_id} not found") from exc
            logger.error("Failed to fetch Tempo team %s: %s", team_id, exc)
            raise

    def create_team(
        self,
        name: str,
        summary: str | None = None,
        lead_user_key: str | None = None,
    ) -> TempoTeam:
        """Create a new Tempo Planner team.

        Args:
            name: The display name for the team.
            summary: Optional short description of the team.
            lead_user_key: Optional Jira user key of the team lead.

        Returns:
            The created TempoTeam instance.

        Raises:
            Exception: On any upstream API error.
        """
        body: dict[str, Any] = {"name": name}
        if summary is not None:
            body["summary"] = summary
        if lead_user_key is not None:
            body["lead"] = {"key": lead_user_key}

        try:
            data = self.jira.post(f"{_TEAMS_BASE}/team", data=body)
            return TempoTeam.from_api_response(data)
        except Exception as exc:
            logger.error("Failed to create Tempo team '%s': %s", name, exc)
            raise

    def get_team_roles(self) -> list[TempoTeamRole]:
        """Return all configured Tempo Planner team roles.

        Returns:
            A list of TempoTeamRole instances; empty list on error.
        """
        try:
            data = self.jira.get(f"{_TEAMS_BASE}/role")
            if not isinstance(data, list):
                data = data.get("roles", []) if isinstance(data, dict) else []
            return [TempoTeamRole.from_api_response(item) for item in data]
        except Exception as exc:
            logger.warning("Failed to fetch Tempo team roles: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Team member methods
    # ------------------------------------------------------------------

    def get_team_members(
        self,
        team_id: int,
        member_type: str | None = None,
        only_active: bool = True,
    ) -> list[TempoTeamMember]:
        """Return all members of a Tempo Planner team.

        Args:
            team_id: The numeric identifier of the team.
            member_type: Optional filter — ``USER``, ``GROUP``, or ``GROUP_USER``.
            only_active: When True (default), only active memberships are returned.

        Returns:
            A list of TempoTeamMember instances; empty list on error.
        """
        params: dict[str, Any] = {"onlyActive": str(only_active).lower()}
        if member_type is not None:
            params["type"] = member_type

        try:
            data = self.jira.get(
                f"{_TEAMS_BASE}/team/{team_id}/member", params=params
            )
            if not isinstance(data, list):
                data = data.get("members", []) if isinstance(data, dict) else []
            return [TempoTeamMember.from_api_response(item) for item in data]
        except Exception as exc:
            logger.warning(
                "Failed to fetch members for Tempo team %s: %s", team_id, exc
            )
            return []

    def add_team_member(
        self,
        team_id: int,
        member_key: str,
        member_type: str = "USER",
        role_id: int | None = None,
        availability: int = 100,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> TempoTeamMember:
        """Add a member to a Tempo Planner team.

        Args:
            team_id: The numeric identifier of the team.
            member_key: The Jira user key (or group key) to add.
            member_type: Member type — ``USER`` (default), ``GROUP``, or ``GROUP_USER``.
            role_id: Optional numeric role ID to assign.
            availability: Percentage availability (0–100); defaults to 100.
            date_from: Optional membership start date (``YYYY-MM-DD``).
            date_to: Optional membership end date (``YYYY-MM-DD``).

        Returns:
            The created TempoTeamMember instance.

        Raises:
            Exception: On any upstream API error.
        """
        membership: dict[str, Any] = {"availability": availability}
        if role_id is not None:
            membership["role"] = {"id": role_id}
        if date_from is not None:
            membership["dateFrom"] = date_from
        if date_to is not None:
            membership["dateTo"] = date_to

        body: dict[str, Any] = {
            "member": {"name": member_key, "type": member_type},
            "membership": membership,
        }

        try:
            data = self.jira.post(
                f"{_TEAMS_BASE}/team/{team_id}/member", data=body
            )
            return TempoTeamMember.from_api_response(data)
        except Exception as exc:
            logger.error(
                "Failed to add member '%s' to Tempo team %s: %s",
                member_key,
                team_id,
                exc,
            )
            raise

    def update_team_member(
        self,
        team_id: int,
        member_id: int,
        role_id: int | None = None,
        availability: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> TempoTeamMember:
        """Update an existing team member's membership details.

        Args:
            team_id: The numeric identifier of the team.
            member_id: The numeric identifier of the membership record.
            role_id: Optional new role ID.
            availability: Optional new availability percentage.
            date_from: Optional new membership start date (``YYYY-MM-DD``).
            date_to: Optional new membership end date (``YYYY-MM-DD``).

        Returns:
            The updated TempoTeamMember instance.

        Raises:
            Exception: On any upstream API error.
        """
        membership: dict[str, Any] = {}
        if role_id is not None:
            membership["role"] = {"id": role_id}
        if availability is not None:
            membership["availability"] = availability
        if date_from is not None:
            membership["dateFrom"] = date_from
        if date_to is not None:
            membership["dateTo"] = date_to

        body: dict[str, Any] = {"membership": membership}

        try:
            data = self.jira.put(
                f"{_TEAMS_BASE}/team/{team_id}/member/{member_id}", data=body
            )
            return TempoTeamMember.from_api_response(data)
        except Exception as exc:
            logger.error(
                "Failed to update member %s in Tempo team %s: %s",
                member_id,
                team_id,
                exc,
            )
            raise

    def remove_team_member(self, team_id: int, member_id: int) -> None:
        """Remove a member from a Tempo Planner team.

        Args:
            team_id: The numeric identifier of the team.
            member_id: The numeric identifier of the membership record.

        Raises:
            Exception: On any upstream API error.
        """
        try:
            self.jira.delete(f"{_TEAMS_BASE}/team/{team_id}/member/{member_id}")
        except Exception as exc:
            logger.error(
                "Failed to remove member %s from Tempo team %s: %s",
                member_id,
                team_id,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Allocation methods
    # ------------------------------------------------------------------

    def search_allocations(
        self,
        assignee_keys: list[str] | None = None,
        assignee_type: str | None = None,
        plan_item_id: int | None = None,
        plan_item_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[TempoAllocation]:
        """Search Tempo Planner allocations with optional filters.

        Args:
            assignee_keys: Optional list of Jira user/team keys to filter by.
            assignee_type: Optional assignee type — ``USER`` or ``TEAM``.
            plan_item_id: Optional plan item ID to filter by.
            plan_item_type: Optional plan item type — e.g. ``ISSUE``, ``PROJECT``.
            start_date: Optional range start date (``YYYY-MM-DD``).
            end_date: Optional range end date (``YYYY-MM-DD``).

        Returns:
            A list of TempoAllocation instances; empty list on error.
        """
        params: dict[str, Any] = {}
        if assignee_keys:
            params["assigneeKey"] = ",".join(assignee_keys)
        if assignee_type is not None:
            params["assigneeType"] = assignee_type
        if plan_item_id is not None:
            params["planItemId"] = plan_item_id
        if plan_item_type is not None:
            params["planItemType"] = plan_item_type
        if start_date is not None:
            params["from"] = start_date
        if end_date is not None:
            params["to"] = end_date

        try:
            data = self.jira.get(
                f"{_PLANNING_BASE}/allocation", params=params or None
            )
            if not isinstance(data, list):
                data = data.get("allocations", []) if isinstance(data, dict) else []
            return [TempoAllocation.from_api_response(item) for item in data]
        except Exception as exc:
            logger.warning("Failed to search Tempo allocations: %s", exc)
            return []

    def create_allocation(
        self,
        assignee_key: str,
        assignee_type: str,
        plan_item_id: int,
        plan_item_type: str,
        commitment: int,
        seconds_per_day: int,
        start: str,
        end: str,
        description: str | None = None,
        include_non_working_days: bool = False,
    ) -> TempoAllocation:
        """Create a new Tempo Planner allocation.

        Args:
            assignee_key: Jira user or team key.
            assignee_type: Assignee type — ``USER`` or ``TEAM``.
            plan_item_id: Numeric ID of the plan item (issue, project, etc.).
            plan_item_type: Plan item type — e.g. ``ISSUE``, ``PROJECT``, ``EPIC``.
            commitment: Total committed seconds for the allocation.
            seconds_per_day: Daily seconds allocated.
            start: Start date in ``YYYY-MM-DD`` format.
            end: End date in ``YYYY-MM-DD`` format.
            description: Optional description.
            include_non_working_days: Whether to include non-working days; defaults to False.

        Returns:
            The created TempoAllocation instance.

        Raises:
            Exception: On any upstream API error.
        """
        body: dict[str, Any] = {
            "assignee": {"key": assignee_key, "type": assignee_type},
            "planItem": {"id": plan_item_id, "type": plan_item_type},
            "commitment": commitment,
            "secondsPerDay": seconds_per_day,
            "start": start,
            "end": end,
            "includeNonWorkingDays": include_non_working_days,
        }
        if description is not None:
            body["description"] = description

        try:
            data = self.jira.post(f"{_PLANNING_BASE}/allocation", data=body)
            return TempoAllocation.from_api_response(data)
        except Exception as exc:
            logger.error("Failed to create Tempo allocation: %s", exc)
            raise

    def update_allocation(
        self,
        allocation_id: int,
        commitment: int | None = None,
        seconds_per_day: int | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        include_non_working_days: bool | None = None,
    ) -> TempoAllocation:
        """Update an existing Tempo Planner allocation.

        Only fields that are explicitly provided (non-None) are sent in the
        request body.

        Args:
            allocation_id: The numeric ID of the allocation to update.
            commitment: Optional new total committed seconds.
            seconds_per_day: Optional new daily seconds.
            start: Optional new start date (``YYYY-MM-DD``).
            end: Optional new end date (``YYYY-MM-DD``).
            description: Optional new description.
            include_non_working_days: Optional flag for non-working days.

        Returns:
            The updated TempoAllocation instance.

        Raises:
            Exception: On any upstream API error.
        """
        body: dict[str, Any] = {}
        if commitment is not None:
            body["commitment"] = commitment
        if seconds_per_day is not None:
            body["secondsPerDay"] = seconds_per_day
        if start is not None:
            body["start"] = start
        if end is not None:
            body["end"] = end
        if description is not None:
            body["description"] = description
        if include_non_working_days is not None:
            body["includeNonWorkingDays"] = include_non_working_days

        try:
            data = self.jira.put(
                f"{_PLANNING_BASE}/allocation/{allocation_id}", data=body
            )
            return TempoAllocation.from_api_response(data)
        except Exception as exc:
            logger.error(
                "Failed to update Tempo allocation %s: %s", allocation_id, exc
            )
            raise

    def delete_allocation(self, allocation_id: int) -> None:
        """Delete a Tempo Planner allocation.

        Args:
            allocation_id: The numeric ID of the allocation to delete.

        Raises:
            Exception: On any upstream API error.
        """
        try:
            self.jira.delete(f"{_PLANNING_BASE}/allocation/{allocation_id}")
        except Exception as exc:
            logger.error(
                "Failed to delete Tempo allocation %s: %s", allocation_id, exc
            )
            raise
