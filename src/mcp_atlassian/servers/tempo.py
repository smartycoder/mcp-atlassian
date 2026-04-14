"""Tempo FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

from mcp_atlassian.servers.tempo_dependencies import get_tempo_fetcher
from mcp_atlassian.utils.decorators import check_write_access

logger = logging.getLogger(__name__)

tempo_mcp = FastMCP(
    name="Tempo MCP Service",
    description="Provides tools for interacting with Tempo Timesheets and Planner on Jira Data Center.",
)


# --- Worklog Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_search_worklogs(
    ctx: Context,
    date_from: Annotated[str, Field(description="Start date in ISO format (YYYY-MM-DD).")],
    date_to: Annotated[str, Field(description="End date in ISO format (YYYY-MM-DD).")],
    worker_keys: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of worker (user) keys to filter by.", default=None),
    ] = None,
    project_keys: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of project keys to filter by.", default=None),
    ] = None,
    team_ids: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of Tempo team IDs to filter by.", default=None),
    ] = None,
    epic_keys: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of epic issue keys to filter by.", default=None),
    ] = None,
    task_keys: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of task issue keys to filter by.", default=None),
    ] = None,
) -> str:
    """Search for Tempo worklogs matching the given date range and optional filters.

    Returns a JSON object with a list of matching worklogs and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        worklogs = tempo.search_worklogs(
            date_from=date_from,
            date_to=date_to,
            worker_keys=worker_keys.split(",") if worker_keys else None,
            project_keys=project_keys.split(",") if project_keys else None,
            team_ids=team_ids.split(",") if team_ids else None,
            epic_keys=epic_keys.split(",") if epic_keys else None,
            task_keys=task_keys.split(",") if task_keys else None,
        )
        return json.dumps(
            {
                "success": True,
                "worklogs": [w.to_simplified_dict() for w in worklogs],
                "count": len(worklogs),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_search_worklogs failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_worklog(
    ctx: Context,
    worklog_id: Annotated[int, Field(description="The Tempo worklog ID.")],
) -> str:
    """Retrieve a single Tempo worklog by its ID.

    Returns a JSON object containing the worklog details, or an error object if not found.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        worklog = tempo.get_worklog(worklog_id=worklog_id)
        return json.dumps(
            {"success": True, "worklog": worklog.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_worklog failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_create_worklog(
    ctx: Context,
    worker: Annotated[str, Field(description="The worker (user) key.")],
    issue_key: Annotated[str, Field(description="The Jira issue key (e.g. 'PROJ-123').")],
    started: Annotated[str, Field(description="The start date/time in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).")],
    time_spent_seconds: Annotated[int, Field(description="Time spent in seconds.", ge=1)],
    comment: Annotated[
        str | None,
        Field(description="(Optional) Free-text comment for the worklog.", default=None),
    ] = None,
    billable_seconds: Annotated[
        int | None,
        Field(description="(Optional) Billable time in seconds.", default=None),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="(Optional) End date for the worklog period (YYYY-MM-DD).", default=None),
    ] = None,
    include_non_working_days: Annotated[
        bool,
        Field(description="Whether to include non-working days. Defaults to false.", default=False),
    ] = False,
    remaining_estimate: Annotated[
        str | None,
        Field(description="(Optional) Remaining estimate string (e.g. '1h', '30m').", default=None),
    ] = None,
) -> str:
    """Create a new Tempo worklog entry for a Jira issue.

    Returns a JSON object with the created worklog details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        worklog = tempo.create_worklog(
            worker=worker,
            issue_key=issue_key,
            started=started,
            time_spent_seconds=time_spent_seconds,
            comment=comment,
            billable_seconds=billable_seconds,
            end_date=end_date,
            include_non_working_days=include_non_working_days,
            remaining_estimate=remaining_estimate,
        )
        return json.dumps(
            {"success": True, "worklog": worklog.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_create_worklog failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_update_worklog(
    ctx: Context,
    worklog_id: Annotated[int, Field(description="The Tempo worklog ID to update.")],
    started: Annotated[
        str | None,
        Field(description="(Optional) New start date/time in ISO format.", default=None),
    ] = None,
    time_spent_seconds: Annotated[
        int | None,
        Field(description="(Optional) New time spent in seconds.", default=None),
    ] = None,
    comment: Annotated[
        str | None,
        Field(description="(Optional) New comment text.", default=None),
    ] = None,
    billable_seconds: Annotated[
        int | None,
        Field(description="(Optional) New billable time in seconds.", default=None),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="(Optional) New end date (YYYY-MM-DD).", default=None),
    ] = None,
    include_non_working_days: Annotated[
        bool | None,
        Field(description="(Optional) Whether to include non-working days.", default=None),
    ] = None,
    remaining_estimate: Annotated[
        str | None,
        Field(description="(Optional) New remaining estimate string (e.g. '1h').", default=None),
    ] = None,
) -> str:
    """Update an existing Tempo worklog entry. Only provided fields are updated.

    Returns a JSON object with the updated worklog details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        worklog = tempo.update_worklog(
            worklog_id=worklog_id,
            started=started,
            time_spent_seconds=time_spent_seconds,
            comment=comment,
            billable_seconds=billable_seconds,
            end_date=end_date,
            include_non_working_days=include_non_working_days,
            remaining_estimate=remaining_estimate,
        )
        return json.dumps(
            {"success": True, "worklog": worklog.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_update_worklog failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_delete_worklog(
    ctx: Context,
    worklog_id: Annotated[int, Field(description="The Tempo worklog ID to delete.")],
) -> str:
    """Delete a Tempo worklog entry by its ID.

    Returns a JSON object confirming deletion or describing any error.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        tempo.delete_worklog(worklog_id=worklog_id)
        return json.dumps(
            {"success": True, "deleted_worklog_id": worklog_id},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_delete_worklog failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Approval Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_approval_status(
    ctx: Context,
    user_key: Annotated[str, Field(description="The Jira user key of the timesheet owner.")],
    period_start_date: Annotated[str, Field(description="The start date of the approval period (YYYY-MM-DD).")],
) -> str:
    """Retrieve the timesheet approval status for a user and period.

    Returns a JSON object with a list of approval records and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        approvals = tempo.get_approval_status(
            user_key=user_key,
            period_start_date=period_start_date,
        )
        return json.dumps(
            {
                "success": True,
                "approvals": [a.to_simplified_dict() for a in approvals],
                "count": len(approvals),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_approval_status failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_pending_approvals(
    ctx: Context,
    reviewer_key: Annotated[str, Field(description="The Jira user key of the reviewer.")],
) -> str:
    """Retrieve all pending timesheet approvals for a given reviewer.

    Returns a JSON object with a list of pending approval records and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        approvals = tempo.get_pending_approvals(reviewer_key=reviewer_key)
        return json.dumps(
            {
                "success": True,
                "approvals": [a.to_simplified_dict() for a in approvals],
                "count": len(approvals),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_pending_approvals failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_submit_approval(
    ctx: Context,
    user_key: Annotated[str, Field(description="The Jira user key of the timesheet owner.")],
    period_date_from: Annotated[str, Field(description="The start date of the approval period (YYYY-MM-DD).")],
    action: Annotated[str, Field(description="The action to perform (e.g. 'SUBMIT', 'APPROVE', 'REJECT').")],
    comment: Annotated[
        str | None,
        Field(description="(Optional) Comment accompanying the action.", default=None),
    ] = None,
    reviewer_key: Annotated[
        str | None,
        Field(description="(Optional) Jira user key of the reviewer.", default=None),
    ] = None,
) -> str:
    """Submit a timesheet approval action (submit, approve, or reject).

    Returns a JSON object with the resulting approval record.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        approval = tempo.submit_approval(
            user_key=user_key,
            period_date_from=period_date_from,
            action=action,
            comment=comment,
            reviewer_key=reviewer_key,
        )
        return json.dumps(
            {"success": True, "approval": approval.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_submit_approval failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Attribute / Schedule Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_work_attributes(ctx: Context) -> str:
    """Retrieve all Tempo work attribute definitions.

    Returns a JSON object with a list of work attributes and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        attributes = tempo.get_work_attributes()
        return json.dumps(
            {
                "success": True,
                "attributes": [a.to_simplified_dict() for a in attributes],
                "count": len(attributes),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_work_attributes failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_user_schedule(
    ctx: Context,
    user: Annotated[
        str | None,
        Field(description="(Optional) Jira user key; defaults to the authenticated user.", default=None),
    ] = None,
    date_from: Annotated[
        str | None,
        Field(description="(Optional) Start date of the schedule range (YYYY-MM-DD).", default=None),
    ] = None,
    date_to: Annotated[
        str | None,
        Field(description="(Optional) End date of the schedule range (YYYY-MM-DD).", default=None),
    ] = None,
) -> str:
    """Retrieve the Tempo work schedule for a user over an optional date range.

    Returns a JSON object with the user's schedule details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        schedule = tempo.get_user_schedule(user=user, date_from=date_from, date_to=date_to)
        return json.dumps(
            {"success": True, "schedule": schedule.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_user_schedule failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Team Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_teams(
    ctx: Context,
    expand: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of fields to expand (e.g. 'members,leads').", default=None),
    ] = None,
) -> str:
    """List all Tempo Planner teams.

    Returns a JSON object with a list of team records and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        teams = tempo.get_teams(expand=expand)
        return json.dumps(
            {
                "success": True,
                "teams": [t.to_simplified_dict() for t in teams],
                "count": len(teams),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_teams failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_team(
    ctx: Context,
    team_id: Annotated[int, Field(description="The numeric ID of the Tempo team.")],
) -> str:
    """Retrieve a single Tempo Planner team by its ID.

    Returns a JSON object with the team details, or an error object if not found.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        team = tempo.get_team(team_id=team_id)
        return json.dumps(
            {"success": True, "team": team.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_team failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_create_team(
    ctx: Context,
    name: Annotated[str, Field(description="The display name for the new team.")],
    summary: Annotated[
        str | None,
        Field(description="(Optional) Short description of the team.", default=None),
    ] = None,
    lead_user_key: Annotated[
        str | None,
        Field(description="(Optional) Jira user key of the team lead.", default=None),
    ] = None,
) -> str:
    """Create a new Tempo Planner team.

    Returns a JSON object with the created team details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        team = tempo.create_team(name=name, summary=summary, lead_user_key=lead_user_key)
        return json.dumps(
            {"success": True, "team": team.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_create_team failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_team_roles(ctx: Context) -> str:
    """Retrieve all configured Tempo Planner team roles.

    Returns a JSON object with a list of role records and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        roles = tempo.get_team_roles()
        return json.dumps(
            {
                "success": True,
                "roles": [r.to_simplified_dict() for r in roles],
                "count": len(roles),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_team_roles failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Team Member Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_team_members(
    ctx: Context,
    team_id: Annotated[int, Field(description="The numeric ID of the Tempo team.")],
    member_type: Annotated[
        str | None,
        Field(description="(Optional) Filter by member type: 'USER', 'GROUP', or 'GROUP_USER'.", default=None),
    ] = None,
    only_active: Annotated[
        bool,
        Field(description="When true (default), only active memberships are returned.", default=True),
    ] = True,
) -> str:
    """List all members of a Tempo Planner team.

    Returns a JSON object with a list of member records and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        members = tempo.get_team_members(
            team_id=team_id,
            member_type=member_type,
            only_active=only_active,
        )
        return json.dumps(
            {
                "success": True,
                "members": [m.to_simplified_dict() for m in members],
                "count": len(members),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_team_members failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_add_team_member(
    ctx: Context,
    team_id: Annotated[int, Field(description="The numeric ID of the Tempo team.")],
    member_key: Annotated[str, Field(description="The Jira user key (or group key) to add.")],
    member_type: Annotated[
        str,
        Field(description="Member type: 'USER' (default), 'GROUP', or 'GROUP_USER'.", default="USER"),
    ] = "USER",
    role_id: Annotated[
        int | None,
        Field(description="(Optional) Numeric role ID to assign to the member.", default=None),
    ] = None,
    availability: Annotated[
        int,
        Field(description="Percentage availability (0–100). Defaults to 100.", default=100, ge=0, le=100),
    ] = 100,
    date_from: Annotated[
        str | None,
        Field(description="(Optional) Membership start date (YYYY-MM-DD).", default=None),
    ] = None,
    date_to: Annotated[
        str | None,
        Field(description="(Optional) Membership end date (YYYY-MM-DD).", default=None),
    ] = None,
) -> str:
    """Add a member to a Tempo Planner team.

    Returns a JSON object with the created membership details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        member = tempo.add_team_member(
            team_id=team_id,
            member_key=member_key,
            member_type=member_type,
            role_id=role_id,
            availability=availability,
            date_from=date_from,
            date_to=date_to,
        )
        return json.dumps(
            {"success": True, "member": member.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_add_team_member failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_update_team_member(
    ctx: Context,
    team_id: Annotated[int, Field(description="The numeric ID of the Tempo team.")],
    member_id: Annotated[int, Field(description="The numeric ID of the membership record.")],
    role_id: Annotated[
        int | None,
        Field(description="(Optional) New role ID to assign.", default=None),
    ] = None,
    availability: Annotated[
        int | None,
        Field(description="(Optional) New availability percentage (0–100).", default=None),
    ] = None,
    date_from: Annotated[
        str | None,
        Field(description="(Optional) New membership start date (YYYY-MM-DD).", default=None),
    ] = None,
    date_to: Annotated[
        str | None,
        Field(description="(Optional) New membership end date (YYYY-MM-DD).", default=None),
    ] = None,
) -> str:
    """Update an existing team member's membership details. Only provided fields are updated.

    Returns a JSON object with the updated membership details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        member = tempo.update_team_member(
            team_id=team_id,
            member_id=member_id,
            role_id=role_id,
            availability=availability,
            date_from=date_from,
            date_to=date_to,
        )
        return json.dumps(
            {"success": True, "member": member.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_update_team_member failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_remove_team_member(
    ctx: Context,
    team_id: Annotated[int, Field(description="The numeric ID of the Tempo team.")],
    member_id: Annotated[int, Field(description="The numeric ID of the membership record to remove.")],
) -> str:
    """Remove a member from a Tempo Planner team.

    Returns a JSON object confirming removal or describing any error.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        tempo.remove_team_member(team_id=team_id, member_id=member_id)
        return json.dumps(
            {"success": True, "team_id": team_id, "removed_member_id": member_id},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_remove_team_member failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Allocation Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_search_allocations(
    ctx: Context,
    assignee_keys: Annotated[
        str | None,
        Field(description="(Optional) Comma-separated list of Jira user/team keys to filter by.", default=None),
    ] = None,
    assignee_type: Annotated[
        str | None,
        Field(description="(Optional) Assignee type filter: 'USER' or 'TEAM'.", default=None),
    ] = None,
    plan_item_id: Annotated[
        int | None,
        Field(description="(Optional) Plan item ID to filter by.", default=None),
    ] = None,
    plan_item_type: Annotated[
        str | None,
        Field(description="(Optional) Plan item type filter (e.g. 'ISSUE', 'PROJECT', 'EPIC').", default=None),
    ] = None,
    start_date: Annotated[
        str | None,
        Field(description="(Optional) Range start date (YYYY-MM-DD).", default=None),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="(Optional) Range end date (YYYY-MM-DD).", default=None),
    ] = None,
) -> str:
    """Search Tempo Planner allocations with optional filters.

    Returns a JSON object with a list of allocation records and a count.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        allocations = tempo.search_allocations(
            assignee_keys=assignee_keys.split(",") if assignee_keys else None,
            assignee_type=assignee_type,
            plan_item_id=plan_item_id,
            plan_item_type=plan_item_type,
            start_date=start_date,
            end_date=end_date,
        )
        return json.dumps(
            {
                "success": True,
                "allocations": [a.to_simplified_dict() for a in allocations],
                "count": len(allocations),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_search_allocations failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_create_allocation(
    ctx: Context,
    assignee_key: Annotated[str, Field(description="Jira user or team key for the assignee.")],
    assignee_type: Annotated[str, Field(description="Assignee type: 'USER' or 'TEAM'.")],
    plan_item_id: Annotated[int, Field(description="Numeric ID of the plan item (issue, project, etc.).")],
    plan_item_type: Annotated[str, Field(description="Plan item type: e.g. 'ISSUE', 'PROJECT', 'EPIC'.")],
    commitment: Annotated[int, Field(description="Total committed seconds for the allocation.", ge=0)],
    seconds_per_day: Annotated[int, Field(description="Daily seconds allocated.", ge=0)],
    start: Annotated[str, Field(description="Start date in YYYY-MM-DD format.")],
    end: Annotated[str, Field(description="End date in YYYY-MM-DD format.")],
    description: Annotated[
        str | None,
        Field(description="(Optional) Description of the allocation.", default=None),
    ] = None,
    include_non_working_days: Annotated[
        bool,
        Field(description="Whether to include non-working days. Defaults to false.", default=False),
    ] = False,
) -> str:
    """Create a new Tempo Planner allocation.

    Returns a JSON object with the created allocation details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        allocation = tempo.create_allocation(
            assignee_key=assignee_key,
            assignee_type=assignee_type,
            plan_item_id=plan_item_id,
            plan_item_type=plan_item_type,
            commitment=commitment,
            seconds_per_day=seconds_per_day,
            start=start,
            end=end,
            description=description,
            include_non_working_days=include_non_working_days,
        )
        return json.dumps(
            {"success": True, "allocation": allocation.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_create_allocation failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_update_allocation(
    ctx: Context,
    allocation_id: Annotated[int, Field(description="The numeric ID of the allocation to update.")],
    commitment: Annotated[
        int | None,
        Field(description="(Optional) New total committed seconds.", default=None),
    ] = None,
    seconds_per_day: Annotated[
        int | None,
        Field(description="(Optional) New daily seconds.", default=None),
    ] = None,
    start: Annotated[
        str | None,
        Field(description="(Optional) New start date (YYYY-MM-DD).", default=None),
    ] = None,
    end: Annotated[
        str | None,
        Field(description="(Optional) New end date (YYYY-MM-DD).", default=None),
    ] = None,
    description: Annotated[
        str | None,
        Field(description="(Optional) New description.", default=None),
    ] = None,
    include_non_working_days: Annotated[
        bool | None,
        Field(description="(Optional) Whether to include non-working days.", default=None),
    ] = None,
) -> str:
    """Update an existing Tempo Planner allocation. Only provided fields are updated.

    Returns a JSON object with the updated allocation details.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        allocation = tempo.update_allocation(
            allocation_id=allocation_id,
            commitment=commitment,
            seconds_per_day=seconds_per_day,
            start=start,
            end=end,
            description=description,
            include_non_working_days=include_non_working_days,
        )
        return json.dumps(
            {"success": True, "allocation": allocation.to_simplified_dict()},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_update_allocation failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_delete_allocation(
    ctx: Context,
    allocation_id: Annotated[int, Field(description="The numeric ID of the allocation to delete.")],
) -> str:
    """Delete a Tempo Planner allocation by its ID.

    Returns a JSON object confirming deletion or describing any error.
    """
    tempo = await get_tempo_fetcher(ctx)
    try:
        tempo.delete_allocation(allocation_id=allocation_id)
        return json.dumps(
            {"success": True, "deleted_allocation_id": allocation_id},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_delete_allocation failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
