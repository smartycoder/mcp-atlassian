# Jira Groups & Tempo MCP Server — Design Spec

**Date:** 2026-04-09
**Scope:** Jira Data Center only (not Cloud)
**Authentication:** Same Jira credentials (PAT / Basic auth) for all APIs
**API verification:** All Tempo endpoints verified against official OpenAPI specs at `apidocs.tempo.io/dc/public/`

## Overview

Two new feature areas for the mcp-atlassian project:

1. **Jira Groups** — 6 tools added to the existing Jira MCP server for managing Jira groups and their members
2. **Tempo MCP Server** — A new, separate MCP server with 22 tools for Tempo Timesheets and Tempo Planner

## Architecture Decision: Separate Tempo Server

Tempo tools are implemented as a **separate MCP server** rather than added to the existing Jira server. Reasons:

- The Jira server already has 33 tools; adding 28 more (61 total) degrades LLM tool selection accuracy
- With Groups added, Jira goes to 39 tools — still manageable
- Tempo is a plugin, not core Jira — logical separation
- Users who don't have Tempo can simply not enable the Tempo server

## Module Organization

### New package: `src/mcp_atlassian/tempo/`

Tempo gets its own top-level package, separate from `jira/`. Rationale: Tempo is a separate MCP server with its own API surface, having it under `jira/` would be confusing.

```
src/mcp_atlassian/tempo/
├── __init__.py          # TempoFetcher (composes all Tempo mixins)
├── client.py            # TempoClient base (wraps self.jira for Tempo API paths)
├── timesheets.py        # TempoTimesheetsMixin — worklogs, approvals
├── planner.py           # TempoPlannerMixin — teams, members, allocations
└── config.py            # TempoConfig (reuses Jira credentials + TEMPO_ENABLED flag)
```

### New files in `src/mcp_atlassian/jira/`

| File | Class | Domain |
|------|-------|--------|
| `groups.py` | `GroupsMixin(JiraClient)` | Jira Groups REST API (`/rest/api/2/group/...`) |

### New files in `src/mcp_atlassian/models/`

| File | Models |
|------|--------|
| `jira/group.py` | `JiraGroup`, `JiraGroupMember`, `JiraGroupMembersResult` |
| `tempo/__init__.py` | Package init |
| `tempo/timesheets.py` | `TempoWorklog`, `TempoApproval`, `TempoWorkAttribute`, `TempoUserSchedule` |
| `tempo/planner.py` | `TempoTeam`, `TempoTeamMember`, `TempoTeamRole`, `TempoAllocation` |

### Server files

| File | Server | Tool count |
|------|--------|------------|
| `servers/jira.py` | Existing `jira_mcp` — add 6 Groups tools | 39 total |
| `servers/tempo.py` | New `tempo_mcp` — Timesheets + Planner | 22 total |

### Composition

Groups mixin is added to `JiraFetcher` in `jira/__init__.py`:

```python
class JiraFetcher(
    ...,  # existing mixins
    GroupsMixin,
):
    pass
```

Tempo gets its own `TempoFetcher` in `tempo/__init__.py`:

```python
class TempoFetcher(
    TempoTimesheetsMixin,
    TempoPlannerMixin,
):
    pass
```

`TempoClient` (base class for Tempo mixins) wraps the same `atlassian.Jira` client instance to make HTTP calls to Tempo REST endpoints on the Jira DC URL.

### Server Registration and Service Detection

Tempo server is mounted via the existing pattern in `servers/main.py`:

```python
main_mcp.mount("tempo", tempo_mcp)
```

**Service detection** (`utils/environment.py`): Add `"tempo"` to `get_available_services()`. Tempo is enabled when:
1. Jira is configured (has `JIRA_URL` + valid auth), AND
2. `TEMPO_ENABLED=true` env variable is set (explicit opt-in, since not all Jira DC instances have Tempo)

**Lifespan handler** (`servers/main.py`): When Tempo is enabled, create `TempoConfig` from the same Jira env vars plus the `TEMPO_ENABLED` flag. Add `full_tempo_config` to `MainAppContext`.

**CLI** (`__init__.py`): Add `--tempo-enabled` flag that sets `TEMPO_ENABLED=true`.

**Tool filtering**: Tempo tools tagged with `{"tempo", "read"}` / `{"tempo", "write"}`. When Tempo is not enabled, these tools are excluded from tool listing (same pattern as other services).

### MCP Client Configuration

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "mcp-atlassian",
      "env": {
        "JIRA_URL": "https://jira.example.com",
        "JIRA_PERSONAL_TOKEN": "...",
        "TEMPO_ENABLED": "true"
      }
    }
  }
}
```

Single MCP server process — Tempo tools appear alongside Jira/Confluence/Bitbucket tools when enabled. The "separate server" refers to a separate `FastMCP` instance mounted under the `tempo` namespace, not a separate process.

---

## Part 1: Jira Groups Tools (6 tools)

Added to the existing Jira MCP server in `servers/jira.py`.

### API Base Path

`/rest/api/2/group/...` and `/rest/api/2/groups/...`

### Tools

#### 1. `jira_search_groups` (read)

Search groups by name substring.

- **API:** `GET /rest/api/2/groups/picker`
- **Parameters:**
  - `query: str` — search text (substring match)
  - `max_results: int = 50` — limit results
- **Returns:** List of `JiraGroup` (`name`, `html`)

#### 2. `jira_get_group_members` (read)

List members of a group with pagination.

- **API:** `GET /rest/api/2/group/member`
- **Parameters:**
  - `group_name: str` — exact group name (required)
  - `include_inactive: bool = False` — include inactive users
  - `start_at: int = 0` — pagination offset
  - `max_results: int = 50` — page size
- **Returns:** `JiraGroupMembersResult` containing list of `JiraGroupMember` plus pagination metadata (`total`, `start_at`, `max_results`, `is_last`)

#### 3. `jira_create_group` (write)

Create a new Jira group.

- **API:** `POST /rest/api/2/group`
- **Parameters:**
  - `name: str` — group name (required)
- **Returns:** Created group (`name`)
- **Requires:** Jira admin permissions

#### 4. `jira_delete_group` (write)

Delete a Jira group.

- **API:** `DELETE /rest/api/2/group`
- **Parameters:**
  - `group_name: str` — group to delete (required)
  - `swap_group: str | None = None` — transfer visibility restrictions to this group before deletion
- **Returns:** Success confirmation
- **Requires:** Jira admin permissions

#### 5. `jira_add_user_to_group` (write)

Add a user to a group.

- **API:** `POST /rest/api/2/group/user`
- **Parameters:**
  - `group_name: str` — target group (required)
  - `username: str` — user to add (DC uses `name` field, not `accountId`)
- **Returns:** Success confirmation
- **Note:** `group_name` parameter is case-sensitive on this endpoint

#### 6. `jira_remove_user_from_group` (write)

Remove a user from a group.

- **API:** `DELETE /rest/api/2/group/user`
- **Parameters:**
  - `group_name: str` — target group (required)
  - `username: str` — user to remove
- **Returns:** Success confirmation

### Groups Models

**`JiraGroup`:**

```python
class JiraGroup(ApiModel):
    name: str = EMPTY_STRING
    html: str | None = None
```

**`JiraGroupMember`:**

```python
class JiraGroupMember(ApiModel):
    key: str = EMPTY_STRING
    name: str = EMPTY_STRING
    display_name: str = EMPTY_STRING
    email: str | None = None
    active: bool = True
```

**`JiraGroupMembersResult`:**

```python
class JiraGroupMembersResult(ApiModel):
    members: list[JiraGroupMember] = []
    total: int = 0
    start_at: int = 0
    max_results: int = 50
    is_last: bool = True
```

All with `from_api_response()` and `to_simplified_dict()`.

---

## Part 2: Tempo Timesheets Tools (10 tools)

Registered in the new Tempo MCP server (`servers/tempo.py`).

### API Base Paths

- Timesheets: `/rest/tempo-timesheets/4/`
- Core: `/rest/tempo-core/1/`

### Worklog Tools (5)

#### 1. `tempo_search_worklogs` (read)

Search worklogs by date range and optional filters.

- **API:** `POST /rest/tempo-timesheets/4/worklogs/search`
- **Parameters:**
  - `date_from: str` — start date, yyyy-MM-dd (required)
  - `date_to: str` — end date, yyyy-MM-dd (required)
  - `worker_keys: list[str] | None = None` — filter by user keys
  - `project_keys: list[str] | None = None` — filter by project keys
  - `team_ids: list[int] | None = None` — filter by Tempo team IDs
  - `epic_keys: list[str] | None = None` — filter by epic keys
  - `task_keys: list[str] | None = None` — filter by issue keys
- **Request body mapping:** Parameters map directly to API body fields: `from`, `to`, `worker`, `projectKey`, `teamId`, `epicKey`, `taskKey`
- **Returns:** List of `TempoWorklog`

#### 2. `tempo_get_worklog` (read)

Get a single worklog by ID.

- **API:** `GET /rest/tempo-timesheets/4/worklogs/{worklog_id}`
- **Parameters:**
  - `worklog_id: int` — Tempo worklog ID (required)
- **Returns:** `TempoWorklog`

#### 3. `tempo_create_worklog` (write)

Create a Tempo worklog.

- **API:** `POST /rest/tempo-timesheets/4/worklogs`
- **Parameters:**
  - `worker: str` — user key (required)
  - `issue_key: str` — Jira issue key, maps to `originTaskId` (required)
  - `started: str` — start date, yyyy-MM-dd (required)
  - `time_spent_seconds: int` — time in seconds (required)
  - `comment: str | None = None`
  - `billable_seconds: int | None = None`
  - `end_date: str | None = None` — for multi-day worklogs
  - `include_non_working_days: bool = False`
  - `attributes: dict | None = None` — custom work attribute values
  - `remaining_estimate: int | None = None` — remaining estimate in seconds
- **Returns:** Created `TempoWorklog`

#### 4. `tempo_update_worklog` (write)

Update an existing Tempo worklog.

- **API:** `PUT /rest/tempo-timesheets/4/worklogs/{worklog_id}`
- **Parameters:**
  - `worklog_id: int` — Tempo worklog ID (required)
  - `started: str | None = None`
  - `time_spent_seconds: int | None = None`
  - `comment: str | None = None`
  - `billable_seconds: int | None = None`
  - `end_date: str | None = None`
  - `include_non_working_days: bool | None = None`
  - `attributes: dict | None = None`
  - `remaining_estimate: int | None = None`
- **Returns:** Updated `TempoWorklog`

#### 5. `tempo_delete_worklog` (write)

Delete a Tempo worklog.

- **API:** `DELETE /rest/tempo-timesheets/4/worklogs/{worklog_id}`
- **Parameters:**
  - `worklog_id: int` — Tempo worklog ID (required)
- **Returns:** Success confirmation (HTTP 204)

### Approval Tools (3)

#### 6. `tempo_get_approval_status` (read)

Get timesheet approval status for a user and period.

- **API:** `GET /rest/tempo-timesheets/4/timesheet-approval/current`
- **Verified:** Exists in OpenAPI spec as `getTimesheetApprovalsForUser_1`
- **Parameters:**
  - `user_key: str` — user key (required)
  - `period_start_date: str` — period start, yyyy-MM-dd (required)
- **Returns:** `TempoApproval` (`status`, `worked_seconds`, `submitted_seconds`, `required_seconds`, `user_key`, `period_start`, `period_end`, `reviewer_key`)
- **Status values:** `open`, `ready_to_submit`, `waiting_for_approval`, `approved`

#### 7. `tempo_get_pending_approvals` (read)

Get timesheets pending approval for a reviewer.

- **API:** `GET /rest/tempo-timesheets/4/timesheet-approval/pending`
- **Verified:** Exists in OpenAPI spec as `getTimesheetApprovalsForReviewer_1`
- **Parameters:**
  - `reviewer_key: str` — reviewer user key (required)
- **Returns:** List of `TempoApproval`

#### 8. `tempo_submit_approval` (write)

Submit, approve, reject, or reopen a timesheet.

- **API:** `POST /rest/tempo-timesheets/4/timesheet-approval`
- **Verified:** Exists in OpenAPI spec. Request body is `ApprovalInputBean`.
- **Parameters:**
  - `user_key: str` — target user key (required)
  - `period_date_from: str` — period start date (required)
  - `action: str` — one of: `submit`, `approve`, `reject`, `reopen` (required)
  - `comment: str | None = None`
  - `reviewer_key: str | None = None` — required for `submit` action
- **Request body mapping:**
  ```json
  {
    "user": {"key": "<user_key>"},
    "period": {"dateFrom": "<period_date_from>"},
    "action": {"name": "<action>", "comment": "<comment>", "reviewer": {"key": "<reviewer_key>"}}
  }
  ```
- **Returns:** Updated `TempoApproval`

### Work Attributes & Schedules (2)

#### 9. `tempo_get_work_attributes` (read)

List all configured work attributes.

- **API:** `GET /rest/tempo-core/1/work-attribute`
- **Parameters:** None
- **Returns:** List of `TempoWorkAttribute` (`id`, `name`, `type`, `required`)
- **Attribute types:** `ACCOUNT`, `BILLABLE_SECONDS`, `CHECKBOX`, `DYNAMIC_DROPDOWN`, `INPUT_FIELD`, `INPUT_NUMERIC`, `STATIC_LIST`

#### 10. `tempo_get_user_schedule` (read)

Get a user's work schedule (working days, required hours).

- **API:** `GET /rest/tempo-core/1/user/schedule`
- **Verified:** Exists in OpenAPI spec as `getUserSchedule`. All parameters optional (defaults to logged-in user and today).
- **Parameters:**
  - `user: str | None = None` — username (defaults to current user)
  - `date_from: str | None = None` — start date, yyyy-MM-dd
  - `date_to: str | None = None` — end date, yyyy-MM-dd
- **Returns:** `TempoUserSchedule` containing `number_of_working_days: int`, `required_seconds: int`, `days: list[TempoScheduleDay]`
- **Day types:** `WORKING_DAY`, `NON_WORKING_DAY`, `HOLIDAY`, `HOLIDAY_AND_NON_WORKING_DAY`

### Timesheets Models

**`TempoWorklog`:**

```python
class TempoWorklog(ApiModel):
    tempo_worklog_id: int = -1
    jira_worklog_id: int | None = None
    issue_key: str = EMPTY_STRING
    worker_key: str = EMPTY_STRING
    updater_key: str | None = None
    started: str = EMPTY_STRING
    time_spent_seconds: int = 0
    billable_seconds: int = 0
    comment: str | None = None
    attributes: dict[str, Any] | None = None
    created: str = EMPTY_STRING
    updated: str = EMPTY_STRING
```

**`TempoApproval`:**

```python
class TempoApproval(ApiModel):
    status: str = EMPTY_STRING  # open | ready_to_submit | waiting_for_approval | approved
    worked_seconds: int = 0
    submitted_seconds: int = 0
    required_seconds: int = 0
    user_key: str = EMPTY_STRING
    period_start: str = EMPTY_STRING
    period_end: str = EMPTY_STRING
    reviewer_key: str | None = None
```

**`TempoWorkAttribute`:**

```python
class TempoWorkAttribute(ApiModel):
    id: int = -1
    name: str = EMPTY_STRING
    type: str = EMPTY_STRING
    required: bool = False
```

**`TempoUserSchedule`:**

```python
class TempoScheduleDay(ApiModel):
    date: str = EMPTY_STRING
    required_seconds: int = 0
    type: str = EMPTY_STRING  # WORKING_DAY | NON_WORKING_DAY | HOLIDAY | HOLIDAY_AND_NON_WORKING_DAY
    holiday_name: str | None = None

class TempoUserSchedule(ApiModel):
    number_of_working_days: int = 0
    required_seconds: int = 0
    days: list[TempoScheduleDay] = []
```

---

## Part 3: Tempo Planner Tools (12 tools)

Registered in the Tempo MCP server (`servers/tempo.py`) alongside Timesheets tools.

### API Base Paths

- Teams: `/rest/tempo-teams/2/`
- Planning: `/rest/tempo-planning/1/`

### Team Tools (4)

#### 1. `tempo_get_teams` (read)

List all Tempo teams.

- **API:** `GET /rest/tempo-teams/2/team`
- **Parameters:**
  - `expand: str | None = None` — optional: `"leaduser"`, `"teamprogram"`, or both
- **Returns:** List of `TempoTeam`

#### 2. `tempo_get_team` (read)

Get a single team by ID.

- **API:** `GET /rest/tempo-teams/2/team/{team_id}`
- **Parameters:**
  - `team_id: int` — team ID (required)
- **Returns:** `TempoTeam`

#### 3. `tempo_create_team` (write)

Create a new Tempo team.

- **API:** `POST /rest/tempo-teams/2/team`
- **Parameters:**
  - `name: str` — team name (required)
  - `summary: str | None = None`
  - `lead_user_key: str | None = None` — team lead user key
- **Returns:** Created `TempoTeam`

#### 4. `tempo_get_team_roles` (read)

List all available team roles.

- **API:** `GET /rest/tempo-teams/2/role`
- **Parameters:** None
- **Returns:** List of `TempoTeamRole` (`id`, `name`)

### Team Member Tools (4)

#### 5. `tempo_get_team_members` (read)

List members of a team.

- **API:** `GET /rest/tempo-teams/2/team/{team_id}/member`
- **Parameters:**
  - `team_id: int` — team ID (required)
  - `member_type: str | None = None` — `"USER"` or `"GROUP"` filter
  - `only_active: bool = True`
- **Returns:** List of `TempoTeamMember`
- **Note:** Members can be of type `USER`, `GROUP`, or `GROUP_USER` (users inherited from group membership)

#### 6. `tempo_add_team_member` (write)

Add a member (user or group) to a team.

- **API:** `POST /rest/tempo-teams/2/team/{team_id}/member`
- **Verified:** Single endpoint handles both USER and GROUP via `member.type` field in request body
- **Parameters:**
  - `team_id: int` — team ID (required)
  - `member_key: str` — user key or group name (required)
  - `member_type: str = "USER"` — `"USER"` or `"GROUP"`
  - `role_id: int | None = None` — team role ID
  - `availability: int = 100` — availability percentage (0-100)
  - `date_from: str | None = None` — membership start date
  - `date_to: str | None = None` — membership end date
- **Request body mapping:**
  ```json
  {
    "member": {"name": "<member_key>", "type": "<member_type>"},
    "membership": {"role": {"id": "<role_id>"}, "dateFrom": "...", "dateTo": "...", "availability": 100}
  }
  ```
- **Returns:** Created `TempoTeamMember`

#### 7. `tempo_update_team_member` (write)

Update a team membership.

- **API:** `PUT /rest/tempo-teams/2/team/{team_id}/member/{member_id}`
- **Parameters:**
  - `team_id: int` — team ID (required)
  - `member_id: int` — membership ID (required)
  - `role_id: int | None = None`
  - `availability: int | None = None`
  - `date_from: str | None = None`
  - `date_to: str | None = None`
- **Returns:** Updated `TempoTeamMember`

#### 8. `tempo_remove_team_member` (write)

Remove a member from a team.

- **API:** `DELETE /rest/tempo-teams/2/team/{team_id}/member/{member_id}`
- **Parameters:**
  - `team_id: int` — team ID (required)
  - `member_id: int` — membership ID (required)
- **Returns:** Success confirmation

### Allocation Tools (4)

#### 9. `tempo_search_allocations` (read)

Search allocations by filters.

- **API:** `GET /rest/tempo-planning/1/allocation`
- **Parameters:**
  - `assignee_keys: list[str] | None = None` — filter by user keys
  - `assignee_type: str | None = None` — `"USER"` or `"TEAM"`
  - `plan_item_id: int | None = None`
  - `plan_item_type: str | None = None`
  - `start_date: str | None = None` — yyyy-MM-dd
  - `end_date: str | None = None` — yyyy-MM-dd
- **Returns:** List of `TempoAllocation`

#### 10. `tempo_create_allocation` (write)

Create a resource allocation.

- **API:** `POST /rest/tempo-planning/1/allocation`
- **Verified:** Exists in OpenAPI spec as `postAllocation`
- **Parameters:**
  - `assignee_key: str` — user key or team ID (required)
  - `assignee_type: str` — `"USER"` or `"TEAM"` (required)
  - `plan_item_id: int` — issue/project/epic ID (required)
  - `plan_item_type: str` — one of: `ISSUE`, `PROJECT`, `EPIC`, `SPRINT`, `VERSION`, `COMPONENT` (required)
  - `commitment: int` — percentage 1-100 (required)
  - `seconds_per_day: int` — planned seconds per day (required)
  - `start: str` — start date, yyyy-MM-dd (required)
  - `end: str` — end date, yyyy-MM-dd (required)
  - `description: str | None = None`
  - `include_non_working_days: bool = False`
- **Returns:** Created `TempoAllocation`

#### 11. `tempo_update_allocation` (write)

Update an existing allocation.

- **API:** `PUT /rest/tempo-planning/1/allocation/{allocation_id}`
- **Verified:** Exists in OpenAPI spec as `updateAllocation`
- **Parameters:**
  - `allocation_id: int` — allocation ID (required)
  - `commitment: int | None = None`
  - `seconds_per_day: int | None = None`
  - `start: str | None = None`
  - `end: str | None = None`
  - `description: str | None = None`
  - `include_non_working_days: bool | None = None`
- **Returns:** Updated `TempoAllocation`

#### 12. `tempo_delete_allocation` (write)

Delete an allocation.

- **API:** `DELETE /rest/tempo-planning/1/allocation/{allocation_id}`
- **Verified:** Exists in OpenAPI spec as `deleteAllocation`, returns 204
- **Parameters:**
  - `allocation_id: int` — allocation ID (required)
- **Returns:** Success confirmation (HTTP 204)

### Planner Models

**`TempoTeam`:**

```python
class TempoTeam(ApiModel):
    id: int = -1
    name: str = EMPTY_STRING
    summary: str | None = None
    lead_key: str | None = None
    is_public: bool = True
```

**`TempoTeamRole`:**

```python
class TempoTeamRole(ApiModel):
    id: int = -1
    name: str = EMPTY_STRING
```

**`TempoTeamMember`:**

```python
class TempoTeamMember(ApiModel):
    id: int = -1
    member_key: str = EMPTY_STRING
    member_type: str = "USER"  # USER | GROUP | GROUP_USER
    display_name: str = EMPTY_STRING
    role: str | None = None
    availability: int = 100
    date_from: str | None = None
    date_to: str | None = None
    status: str = EMPTY_STRING
```

**`TempoAllocation`:**

```python
class TempoAllocation(ApiModel):
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
```

---

## Error Handling

### Tempo Plugin Availability

Distinguish between different failure modes when calling Tempo endpoints:

| HTTP Status | Meaning | Handling |
|-------------|---------|----------|
| 404 on base path (e.g. `/rest/tempo-timesheets/4/` returns 404) | Tempo plugin not installed | Raise `TempoNotAvailableError("Tempo Timesheets plugin is not available on this Jira instance")` |
| 404 on specific resource (e.g. `/worklogs/999`) | Resource not found | Raise `ValueError("Worklog 999 not found")` |
| 401 | Authentication failed | Raise `MCPAtlassianAuthenticationError` |
| 403 | Tempo permission denied (e.g. viewing another user's worklogs) | Raise `MCPAtlassianAuthenticationError("Permission denied: ...")` |
| Other errors | Unexpected | `logger.error()`, re-raise with context |

Detection heuristic for "plugin not installed" vs "resource not found": If the 404 response body does not contain JSON or contains a generic Jira 404 page (not a Tempo error), it's likely a missing plugin. If it contains a Tempo-formatted error JSON, it's a resource not found.

### Standard Error Patterns

Following existing project conventions:

| Scenario | Handling |
|----------|----------|
| Read operations, resource not found | `logger.warning()`, return empty list/dict |
| Read operations, plugin missing or auth error | Raise specific exception (don't silently swallow) |
| Write operations, any failure | `logger.error()`, re-raise with context |
| Unexpected response type | `TypeError` with logging |

### Write Protection

All write tools decorated with `@check_write_access` — respects `READ_ONLY_MODE` env variable.

---

## Testing Strategy

### Test Files

| File | Coverage |
|------|----------|
| `tests/unit/jira/test_groups.py` | GroupsMixin methods |
| `tests/unit/tempo/test_timesheets.py` | TempoTimesheetsMixin methods |
| `tests/unit/tempo/test_planner.py` | TempoPlannerMixin methods |
| `tests/unit/models/jira/test_group_models.py` | JiraGroup, JiraGroupMember, JiraGroupMembersResult |
| `tests/unit/models/tempo/test_timesheets_models.py` | TempoWorklog, TempoApproval, TempoWorkAttribute, TempoUserSchedule |
| `tests/unit/models/tempo/test_planner_models.py` | TempoTeam, TempoTeamMember, TempoTeamRole, TempoAllocation |
| `tests/unit/servers/test_tempo_server.py` | Tempo server tool registration, tool filtering, service detection |

### Test Patterns

Following existing conventions:

- Session-scoped fixtures for mock data factories
- Function-scoped fixtures for mixin instances with mocked HTTP client
- Mock `self.jira.get()`, `self.jira.post()`, `self.jira.put()` responses
- Parametrized tests for error scenarios (404 plugin missing, 404 resource, 403 permission, invalid input)
- Test both happy path and edge cases (empty responses, malformed data)
- Server-level tests: verify tool registration, tag-based filtering, `TEMPO_ENABLED` gating

---

## Scope Exclusions

Explicitly not included in this design:

- **Jira Cloud support** — DC only, Cloud has different Tempo API
- **Tempo Accounts** — account management, rate tables, customers
- **Tempo Budgets** — cost tracking and budgeting
- **Tempo Expenses** — expense tracking
- **Work Attribute CRUD** — admin configuration, read-only access sufficient
- **Team Programs** — rarely used organizational grouping
- **Plan endpoints** (`/rest/tempo-planning/1/plan`) — day-level granularity planning; allocations cover the primary resource planning use case
- **Holiday/Workload scheme management** — admin configuration
- **Team permissions** — admin configuration

These can be added incrementally in future iterations.

---

## Summary

| Area | Tools | Server |
|------|-------|--------|
| Jira Groups | 6 (2 read, 4 write) | Existing Jira MCP |
| Tempo Timesheets | 10 (6 read, 4 write) | New Tempo MCP |
| Tempo Planner | 12 (5 read, 7 write) | New Tempo MCP |
| **Total** | **28** | |

**Final tool counts:**
- Jira MCP server: 33 existing + 6 groups = **39 tools**
- Tempo MCP server: 10 timesheets + 12 planner = **22 tools**
