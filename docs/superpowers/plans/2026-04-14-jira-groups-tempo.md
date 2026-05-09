# Jira Groups & Tempo MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6 Jira Groups tools to the existing Jira MCP server and create a new Tempo MCP server with 22 tools for Tempo Timesheets and Tempo Planner, targeting Jira Data Center only.

**Architecture:** Jira Groups is a new mixin (`GroupsMixin`) added to `JiraFetcher` with tools registered in `servers/jira.py`. Tempo gets its own package (`src/mcp_atlassian/tempo/`) with `TempoClient`, `TempoFetcher`, and two mixins, plus a separate FastMCP instance mounted via `main_mcp.mount("tempo", tempo_mcp)`. Service detection uses `TEMPO_ENABLED=true` env var gated on Jira being configured.

**Tech Stack:** Python, FastMCP, Pydantic v2, atlassian-python-api, pytest

**Spec:** `docs/superpowers/specs/2026-04-09-jira-groups-tempo-design.md`

---

### Task 1: Groups Models

**Files:**
- Create: `src/mcp_atlassian/models/jira/group.py`
- Modify: `src/mcp_atlassian/models/jira/__init__.py`
- Modify: `src/mcp_atlassian/models/__init__.py`
- Test: `tests/unit/models/jira/test_group_models.py`

- [ ] **Step 1: Write failing tests for JiraGroup model**

Create `tests/unit/models/jira/test_group_models.py`:

```python
"""Tests for Jira Group models."""

import pytest

from mcp_atlassian.models.jira.group import (
    JiraGroup,
    JiraGroupMember,
    JiraGroupMembersResult,
)


class TestJiraGroup:
    def test_from_api_response_basic(self):
        data = {"name": "jira-users", "html": "<b>jira-users</b>"}
        group = JiraGroup.from_api_response(data)
        assert group.name == "jira-users"
        assert group.html == "<b>jira-users</b>"

    def test_from_api_response_empty(self):
        group = JiraGroup.from_api_response({})
        assert group.name == ""

    def test_from_api_response_non_dict(self):
        group = JiraGroup.from_api_response("not a dict")
        assert group.name == ""

    def test_to_simplified_dict(self):
        group = JiraGroup(name="developers", html="<b>developers</b>")
        result = group.to_simplified_dict()
        assert result["name"] == "developers"


class TestJiraGroupMember:
    def test_from_api_response_basic(self):
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

    def test_from_api_response_empty(self):
        member = JiraGroupMember.from_api_response({})
        assert member.name == ""
        assert member.active is True

    def test_to_simplified_dict(self):
        member = JiraGroupMember(
            key="jdoe", name="jdoe", display_name="John Doe",
            email="jdoe@example.com", active=True,
        )
        result = member.to_simplified_dict()
        assert result["display_name"] == "John Doe"
        assert result["name"] == "jdoe"


class TestJiraGroupMembersResult:
    def test_from_api_response_basic(self):
        data = {
            "values": [
                {"key": "jdoe", "name": "jdoe", "displayName": "John Doe",
                 "emailAddress": "jdoe@example.com", "active": True},
                {"key": "asmith", "name": "asmith", "displayName": "Alice Smith",
                 "emailAddress": "asmith@example.com", "active": False},
            ],
            "total": 2,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,
        }
        result = JiraGroupMembersResult.from_api_response(data)
        assert len(result.members) == 2
        assert result.total == 2
        assert result.is_last is True
        assert result.members[0].name == "jdoe"
        assert result.members[1].active is False

    def test_from_api_response_empty(self):
        result = JiraGroupMembersResult.from_api_response({})
        assert len(result.members) == 0
        assert result.total == 0

    def test_to_simplified_dict(self):
        result = JiraGroupMembersResult(
            members=[JiraGroupMember(key="jdoe", name="jdoe", display_name="John Doe")],
            total=1, start_at=0, max_results=50, is_last=True,
        )
        d = result.to_simplified_dict()
        assert d["total"] == 1
        assert len(d["members"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/models/jira/test_group_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_atlassian.models.jira.group'`

- [ ] **Step 3: Implement the models**

Create `src/mcp_atlassian/models/jira/group.py`:

```python
"""Jira Group models."""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import EMPTY_STRING

logger = logging.getLogger(__name__)


class JiraGroup(ApiModel):
    """Model representing a Jira group."""

    name: str = EMPTY_STRING
    html: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "JiraGroup":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            name=str(data.get("name", EMPTY_STRING)),
            html=data.get("html"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.html:
            result["html"] = self.html
        return result


class JiraGroupMember(ApiModel):
    """Model representing a member of a Jira group."""

    key: str = EMPTY_STRING
    name: str = EMPTY_STRING
    display_name: str = EMPTY_STRING
    email: str | None = None
    active: bool = True

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "JiraGroupMember":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            key=str(data.get("key", EMPTY_STRING)),
            name=str(data.get("name", EMPTY_STRING)),
            display_name=str(data.get("displayName", EMPTY_STRING)),
            email=data.get("emailAddress"),
            active=bool(data.get("active", True)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "key": self.key,
            "name": self.name,
            "display_name": self.display_name,
            "active": self.active,
        }
        if self.email:
            result["email"] = self.email
        return result


class JiraGroupMembersResult(ApiModel):
    """Model representing a paginated list of group members."""

    members: list[JiraGroupMember] = []
    total: int = 0
    start_at: int = 0
    max_results: int = 50
    is_last: bool = True

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "JiraGroupMembersResult":
        if not data or not isinstance(data, dict):
            return cls()
        members = []
        for item in data.get("values", []):
            members.append(JiraGroupMember.from_api_response(item))
        return cls(
            members=members,
            total=int(data.get("total", 0)),
            start_at=int(data.get("startAt", 0)),
            max_results=int(data.get("maxResults", 50)),
            is_last=bool(data.get("isLast", True)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "members": [m.to_simplified_dict() for m in self.members],
            "total": self.total,
            "start_at": self.start_at,
            "max_results": self.max_results,
            "is_last": self.is_last,
        }
```

- [ ] **Step 4: Add exports to model `__init__` files**

In `src/mcp_atlassian/models/jira/__init__.py`, add import:
```python
from .group import JiraGroup, JiraGroupMember, JiraGroupMembersResult
```

In `src/mcp_atlassian/models/__init__.py`, add to imports and `__all__`:
```python
from .jira import JiraGroup, JiraGroupMember, JiraGroupMembersResult
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/models/jira/test_group_models.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_atlassian/models/jira/group.py tests/unit/models/jira/test_group_models.py src/mcp_atlassian/models/jira/__init__.py src/mcp_atlassian/models/__init__.py
git commit -m "feat: add Jira Group models (JiraGroup, JiraGroupMember, JiraGroupMembersResult)"
```

---

### Task 2: GroupsMixin

**Files:**
- Create: `src/mcp_atlassian/jira/groups.py`
- Modify: `src/mcp_atlassian/jira/__init__.py`
- Test: `tests/unit/jira/test_groups.py`

- [ ] **Step 1: Write failing tests for GroupsMixin**

Create `tests/unit/jira/test_groups.py`:

```python
"""Tests for the Jira Groups mixin."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.jira.groups import GroupsMixin


class TestGroupsMixin:
    @pytest.fixture
    def groups_mixin(self, jira_client):
        mixin = GroupsMixin(config=jira_client.config)
        mixin.jira = jira_client.jira
        return mixin

    def test_search_groups(self, groups_mixin):
        groups_mixin.jira.get = MagicMock(return_value={
            "header": "Showing 2 of 2 matching groups",
            "total": 2,
            "groups": [
                {"name": "jira-users", "html": "<b>jira-users</b>"},
                {"name": "jira-admins", "html": "<b>jira-admins</b>"},
            ],
        })
        result = groups_mixin.search_groups("jira")
        assert len(result) == 2
        assert result[0].name == "jira-users"

    def test_search_groups_empty(self, groups_mixin):
        groups_mixin.jira.get = MagicMock(return_value={"groups": [], "total": 0})
        result = groups_mixin.search_groups("nonexistent")
        assert len(result) == 0

    def test_get_group_members(self, groups_mixin):
        groups_mixin.jira.get = MagicMock(return_value={
            "values": [
                {"key": "jdoe", "name": "jdoe", "displayName": "John Doe",
                 "emailAddress": "jdoe@example.com", "active": True},
            ],
            "total": 1, "startAt": 0, "maxResults": 50, "isLast": True,
        })
        result = groups_mixin.get_group_members("jira-users")
        assert result.total == 1
        assert result.members[0].name == "jdoe"

    def test_create_group(self, groups_mixin):
        groups_mixin.jira.post = MagicMock(return_value={"name": "new-group"})
        result = groups_mixin.create_group("new-group")
        assert result["name"] == "new-group"

    def test_delete_group(self, groups_mixin):
        groups_mixin.jira.delete = MagicMock(return_value=None)
        groups_mixin.delete_group("old-group")
        groups_mixin.jira.delete.assert_called_once()

    def test_add_user_to_group(self, groups_mixin):
        groups_mixin.jira.post = MagicMock(return_value={"name": "jira-users"})
        groups_mixin.add_user_to_group("jira-users", "jdoe")
        groups_mixin.jira.post.assert_called_once()

    def test_remove_user_from_group(self, groups_mixin):
        groups_mixin.jira.delete = MagicMock(return_value=None)
        groups_mixin.remove_user_from_group("jira-users", "jdoe")
        groups_mixin.jira.delete.assert_called_once()

    def test_get_group_members_http_404(self, groups_mixin):
        response = MagicMock()
        response.status_code = 404
        response.text = "Not Found"
        groups_mixin.jira.get = MagicMock(
            side_effect=HTTPError(response=response)
        )
        with pytest.raises(ValueError, match="not found"):
            groups_mixin.get_group_members("nonexistent-group")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/jira/test_groups.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_atlassian.jira.groups'`

- [ ] **Step 3: Implement GroupsMixin**

Create `src/mcp_atlassian/jira/groups.py`:

```python
"""Module for Jira group operations."""

import logging
from typing import Any

from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.models.jira.group import (
    JiraGroup,
    JiraGroupMembersResult,
)

from .client import JiraClient

logger = logging.getLogger("mcp-jira")


class GroupsMixin(JiraClient):
    """Mixin for Jira group operations."""

    def search_groups(
        self, query: str, max_results: int = 50
    ) -> list[JiraGroup]:
        """Search groups by name substring.

        Args:
            query: Search text (substring match)
            max_results: Maximum number of results

        Returns:
            List of JiraGroup models
        """
        try:
            result = self.jira.get(
                "rest/api/2/groups/picker",
                params={"query": query, "maxResults": max_results},
            )
            if not isinstance(result, dict):
                return []
            groups = []
            for group_data in result.get("groups", []):
                groups.append(JiraGroup.from_api_response(group_data))
            return groups
        except Exception as e:
            logger.warning(f"Error searching groups with query '{query}': {e}")
            return []

    def get_group_members(
        self,
        group_name: str,
        include_inactive: bool = False,
        start_at: int = 0,
        max_results: int = 50,
    ) -> JiraGroupMembersResult:
        """List members of a group with pagination.

        Args:
            group_name: Exact group name
            include_inactive: Include inactive users
            start_at: Pagination offset
            max_results: Page size

        Returns:
            JiraGroupMembersResult with members and pagination metadata

        Raises:
            ValueError: If group not found
            MCPAtlassianAuthenticationError: If permission denied
        """
        try:
            result = self.jira.get(
                "rest/api/2/group/member",
                params={
                    "groupname": group_name,
                    "includeInactiveUsers": str(include_inactive).lower(),
                    "startAt": start_at,
                    "maxResults": max_results,
                },
            )
            if not isinstance(result, dict):
                msg = f"Unexpected response type: {type(result)}"
                logger.error(msg)
                raise TypeError(msg)
            return JiraGroupMembersResult.from_api_response(result)
        except HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 404:
                    raise ValueError(f"Group '{group_name}' not found.") from e
                if e.response.status_code in (401, 403):
                    raise MCPAtlassianAuthenticationError(
                        f"Permission denied accessing group '{group_name}'."
                    ) from e
            raise Exception(f"Error getting group members: {e}") from e

    def create_group(self, name: str) -> dict[str, Any]:
        """Create a new Jira group.

        Args:
            name: Group name

        Returns:
            Created group data

        Raises:
            Exception: If creation fails
        """
        try:
            result = self.jira.post("rest/api/2/group", data={"name": name})
            if not isinstance(result, dict):
                return {"name": name}
            return result
        except Exception as e:
            logger.error(f"Error creating group '{name}': {e}")
            raise Exception(f"Error creating group: {e}") from e

    def delete_group(
        self, group_name: str, swap_group: str | None = None
    ) -> None:
        """Delete a Jira group.

        Args:
            group_name: Group to delete
            swap_group: Optional group to transfer visibility restrictions to
        """
        try:
            params: dict[str, str] = {"groupname": group_name}
            if swap_group:
                params["swapGroup"] = swap_group
            self.jira.delete("rest/api/2/group", params=params)
        except Exception as e:
            logger.error(f"Error deleting group '{group_name}': {e}")
            raise Exception(f"Error deleting group: {e}") from e

    def add_user_to_group(self, group_name: str, username: str) -> None:
        """Add a user to a group.

        Args:
            group_name: Target group (case-sensitive)
            username: User to add (DC name field)
        """
        try:
            self.jira.post(
                "rest/api/2/group/user",
                params={"groupname": group_name},
                data={"name": username},
            )
        except Exception as e:
            logger.error(
                f"Error adding user '{username}' to group '{group_name}': {e}"
            )
            raise Exception(f"Error adding user to group: {e}") from e

    def remove_user_from_group(
        self, group_name: str, username: str
    ) -> None:
        """Remove a user from a group.

        Args:
            group_name: Target group (case-sensitive)
            username: User to remove
        """
        try:
            self.jira.delete(
                "rest/api/2/group/user",
                params={"groupname": group_name, "username": username},
            )
        except Exception as e:
            logger.error(
                f"Error removing user '{username}' from group '{group_name}': {e}"
            )
            raise Exception(f"Error removing user from group: {e}") from e
```

- [ ] **Step 4: Add GroupsMixin to JiraFetcher**

In `src/mcp_atlassian/jira/__init__.py`, add import and mixin:

```python
from .groups import GroupsMixin

class JiraFetcher(
    ProjectsMixin,
    FieldsMixin,
    FormattingMixin,
    TransitionsMixin,
    WorklogMixin,
    EpicsMixin,
    CommentsMixin,
    SearchMixin,
    IssuesMixin,
    UsersMixin,
    BoardsMixin,
    SprintsMixin,
    AttachmentsMixin,
    LinksMixin,
    GroupsMixin,
):
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/jira/test_groups.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_atlassian/jira/groups.py src/mcp_atlassian/jira/__init__.py tests/unit/jira/test_groups.py
git commit -m "feat: add GroupsMixin with search, members, CRUD operations"
```

---

### Task 3: Groups Tools in Jira Server

**Files:**
- Modify: `src/mcp_atlassian/servers/jira.py`

- [ ] **Step 1: Add 6 Groups tools to jira server**

Append to `src/mcp_atlassian/servers/jira.py` (after the last existing tool):

```python
# --- Groups Tools ---


@jira_mcp.tool(tags={"jira", "read"})
async def jira_search_groups(
    ctx: Context,
    query: Annotated[str, Field(description="Search text (substring match on group name)")],
    max_results: Annotated[int, Field(description="Maximum number of results", default=50)] = 50,
) -> str:
    """Search for Jira groups by name."""
    jira = await get_jira_fetcher(ctx)
    try:
        groups = jira.search_groups(query=query, max_results=max_results)
        return json.dumps(
            {"success": True, "groups": [g.to_simplified_dict() for g in groups]},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"jira_search_groups failed for query '{query}': {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def jira_get_group_members(
    ctx: Context,
    group_name: Annotated[str, Field(description="Exact group name")],
    include_inactive: Annotated[bool, Field(description="Include inactive users", default=False)] = False,
    start_at: Annotated[int, Field(description="Pagination offset", default=0)] = 0,
    max_results: Annotated[int, Field(description="Page size (max 50)", default=50)] = 50,
) -> str:
    """List members of a Jira group with pagination."""
    jira = await get_jira_fetcher(ctx)
    try:
        result = jira.get_group_members(
            group_name=group_name,
            include_inactive=include_inactive,
            start_at=start_at,
            max_results=max_results,
        )
        return json.dumps(
            {"success": True, **result.to_simplified_dict()},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        log_level = logging.WARNING if isinstance(e, ValueError) else logging.ERROR
        logger.log(log_level, f"jira_get_group_members failed for '{group_name}': {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
async def jira_create_group(
    ctx: Context,
    name: Annotated[str, Field(description="Name for the new group")],
) -> str:
    """Create a new Jira group. Requires admin permissions."""
    jira = await get_jira_fetcher(ctx)
    try:
        result = jira.create_group(name=name)
        return json.dumps({"success": True, "group": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"jira_create_group failed for '{name}': {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
async def jira_delete_group(
    ctx: Context,
    group_name: Annotated[str, Field(description="Group to delete")],
    swap_group: Annotated[str | None, Field(description="Transfer visibility restrictions to this group before deletion")] = None,
) -> str:
    """Delete a Jira group. Requires admin permissions."""
    jira = await get_jira_fetcher(ctx)
    try:
        jira.delete_group(group_name=group_name, swap_group=swap_group)
        return json.dumps({"success": True, "deleted": group_name}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"jira_delete_group failed for '{group_name}': {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
async def jira_add_user_to_group(
    ctx: Context,
    group_name: Annotated[str, Field(description="Target group (case-sensitive)")],
    username: Annotated[str, Field(description="Username to add (DC 'name' field)")],
) -> str:
    """Add a user to a Jira group."""
    jira = await get_jira_fetcher(ctx)
    try:
        jira.add_user_to_group(group_name=group_name, username=username)
        return json.dumps(
            {"success": True, "group": group_name, "user_added": username},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"jira_add_user_to_group failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
async def jira_remove_user_from_group(
    ctx: Context,
    group_name: Annotated[str, Field(description="Target group (case-sensitive)")],
    username: Annotated[str, Field(description="Username to remove")],
) -> str:
    """Remove a user from a Jira group."""
    jira = await get_jira_fetcher(ctx)
    try:
        jira.remove_user_from_group(group_name=group_name, username=username)
        return json.dumps(
            {"success": True, "group": group_name, "user_removed": username},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"jira_remove_user_from_group failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `python -m pytest tests/unit/jira/ -v --timeout=30`
Expected: All existing + new tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/mcp_atlassian/servers/jira.py
git commit -m "feat: register 6 Jira Groups tools in Jira MCP server"
```

---

### Task 4: Tempo Models — Timesheets

**Files:**
- Create: `src/mcp_atlassian/models/tempo/__init__.py`
- Create: `src/mcp_atlassian/models/tempo/timesheets.py`
- Modify: `src/mcp_atlassian/models/__init__.py`
- Test: `tests/unit/models/tempo/test_timesheets_models.py`

- [ ] **Step 1: Create test directory and conftest**

```bash
mkdir -p tests/unit/models/tempo
touch tests/unit/models/tempo/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `tests/unit/models/tempo/test_timesheets_models.py`:

```python
"""Tests for Tempo Timesheets models."""

from mcp_atlassian.models.tempo.timesheets import (
    TempoApproval,
    TempoScheduleDay,
    TempoUserSchedule,
    TempoWorkAttribute,
    TempoWorklog,
)


class TestTempoWorklog:
    def test_from_api_response_basic(self):
        data = {
            "tempoWorklogId": 12345,
            "jiraWorklogId": 67890,
            "issue": {"key": "PROJ-123"},
            "worker": "jdoe",
            "updater": "jdoe",
            "startDate": "2026-04-01",
            "timeSpentSeconds": 3600,
            "billableSeconds": 3600,
            "comment": "Did some work",
            "attributes": {"_Account_": {"value": "INTERNAL"}},
            "dateCreated": "2026-04-01T10:00:00.000",
            "dateUpdated": "2026-04-01T11:00:00.000",
        }
        wl = TempoWorklog.from_api_response(data)
        assert wl.tempo_worklog_id == 12345
        assert wl.jira_worklog_id == 67890
        assert wl.issue_key == "PROJ-123"
        assert wl.worker_key == "jdoe"
        assert wl.time_spent_seconds == 3600
        assert wl.comment == "Did some work"

    def test_from_api_response_empty(self):
        wl = TempoWorklog.from_api_response({})
        assert wl.tempo_worklog_id == -1

    def test_to_simplified_dict(self):
        wl = TempoWorklog(
            tempo_worklog_id=1, issue_key="PROJ-1",
            worker_key="jdoe", started="2026-04-01",
            time_spent_seconds=7200,
        )
        d = wl.to_simplified_dict()
        assert d["tempo_worklog_id"] == 1
        assert d["issue_key"] == "PROJ-1"


class TestTempoApproval:
    def test_from_api_response_basic(self):
        data = {
            "status": "waiting_for_approval",
            "workedSeconds": 28800,
            "submittedSeconds": 28800,
            "requiredSeconds": 28800,
            "user": {"key": "jdoe"},
            "period": {"dateFrom": "2026-04-01", "dateTo": "2026-04-07"},
            "reviewer": {"key": "manager1"},
        }
        a = TempoApproval.from_api_response(data)
        assert a.status == "waiting_for_approval"
        assert a.worked_seconds == 28800
        assert a.user_key == "jdoe"
        assert a.reviewer_key == "manager1"


class TestTempoWorkAttribute:
    def test_from_api_response(self):
        data = {"id": 1, "name": "Activity", "type": "STATIC_LIST", "required": True}
        wa = TempoWorkAttribute.from_api_response(data)
        assert wa.id == 1
        assert wa.name == "Activity"
        assert wa.required is True


class TestTempoUserSchedule:
    def test_from_api_response(self):
        data = {
            "numberOfWorkingDays": 5,
            "requiredSeconds": 144000,
            "days": [
                {"date": "2026-04-01", "requiredSeconds": 28800, "type": "WORKING_DAY"},
                {"date": "2026-04-02", "requiredSeconds": 0, "type": "HOLIDAY",
                 "holiday": {"name": "Easter"}},
            ],
        }
        s = TempoUserSchedule.from_api_response(data)
        assert s.number_of_working_days == 5
        assert len(s.days) == 2
        assert s.days[1].holiday_name == "Easter"
        assert s.days[1].type == "HOLIDAY"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/unit/models/tempo/test_timesheets_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement the models**

Create `src/mcp_atlassian/models/tempo/__init__.py`:

```python
"""Tempo models package."""

from .timesheets import (
    TempoApproval,
    TempoScheduleDay,
    TempoUserSchedule,
    TempoWorkAttribute,
    TempoWorklog,
)

__all__ = [
    "TempoWorklog",
    "TempoApproval",
    "TempoWorkAttribute",
    "TempoScheduleDay",
    "TempoUserSchedule",
]
```

Create `src/mcp_atlassian/models/tempo/timesheets.py`:

```python
"""Tempo Timesheets models."""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import EMPTY_STRING

logger = logging.getLogger(__name__)


class TempoWorklog(ApiModel):
    """Model representing a Tempo worklog entry."""

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

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoWorklog":
        if not data or not isinstance(data, dict):
            return cls()
        issue_key = EMPTY_STRING
        issue_data = data.get("issue")
        if isinstance(issue_data, dict):
            issue_key = str(issue_data.get("key", EMPTY_STRING))
        elif isinstance(data.get("originTaskId"), str):
            issue_key = data["originTaskId"]
        return cls(
            tempo_worklog_id=int(data.get("tempoWorklogId", -1)),
            jira_worklog_id=data.get("jiraWorklogId"),
            issue_key=issue_key,
            worker_key=str(data.get("worker", data.get("workerKey", EMPTY_STRING))),
            updater_key=data.get("updater", data.get("updaterKey")),
            started=str(data.get("startDate", data.get("started", EMPTY_STRING))),
            time_spent_seconds=int(data.get("timeSpentSeconds", 0)),
            billable_seconds=int(data.get("billableSeconds", 0)),
            comment=data.get("comment"),
            attributes=data.get("attributes"),
            created=str(data.get("dateCreated", EMPTY_STRING)),
            updated=str(data.get("dateUpdated", EMPTY_STRING)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tempo_worklog_id": self.tempo_worklog_id,
            "issue_key": self.issue_key,
            "worker_key": self.worker_key,
            "started": self.started,
            "time_spent_seconds": self.time_spent_seconds,
            "billable_seconds": self.billable_seconds,
        }
        if self.jira_worklog_id is not None:
            result["jira_worklog_id"] = self.jira_worklog_id
        if self.comment:
            result["comment"] = self.comment
        if self.attributes:
            result["attributes"] = self.attributes
        if self.created:
            result["created"] = self.created
        if self.updated:
            result["updated"] = self.updated
        return result


class TempoApproval(ApiModel):
    """Model representing a Tempo timesheet approval."""

    status: str = EMPTY_STRING
    worked_seconds: int = 0
    submitted_seconds: int = 0
    required_seconds: int = 0
    user_key: str = EMPTY_STRING
    period_start: str = EMPTY_STRING
    period_end: str = EMPTY_STRING
    reviewer_key: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoApproval":
        if not data or not isinstance(data, dict):
            return cls()
        user_key = EMPTY_STRING
        user_data = data.get("user")
        if isinstance(user_data, dict):
            user_key = str(user_data.get("key", EMPTY_STRING))
        period_start = EMPTY_STRING
        period_end = EMPTY_STRING
        period_data = data.get("period")
        if isinstance(period_data, dict):
            period_start = str(period_data.get("dateFrom", EMPTY_STRING))
            period_end = str(period_data.get("dateTo", EMPTY_STRING))
        reviewer_key = None
        reviewer_data = data.get("reviewer")
        if isinstance(reviewer_data, dict):
            reviewer_key = reviewer_data.get("key")
        return cls(
            status=str(data.get("status", EMPTY_STRING)),
            worked_seconds=int(data.get("workedSeconds", 0)),
            submitted_seconds=int(data.get("submittedSeconds", 0)),
            required_seconds=int(data.get("requiredSeconds", 0)),
            user_key=user_key,
            period_start=period_start,
            period_end=period_end,
            reviewer_key=reviewer_key,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "worked_seconds": self.worked_seconds,
            "required_seconds": self.required_seconds,
            "user_key": self.user_key,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }
        if self.submitted_seconds:
            result["submitted_seconds"] = self.submitted_seconds
        if self.reviewer_key:
            result["reviewer_key"] = self.reviewer_key
        return result


class TempoWorkAttribute(ApiModel):
    """Model representing a Tempo work attribute."""

    id: int = -1
    name: str = EMPTY_STRING
    type: str = EMPTY_STRING
    required: bool = False

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoWorkAttribute":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            id=int(data.get("id", -1)),
            name=str(data.get("name", EMPTY_STRING)),
            type=str(data.get("type", EMPTY_STRING)),
            required=bool(data.get("required", False)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "required": self.required,
        }


class TempoScheduleDay(ApiModel):
    """Model representing a single day in a user schedule."""

    date: str = EMPTY_STRING
    required_seconds: int = 0
    type: str = EMPTY_STRING
    holiday_name: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoScheduleDay":
        if not data or not isinstance(data, dict):
            return cls()
        holiday_name = None
        holiday_data = data.get("holiday")
        if isinstance(holiday_data, dict):
            holiday_name = holiday_data.get("name")
        return cls(
            date=str(data.get("date", EMPTY_STRING)),
            required_seconds=int(data.get("requiredSeconds", 0)),
            type=str(data.get("type", EMPTY_STRING)),
            holiday_name=holiday_name,
        )


class TempoUserSchedule(ApiModel):
    """Model representing a user's work schedule."""

    number_of_working_days: int = 0
    required_seconds: int = 0
    days: list[TempoScheduleDay] = []

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoUserSchedule":
        if not data or not isinstance(data, dict):
            return cls()
        days = []
        for day_data in data.get("days", []):
            days.append(TempoScheduleDay.from_api_response(day_data))
        return cls(
            number_of_working_days=int(data.get("numberOfWorkingDays", 0)),
            required_seconds=int(data.get("requiredSeconds", 0)),
            days=days,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "number_of_working_days": self.number_of_working_days,
            "required_seconds": self.required_seconds,
            "days": [{"date": d.date, "required_seconds": d.required_seconds,
                       "type": d.type, **({"holiday_name": d.holiday_name} if d.holiday_name else {})}
                      for d in self.days],
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/models/tempo/test_timesheets_models.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_atlassian/models/tempo/ tests/unit/models/tempo/
git commit -m "feat: add Tempo Timesheets models (TempoWorklog, TempoApproval, TempoWorkAttribute, TempoUserSchedule)"
```

---

### Task 5: Tempo Models — Planner

**Files:**
- Create: `src/mcp_atlassian/models/tempo/planner.py`
- Modify: `src/mcp_atlassian/models/tempo/__init__.py`
- Test: `tests/unit/models/tempo/test_planner_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/models/tempo/test_planner_models.py`:

```python
"""Tests for Tempo Planner models."""

from mcp_atlassian.models.tempo.planner import (
    TempoAllocation,
    TempoTeam,
    TempoTeamMember,
    TempoTeamRole,
)


class TestTempoTeam:
    def test_from_api_response(self):
        data = {"id": 1, "name": "Backend", "summary": "Backend team",
                "lead": {"key": "jdoe"}, "isPublic": True}
        team = TempoTeam.from_api_response(data)
        assert team.id == 1
        assert team.name == "Backend"
        assert team.lead_key == "jdoe"
        assert team.is_public is True

    def test_from_api_response_empty(self):
        team = TempoTeam.from_api_response({})
        assert team.id == -1


class TestTempoTeamRole:
    def test_from_api_response(self):
        data = {"id": 1, "name": "Developer"}
        role = TempoTeamRole.from_api_response(data)
        assert role.id == 1
        assert role.name == "Developer"


class TestTempoTeamMember:
    def test_from_api_response(self):
        data = {
            "id": 42,
            "member": {"name": "jdoe", "type": "USER", "displayName": "John Doe"},
            "membership": {
                "role": {"name": "Developer"},
                "availability": 80,
                "dateFrom": "2026-01-01",
                "dateTo": "2026-12-31",
                "status": "ACTIVE",
            },
        }
        m = TempoTeamMember.from_api_response(data)
        assert m.id == 42
        assert m.member_key == "jdoe"
        assert m.member_type == "USER"
        assert m.display_name == "John Doe"
        assert m.role == "Developer"
        assert m.availability == 80

    def test_from_api_response_group_type(self):
        data = {
            "id": 43,
            "member": {"name": "dev-group", "type": "GROUP", "displayName": "Dev Group"},
            "membership": {"status": "ACTIVE"},
        }
        m = TempoTeamMember.from_api_response(data)
        assert m.member_type == "GROUP"
        assert m.member_key == "dev-group"


class TestTempoAllocation:
    def test_from_api_response(self):
        data = {
            "id": 100,
            "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 456, "type": "ISSUE"},
            "commitment": 50,
            "secondsPerDay": 14400,
            "start": "2026-04-01",
            "end": "2026-04-30",
            "description": "Sprint work",
            "created": "2026-03-28T10:00:00.000",
            "updated": "2026-03-28T10:00:00.000",
        }
        a = TempoAllocation.from_api_response(data)
        assert a.id == 100
        assert a.assignee_key == "jdoe"
        assert a.assignee_type == "USER"
        assert a.plan_item_id == 456
        assert a.commitment == 50
        assert a.seconds_per_day == 14400

    def test_from_api_response_empty(self):
        a = TempoAllocation.from_api_response({})
        assert a.id == -1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/models/tempo/test_planner_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the models**

Create `src/mcp_atlassian/models/tempo/planner.py`:

```python
"""Tempo Planner models."""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import EMPTY_STRING

logger = logging.getLogger(__name__)


class TempoTeam(ApiModel):
    """Model representing a Tempo team."""

    id: int = -1
    name: str = EMPTY_STRING
    summary: str | None = None
    lead_key: str | None = None
    is_public: bool = True

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoTeam":
        if not data or not isinstance(data, dict):
            return cls()
        lead_key = None
        lead_data = data.get("lead")
        if isinstance(lead_data, dict):
            lead_key = lead_data.get("key")
        return cls(
            id=int(data.get("id", -1)),
            name=str(data.get("name", EMPTY_STRING)),
            summary=data.get("summary"),
            lead_key=lead_key,
            is_public=bool(data.get("isPublic", True)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.summary:
            result["summary"] = self.summary
        if self.lead_key:
            result["lead_key"] = self.lead_key
        result["is_public"] = self.is_public
        return result


class TempoTeamRole(ApiModel):
    """Model representing a Tempo team role."""

    id: int = -1
    name: str = EMPTY_STRING

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoTeamRole":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            id=int(data.get("id", -1)),
            name=str(data.get("name", EMPTY_STRING)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}


class TempoTeamMember(ApiModel):
    """Model representing a Tempo team member."""

    id: int = -1
    member_key: str = EMPTY_STRING
    member_type: str = "USER"
    display_name: str = EMPTY_STRING
    role: str | None = None
    availability: int = 100
    date_from: str | None = None
    date_to: str | None = None
    status: str = EMPTY_STRING

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoTeamMember":
        if not data or not isinstance(data, dict):
            return cls()
        member_data = data.get("member", {})
        membership_data = data.get("membership", {})
        role_name = None
        role_data = membership_data.get("role")
        if isinstance(role_data, dict):
            role_name = role_data.get("name")
        return cls(
            id=int(data.get("id", -1)),
            member_key=str(member_data.get("name", EMPTY_STRING)),
            member_type=str(member_data.get("type", "USER")),
            display_name=str(member_data.get("displayName", EMPTY_STRING)),
            role=role_name,
            availability=int(membership_data.get("availability", 100)),
            date_from=membership_data.get("dateFrom"),
            date_to=membership_data.get("dateTo"),
            status=str(membership_data.get("status", EMPTY_STRING)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "member_key": self.member_key,
            "member_type": self.member_type,
            "display_name": self.display_name,
            "availability": self.availability,
            "status": self.status,
        }
        if self.role:
            result["role"] = self.role
        if self.date_from:
            result["date_from"] = self.date_from
        if self.date_to:
            result["date_to"] = self.date_to
        return result


class TempoAllocation(ApiModel):
    """Model representing a Tempo resource allocation."""

    id: int = -1
    assignee_key: str = EMPTY_STRING
    assignee_type: str = EMPTY_STRING
    plan_item_id: int = -1
    plan_item_type: str = EMPTY_STRING
    commitment: int = 0
    seconds_per_day: int = 0
    start: str = EMPTY_STRING
    end: str = EMPTY_STRING
    description: str | None = None
    created: str = EMPTY_STRING
    updated: str = EMPTY_STRING

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "TempoAllocation":
        if not data or not isinstance(data, dict):
            return cls()
        assignee_data = data.get("assignee", {})
        plan_item_data = data.get("planItem", {})
        return cls(
            id=int(data.get("id", -1)),
            assignee_key=str(assignee_data.get("key", EMPTY_STRING)),
            assignee_type=str(assignee_data.get("type", EMPTY_STRING)),
            plan_item_id=int(plan_item_data.get("id", -1)),
            plan_item_type=str(plan_item_data.get("type", EMPTY_STRING)),
            commitment=int(data.get("commitment", 0)),
            seconds_per_day=int(data.get("secondsPerDay", 0)),
            start=str(data.get("start", EMPTY_STRING)),
            end=str(data.get("end", EMPTY_STRING)),
            description=data.get("description"),
            created=str(data.get("created", EMPTY_STRING)),
            updated=str(data.get("updated", EMPTY_STRING)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
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
        if self.description:
            result["description"] = self.description
        return result
```

- [ ] **Step 4: Update `__init__.py` exports**

Add to `src/mcp_atlassian/models/tempo/__init__.py`:

```python
from .planner import TempoAllocation, TempoTeam, TempoTeamMember, TempoTeamRole
```

And add to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/models/tempo/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_atlassian/models/tempo/planner.py src/mcp_atlassian/models/tempo/__init__.py tests/unit/models/tempo/test_planner_models.py
git commit -m "feat: add Tempo Planner models (TempoTeam, TempoTeamMember, TempoTeamRole, TempoAllocation)"
```

---

### Task 6: Tempo Package — Client and Config

**Files:**
- Create: `src/mcp_atlassian/tempo/__init__.py`
- Create: `src/mcp_atlassian/tempo/config.py`
- Create: `src/mcp_atlassian/tempo/client.py`
- Test: `tests/unit/tempo/__init__.py`
- Test: `tests/unit/tempo/conftest.py`

- [ ] **Step 1: Create the tempo package and config**

Create `src/mcp_atlassian/tempo/config.py`:

```python
"""Configuration for Tempo integration."""

import logging
import os
from dataclasses import dataclass, field

from mcp_atlassian.jira.config import JiraConfig

logger = logging.getLogger("mcp-tempo")


@dataclass
class TempoConfig:
    """Configuration for Tempo, reusing Jira credentials."""

    jira_config: JiraConfig = field(default_factory=JiraConfig.from_env)
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "TempoConfig":
        """Create TempoConfig from environment variables."""
        enabled = os.getenv("TEMPO_ENABLED", "").lower() in ("true", "1", "yes")
        jira_config = JiraConfig.from_env()
        return cls(jira_config=jira_config, enabled=enabled)

    def is_auth_configured(self) -> bool:
        """Check if Tempo auth is configured (same as Jira auth)."""
        return self.enabled and self.jira_config.is_auth_configured()

    @property
    def url(self) -> str:
        return self.jira_config.url

    @property
    def ssl_verify(self) -> bool:
        return self.jira_config.ssl_verify
```

- [ ] **Step 2: Create the base client**

Create `src/mcp_atlassian/tempo/client.py`:

```python
"""Base client for Tempo API interactions."""

import logging
from typing import Any

from atlassian import Jira

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.utils.ssl import configure_ssl_verification

from .config import TempoConfig

logger = logging.getLogger("mcp-tempo")


class TempoClient:
    """Base client for Tempo API interactions.

    Reuses the atlassian Jira client for HTTP calls since Tempo REST APIs
    are served on the same Jira DC URL with the same auth.
    """

    config: TempoConfig

    def __init__(self, config: TempoConfig | None = None) -> None:
        self.config = config or TempoConfig.from_env()
        jc = self.config.jira_config

        if jc.auth_type == "pat":
            self.jira = Jira(
                url=jc.url,
                token=jc.personal_token,
                cloud=False,
                verify_ssl=jc.ssl_verify,
            )
        else:
            self.jira = Jira(
                url=jc.url,
                username=jc.username,
                password=jc.api_token,
                cloud=jc.is_cloud,
                verify_ssl=jc.ssl_verify,
            )

        configure_ssl_verification(self.jira, jc.ssl_verify)
        logger.info(f"TempoClient initialized for {jc.url}")
```

- [ ] **Step 3: Create the TempoFetcher composition**

Create `src/mcp_atlassian/tempo/__init__.py`:

```python
"""Tempo API module for mcp_atlassian."""

from .client import TempoClient
from .config import TempoConfig

__all__ = ["TempoFetcher", "TempoClient", "TempoConfig"]
```

Note: `TempoFetcher` will be added in Task 8 after the mixins are created.

- [ ] **Step 4: Create test infrastructure**

```bash
mkdir -p tests/unit/tempo
```

Create `tests/unit/tempo/__init__.py` (empty).

Create `tests/unit/tempo/conftest.py`:

```python
"""Test fixtures for Tempo unit tests."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_atlassian.tempo.client import TempoClient
from mcp_atlassian.tempo.config import TempoConfig


@pytest.fixture
def tempo_config():
    with patch.dict(os.environ, {
        "JIRA_URL": "https://jira.example.com",
        "JIRA_PERSONAL_TOKEN": "fake-token",
        "TEMPO_ENABLED": "true",
    }):
        return TempoConfig.from_env()


@pytest.fixture
def tempo_client(tempo_config):
    with patch("mcp_atlassian.tempo.client.Jira") as MockJira:
        mock_jira = MagicMock()
        MockJira.return_value = mock_jira
        client = TempoClient(config=tempo_config)
        client.jira = mock_jira
        return client
```

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/tempo/ tests/unit/tempo/
git commit -m "feat: add Tempo package with TempoConfig and TempoClient"
```

---

### Task 7: Tempo Timesheets Mixin

**Files:**
- Create: `src/mcp_atlassian/tempo/timesheets.py`
- Test: `tests/unit/tempo/test_timesheets.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/tempo/test_timesheets.py`:

```python
"""Tests for the Tempo Timesheets mixin."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.tempo.timesheets import TempoTimesheetsMixin


class TestTempoTimesheetsMixin:
    @pytest.fixture
    def ts_mixin(self, tempo_client):
        mixin = TempoTimesheetsMixin(config=tempo_client.config)
        mixin.jira = tempo_client.jira
        return mixin

    def test_search_worklogs(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=[
            {"tempoWorklogId": 1, "issue": {"key": "PROJ-1"},
             "worker": "jdoe", "startDate": "2026-04-01",
             "timeSpentSeconds": 3600, "billableSeconds": 3600},
        ])
        result = ts_mixin.search_worklogs(date_from="2026-04-01", date_to="2026-04-07")
        assert len(result) == 1
        assert result[0].tempo_worklog_id == 1

    def test_get_worklog(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value={
            "tempoWorklogId": 1, "issue": {"key": "PROJ-1"},
            "worker": "jdoe", "startDate": "2026-04-01",
            "timeSpentSeconds": 3600, "billableSeconds": 3600,
        })
        result = ts_mixin.get_worklog(1)
        assert result.tempo_worklog_id == 1

    def test_create_worklog(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value={
            "tempoWorklogId": 99, "issue": {"key": "PROJ-1"},
            "worker": "jdoe", "startDate": "2026-04-01",
            "timeSpentSeconds": 7200, "billableSeconds": 7200,
        })
        result = ts_mixin.create_worklog(
            worker="jdoe", issue_key="PROJ-1",
            started="2026-04-01", time_spent_seconds=7200,
        )
        assert result.tempo_worklog_id == 99

    def test_delete_worklog(self, ts_mixin):
        ts_mixin.jira.delete = MagicMock(return_value=None)
        ts_mixin.delete_worklog(1)
        ts_mixin.jira.delete.assert_called_once()

    def test_get_approval_status(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[{
            "status": "approved", "workedSeconds": 28800,
            "requiredSeconds": 28800, "submittedSeconds": 28800,
            "user": {"key": "jdoe"},
            "period": {"dateFrom": "2026-04-01", "dateTo": "2026-04-07"},
        }])
        result = ts_mixin.get_approval_status("jdoe", "2026-04-01")
        assert len(result) >= 1
        assert result[0].status == "approved"

    def test_get_work_attributes(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[
            {"id": 1, "name": "Activity", "type": "STATIC_LIST", "required": True},
        ])
        result = ts_mixin.get_work_attributes()
        assert len(result) == 1
        assert result[0].name == "Activity"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tempo/test_timesheets.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TempoTimesheetsMixin**

Create `src/mcp_atlassian/tempo/timesheets.py`:

```python
"""Module for Tempo Timesheets operations."""

import logging
from typing import Any

from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.models.tempo.timesheets import (
    TempoApproval,
    TempoUserSchedule,
    TempoWorkAttribute,
    TempoWorklog,
)

from .client import TempoClient

logger = logging.getLogger("mcp-tempo")


class TempoTimesheetsMixin(TempoClient):
    """Mixin for Tempo Timesheets operations."""

    def search_worklogs(
        self,
        date_from: str,
        date_to: str,
        worker_keys: list[str] | None = None,
        project_keys: list[str] | None = None,
        team_ids: list[int] | None = None,
        epic_keys: list[str] | None = None,
        task_keys: list[str] | None = None,
    ) -> list[TempoWorklog]:
        """Search worklogs by date range and optional filters."""
        try:
            body: dict[str, Any] = {"from": date_from, "to": date_to}
            if worker_keys:
                body["worker"] = worker_keys
            if project_keys:
                body["projectKey"] = project_keys
            if team_ids:
                body["teamId"] = team_ids
            if epic_keys:
                body["epicKey"] = epic_keys
            if task_keys:
                body["taskKey"] = task_keys
            result = self.jira.post(
                "rest/tempo-timesheets/4/worklogs/search", data=body
            )
            if isinstance(result, list):
                return [TempoWorklog.from_api_response(w) for w in result]
            return []
        except Exception as e:
            logger.warning(f"Error searching worklogs: {e}")
            return []

    def get_worklog(self, worklog_id: int) -> TempoWorklog:
        """Get a single worklog by ID."""
        try:
            result = self.jira.get(
                f"rest/tempo-timesheets/4/worklogs/{worklog_id}"
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoWorklog.from_api_response(result)
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise ValueError(f"Worklog {worklog_id} not found.") from e
            raise

    def create_worklog(
        self,
        worker: str,
        issue_key: str,
        started: str,
        time_spent_seconds: int,
        comment: str | None = None,
        billable_seconds: int | None = None,
        end_date: str | None = None,
        include_non_working_days: bool = False,
        attributes: dict | None = None,
        remaining_estimate: int | None = None,
    ) -> TempoWorklog:
        """Create a Tempo worklog."""
        try:
            body: dict[str, Any] = {
                "worker": worker,
                "originTaskId": issue_key,
                "started": started,
                "timeSpentSeconds": time_spent_seconds,
                "includeNonWorkingDays": include_non_working_days,
            }
            if comment:
                body["comment"] = comment
            if billable_seconds is not None:
                body["billableSeconds"] = billable_seconds
            if end_date:
                body["endDate"] = end_date
            if attributes:
                body["attributes"] = attributes
            if remaining_estimate is not None:
                body["remainingEstimate"] = remaining_estimate
            result = self.jira.post(
                "rest/tempo-timesheets/4/worklogs", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoWorklog.from_api_response(result)
        except Exception as e:
            logger.error(f"Error creating worklog: {e}")
            raise Exception(f"Error creating worklog: {e}") from e

    def update_worklog(
        self,
        worklog_id: int,
        started: str | None = None,
        time_spent_seconds: int | None = None,
        comment: str | None = None,
        billable_seconds: int | None = None,
        end_date: str | None = None,
        include_non_working_days: bool | None = None,
        attributes: dict | None = None,
        remaining_estimate: int | None = None,
    ) -> TempoWorklog:
        """Update an existing Tempo worklog."""
        try:
            body: dict[str, Any] = {}
            if started is not None:
                body["started"] = started
            if time_spent_seconds is not None:
                body["timeSpentSeconds"] = time_spent_seconds
            if comment is not None:
                body["comment"] = comment
            if billable_seconds is not None:
                body["billableSeconds"] = billable_seconds
            if end_date is not None:
                body["endDate"] = end_date
            if include_non_working_days is not None:
                body["includeNonWorkingDays"] = include_non_working_days
            if attributes is not None:
                body["attributes"] = attributes
            if remaining_estimate is not None:
                body["remainingEstimate"] = remaining_estimate
            result = self.jira.put(
                f"rest/tempo-timesheets/4/worklogs/{worklog_id}", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoWorklog.from_api_response(result)
        except Exception as e:
            logger.error(f"Error updating worklog {worklog_id}: {e}")
            raise Exception(f"Error updating worklog: {e}") from e

    def delete_worklog(self, worklog_id: int) -> None:
        """Delete a Tempo worklog."""
        try:
            self.jira.delete(f"rest/tempo-timesheets/4/worklogs/{worklog_id}")
        except Exception as e:
            logger.error(f"Error deleting worklog {worklog_id}: {e}")
            raise Exception(f"Error deleting worklog: {e}") from e

    def get_approval_status(
        self, user_key: str, period_start_date: str
    ) -> list[TempoApproval]:
        """Get timesheet approval status for a user and period."""
        try:
            result = self.jira.get(
                "rest/tempo-timesheets/4/timesheet-approval/current",
                params={"userKey": user_key, "periodStartDate": period_start_date},
            )
            if isinstance(result, list):
                return [TempoApproval.from_api_response(a) for a in result]
            if isinstance(result, dict):
                return [TempoApproval.from_api_response(result)]
            return []
        except Exception as e:
            logger.warning(f"Error getting approval status: {e}")
            return []

    def get_pending_approvals(self, reviewer_key: str) -> list[TempoApproval]:
        """Get timesheets pending approval for a reviewer."""
        try:
            result = self.jira.get(
                "rest/tempo-timesheets/4/timesheet-approval/pending",
                params={"reviewerKey": reviewer_key},
            )
            if isinstance(result, list):
                return [TempoApproval.from_api_response(a) for a in result]
            return []
        except Exception as e:
            logger.warning(f"Error getting pending approvals: {e}")
            return []

    def submit_approval(
        self,
        user_key: str,
        period_date_from: str,
        action: str,
        comment: str | None = None,
        reviewer_key: str | None = None,
    ) -> TempoApproval:
        """Submit, approve, reject, or reopen a timesheet."""
        try:
            body: dict[str, Any] = {
                "user": {"key": user_key},
                "period": {"dateFrom": period_date_from},
                "action": {"name": action},
            }
            if comment:
                body["action"]["comment"] = comment
            if reviewer_key:
                body["action"]["reviewer"] = {"key": reviewer_key}
            result = self.jira.post(
                "rest/tempo-timesheets/4/timesheet-approval", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoApproval.from_api_response(result)
        except Exception as e:
            logger.error(f"Error submitting approval action '{action}': {e}")
            raise Exception(f"Error submitting approval: {e}") from e

    def get_work_attributes(self) -> list[TempoWorkAttribute]:
        """List all configured work attributes."""
        try:
            result = self.jira.get("rest/tempo-core/1/work-attribute")
            if isinstance(result, list):
                return [TempoWorkAttribute.from_api_response(a) for a in result]
            return []
        except Exception as e:
            logger.warning(f"Error getting work attributes: {e}")
            return []

    def get_user_schedule(
        self,
        user: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> TempoUserSchedule:
        """Get a user's work schedule."""
        try:
            params: dict[str, str] = {}
            if user:
                params["user"] = user
            if date_from:
                params["from"] = date_from
            if date_to:
                params["to"] = date_to
            result = self.jira.get(
                "rest/tempo-core/1/user/schedule", params=params
            )
            if not isinstance(result, dict):
                return TempoUserSchedule()
            return TempoUserSchedule.from_api_response(result)
        except Exception as e:
            logger.warning(f"Error getting user schedule: {e}")
            return TempoUserSchedule()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tempo/test_timesheets.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_atlassian/tempo/timesheets.py tests/unit/tempo/test_timesheets.py
git commit -m "feat: add TempoTimesheetsMixin with worklogs, approvals, attributes, schedule"
```

---

### Task 8: Tempo Planner Mixin

**Files:**
- Create: `src/mcp_atlassian/tempo/planner.py`
- Modify: `src/mcp_atlassian/tempo/__init__.py`
- Test: `tests/unit/tempo/test_planner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/tempo/test_planner.py`:

```python
"""Tests for the Tempo Planner mixin."""

from unittest.mock import MagicMock

import pytest

from mcp_atlassian.tempo.planner import TempoPlannerMixin


class TestTempoPlannerMixin:
    @pytest.fixture
    def planner_mixin(self, tempo_client):
        mixin = TempoPlannerMixin(config=tempo_client.config)
        mixin.jira = tempo_client.jira
        return mixin

    def test_get_teams(self, planner_mixin):
        planner_mixin.jira.get = MagicMock(return_value=[
            {"id": 1, "name": "Backend", "summary": "Backend team"},
        ])
        result = planner_mixin.get_teams()
        assert len(result) == 1
        assert result[0].name == "Backend"

    def test_get_team(self, planner_mixin):
        planner_mixin.jira.get = MagicMock(return_value={
            "id": 1, "name": "Backend", "summary": "Backend team",
        })
        result = planner_mixin.get_team(1)
        assert result.id == 1

    def test_create_team(self, planner_mixin):
        planner_mixin.jira.post = MagicMock(return_value={
            "id": 2, "name": "Frontend", "summary": "Frontend team",
        })
        result = planner_mixin.create_team(name="Frontend", summary="Frontend team")
        assert result.id == 2

    def test_get_team_members(self, planner_mixin):
        planner_mixin.jira.get = MagicMock(return_value=[{
            "id": 42,
            "member": {"name": "jdoe", "type": "USER", "displayName": "John Doe"},
            "membership": {"availability": 100, "status": "ACTIVE"},
        }])
        result = planner_mixin.get_team_members(1)
        assert len(result) == 1
        assert result[0].member_key == "jdoe"

    def test_add_team_member(self, planner_mixin):
        planner_mixin.jira.post = MagicMock(return_value={
            "id": 43,
            "member": {"name": "asmith", "type": "USER", "displayName": "Alice Smith"},
            "membership": {"availability": 80, "status": "ACTIVE"},
        })
        result = planner_mixin.add_team_member(team_id=1, member_key="asmith")
        assert result.member_key == "asmith"

    def test_remove_team_member(self, planner_mixin):
        planner_mixin.jira.delete = MagicMock(return_value=None)
        planner_mixin.remove_team_member(team_id=1, member_id=42)
        planner_mixin.jira.delete.assert_called_once()

    def test_search_allocations(self, planner_mixin):
        planner_mixin.jira.get = MagicMock(return_value=[{
            "id": 100, "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 456, "type": "ISSUE"},
            "commitment": 50, "secondsPerDay": 14400,
            "start": "2026-04-01", "end": "2026-04-30",
        }])
        result = planner_mixin.search_allocations()
        assert len(result) == 1
        assert result[0].commitment == 50

    def test_create_allocation(self, planner_mixin):
        planner_mixin.jira.post = MagicMock(return_value={
            "id": 101, "assignee": {"key": "jdoe", "type": "USER"},
            "planItem": {"id": 456, "type": "ISSUE"},
            "commitment": 100, "secondsPerDay": 28800,
            "start": "2026-04-01", "end": "2026-04-30",
        })
        result = planner_mixin.create_allocation(
            assignee_key="jdoe", assignee_type="USER",
            plan_item_id=456, plan_item_type="ISSUE",
            commitment=100, seconds_per_day=28800,
            start="2026-04-01", end="2026-04-30",
        )
        assert result.id == 101

    def test_delete_allocation(self, planner_mixin):
        planner_mixin.jira.delete = MagicMock(return_value=None)
        planner_mixin.delete_allocation(100)
        planner_mixin.jira.delete.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tempo/test_planner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TempoPlannerMixin**

Create `src/mcp_atlassian/tempo/planner.py`:

```python
"""Module for Tempo Planner operations (Teams + Allocations)."""

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


class TempoPlannerMixin(TempoClient):
    """Mixin for Tempo Planner operations."""

    def get_teams(self, expand: str | None = None) -> list[TempoTeam]:
        """List all Tempo teams."""
        try:
            params: dict[str, str] = {}
            if expand:
                params["expand"] = expand
            result = self.jira.get("rest/tempo-teams/2/team", params=params)
            if isinstance(result, list):
                return [TempoTeam.from_api_response(t) for t in result]
            return []
        except Exception as e:
            logger.warning(f"Error getting teams: {e}")
            return []

    def get_team(self, team_id: int) -> TempoTeam:
        """Get a single team by ID."""
        try:
            result = self.jira.get(f"rest/tempo-teams/2/team/{team_id}")
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoTeam.from_api_response(result)
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise ValueError(f"Team {team_id} not found.") from e
            raise

    def create_team(
        self, name: str, summary: str | None = None,
        lead_user_key: str | None = None,
    ) -> TempoTeam:
        """Create a new Tempo team."""
        try:
            body: dict[str, Any] = {"name": name}
            if summary:
                body["summary"] = summary
            if lead_user_key:
                body["lead"] = lead_user_key
            result = self.jira.post("rest/tempo-teams/2/team", data=body)
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoTeam.from_api_response(result)
        except Exception as e:
            logger.error(f"Error creating team '{name}': {e}")
            raise Exception(f"Error creating team: {e}") from e

    def get_team_roles(self) -> list[TempoTeamRole]:
        """List all available team roles."""
        try:
            result = self.jira.get("rest/tempo-teams/2/role")
            if isinstance(result, list):
                return [TempoTeamRole.from_api_response(r) for r in result]
            return []
        except Exception as e:
            logger.warning(f"Error getting team roles: {e}")
            return []

    def get_team_members(
        self, team_id: int, member_type: str | None = None,
        only_active: bool = True,
    ) -> list[TempoTeamMember]:
        """List members of a team."""
        try:
            params: dict[str, Any] = {"onlyActive": str(only_active).lower()}
            if member_type:
                params["type"] = member_type
            result = self.jira.get(
                f"rest/tempo-teams/2/team/{team_id}/member", params=params
            )
            if isinstance(result, list):
                return [TempoTeamMember.from_api_response(m) for m in result]
            return []
        except Exception as e:
            logger.warning(f"Error getting team {team_id} members: {e}")
            return []

    def add_team_member(
        self, team_id: int, member_key: str, member_type: str = "USER",
        role_id: int | None = None, availability: int = 100,
        date_from: str | None = None, date_to: str | None = None,
    ) -> TempoTeamMember:
        """Add a member to a team."""
        try:
            body: dict[str, Any] = {
                "member": {"name": member_key, "type": member_type},
                "membership": {"availability": availability},
            }
            if role_id is not None:
                body["membership"]["role"] = {"id": role_id}
            if date_from:
                body["membership"]["dateFrom"] = date_from
            if date_to:
                body["membership"]["dateTo"] = date_to
            result = self.jira.post(
                f"rest/tempo-teams/2/team/{team_id}/member", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoTeamMember.from_api_response(result)
        except Exception as e:
            logger.error(f"Error adding member to team {team_id}: {e}")
            raise Exception(f"Error adding team member: {e}") from e

    def update_team_member(
        self, team_id: int, member_id: int,
        role_id: int | None = None, availability: int | None = None,
        date_from: str | None = None, date_to: str | None = None,
    ) -> TempoTeamMember:
        """Update a team membership."""
        try:
            body: dict[str, Any] = {"membership": {}}
            if role_id is not None:
                body["membership"]["role"] = {"id": role_id}
            if availability is not None:
                body["membership"]["availability"] = availability
            if date_from is not None:
                body["membership"]["dateFrom"] = date_from
            if date_to is not None:
                body["membership"]["dateTo"] = date_to
            result = self.jira.put(
                f"rest/tempo-teams/2/team/{team_id}/member/{member_id}", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoTeamMember.from_api_response(result)
        except Exception as e:
            logger.error(f"Error updating team member {member_id}: {e}")
            raise Exception(f"Error updating team member: {e}") from e

    def remove_team_member(self, team_id: int, member_id: int) -> None:
        """Remove a member from a team."""
        try:
            self.jira.delete(
                f"rest/tempo-teams/2/team/{team_id}/member/{member_id}"
            )
        except Exception as e:
            logger.error(f"Error removing team member {member_id}: {e}")
            raise Exception(f"Error removing team member: {e}") from e

    def search_allocations(
        self, assignee_keys: list[str] | None = None,
        assignee_type: str | None = None,
        plan_item_id: int | None = None,
        plan_item_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[TempoAllocation]:
        """Search allocations by filters."""
        try:
            params: dict[str, Any] = {}
            if assignee_keys:
                params["assigneeKeys"] = ",".join(assignee_keys)
            if assignee_type:
                params["assigneeType"] = assignee_type
            if plan_item_id is not None:
                params["planItemId"] = plan_item_id
            if plan_item_type:
                params["planItemType"] = plan_item_type
            if start_date:
                params["startDate"] = start_date
            if end_date:
                params["endDate"] = end_date
            result = self.jira.get(
                "rest/tempo-planning/1/allocation", params=params
            )
            if isinstance(result, list):
                return [TempoAllocation.from_api_response(a) for a in result]
            return []
        except Exception as e:
            logger.warning(f"Error searching allocations: {e}")
            return []

    def create_allocation(
        self, assignee_key: str, assignee_type: str,
        plan_item_id: int, plan_item_type: str,
        commitment: int, seconds_per_day: int,
        start: str, end: str,
        description: str | None = None,
        include_non_working_days: bool = False,
    ) -> TempoAllocation:
        """Create a resource allocation."""
        try:
            body: dict[str, Any] = {
                "assignee": {"key": assignee_key, "type": assignee_type},
                "planItem": {"id": plan_item_id, "type": plan_item_type},
                "commitment": commitment,
                "secondsPerDay": seconds_per_day,
                "start": start,
                "end": end,
                "includeNonWorkingDays": include_non_working_days,
            }
            if description:
                body["description"] = description
            result = self.jira.post(
                "rest/tempo-planning/1/allocation", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoAllocation.from_api_response(result)
        except Exception as e:
            logger.error(f"Error creating allocation: {e}")
            raise Exception(f"Error creating allocation: {e}") from e

    def update_allocation(
        self, allocation_id: int,
        commitment: int | None = None,
        seconds_per_day: int | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        include_non_working_days: bool | None = None,
    ) -> TempoAllocation:
        """Update an existing allocation."""
        try:
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
            result = self.jira.put(
                f"rest/tempo-planning/1/allocation/{allocation_id}", data=body
            )
            if not isinstance(result, dict):
                raise TypeError(f"Unexpected response type: {type(result)}")
            return TempoAllocation.from_api_response(result)
        except Exception as e:
            logger.error(f"Error updating allocation {allocation_id}: {e}")
            raise Exception(f"Error updating allocation: {e}") from e

    def delete_allocation(self, allocation_id: int) -> None:
        """Delete an allocation."""
        try:
            self.jira.delete(
                f"rest/tempo-planning/1/allocation/{allocation_id}"
            )
        except Exception as e:
            logger.error(f"Error deleting allocation {allocation_id}: {e}")
            raise Exception(f"Error deleting allocation: {e}") from e
```

- [ ] **Step 4: Complete TempoFetcher composition**

Update `src/mcp_atlassian/tempo/__init__.py`:

```python
"""Tempo API module for mcp_atlassian."""

from .client import TempoClient
from .config import TempoConfig
from .planner import TempoPlannerMixin
from .timesheets import TempoTimesheetsMixin


class TempoFetcher(
    TempoTimesheetsMixin,
    TempoPlannerMixin,
):
    """The main Tempo client class providing access to all Tempo operations."""

    pass


__all__ = ["TempoFetcher", "TempoClient", "TempoConfig"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tempo/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_atlassian/tempo/planner.py src/mcp_atlassian/tempo/__init__.py tests/unit/tempo/test_planner.py
git commit -m "feat: add TempoPlannerMixin with teams, members, allocations + TempoFetcher"
```

---

### Task 9: Tempo MCP Server (tools registration)

**Files:**
- Create: `src/mcp_atlassian/servers/tempo.py`
- Create: `src/mcp_atlassian/servers/tempo_dependencies.py`

This is the largest task. It creates the Tempo FastMCP server with all 22 tools. The tool implementations follow the exact same pattern as `servers/jira.py` — async functions with `@tempo_mcp.tool()`, `Annotated` params, JSON responses with `success` flag.

- [ ] **Step 1: Create the dependency provider**

Create `src/mcp_atlassian/servers/tempo_dependencies.py`:

```python
"""Dependency provider for TempoFetcher."""

from __future__ import annotations

import logging

from fastmcp import Context

from mcp_atlassian.servers.context import MainAppContext
from mcp_atlassian.tempo import TempoConfig, TempoFetcher

logger = logging.getLogger("mcp-atlassian.servers.tempo_dependencies")


async def get_tempo_fetcher(ctx: Context) -> TempoFetcher:
    """Get or create a TempoFetcher instance from the request context."""
    lifespan_ctx_dict = ctx.request_context.lifespan_context
    app_lifespan_state: MainAppContext | None = (
        lifespan_ctx_dict.get("app_lifespan_context")
        if isinstance(lifespan_ctx_dict, dict)
        else None
    )

    if app_lifespan_state is None:
        raise ValueError("Application context is not available.")

    tempo_config = getattr(app_lifespan_state, "full_tempo_config", None)
    if tempo_config is None:
        raise ValueError(
            "Tempo is not configured. Set TEMPO_ENABLED=true and configure Jira credentials."
        )

    return TempoFetcher(config=tempo_config)
```

- [ ] **Step 2: Create the Tempo server with all 22 tools**

Create `src/mcp_atlassian/servers/tempo.py`. This file registers all 22 tools. The pattern for each tool is identical to the Jira server tools — I'll show the structure and a few representative tools:

```python
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
    date_from: Annotated[str, Field(description="Start date (yyyy-MM-dd)")],
    date_to: Annotated[str, Field(description="End date (yyyy-MM-dd)")],
    worker_keys: Annotated[str | None, Field(description="Comma-separated user keys to filter by")] = None,
    project_keys: Annotated[str | None, Field(description="Comma-separated project keys to filter by")] = None,
    team_ids: Annotated[str | None, Field(description="Comma-separated Tempo team IDs to filter by")] = None,
    epic_keys: Annotated[str | None, Field(description="Comma-separated epic keys to filter by")] = None,
    task_keys: Annotated[str | None, Field(description="Comma-separated issue keys to filter by")] = None,
) -> str:
    """Search Tempo worklogs by date range and optional filters."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        worklogs = tempo.search_worklogs(
            date_from=date_from, date_to=date_to,
            worker_keys=worker_keys.split(",") if worker_keys else None,
            project_keys=project_keys.split(",") if project_keys else None,
            team_ids=[int(x) for x in team_ids.split(",")] if team_ids else None,
            epic_keys=epic_keys.split(",") if epic_keys else None,
            task_keys=task_keys.split(",") if task_keys else None,
        )
        return json.dumps(
            {"success": True, "worklogs": [w.to_simplified_dict() for w in worklogs], "count": len(worklogs)},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_search_worklogs failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_worklog(
    ctx: Context,
    worklog_id: Annotated[int, Field(description="Tempo worklog ID")],
) -> str:
    """Get a single Tempo worklog by ID."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        wl = tempo.get_worklog(worklog_id)
        return json.dumps({"success": True, "worklog": wl.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        log_level = logging.WARNING if isinstance(e, ValueError) else logging.ERROR
        logger.log(log_level, f"tempo_get_worklog failed for {worklog_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_create_worklog(
    ctx: Context,
    worker: Annotated[str, Field(description="User key")],
    issue_key: Annotated[str, Field(description="Jira issue key (e.g. PROJ-123)")],
    started: Annotated[str, Field(description="Start date (yyyy-MM-dd)")],
    time_spent_seconds: Annotated[int, Field(description="Time spent in seconds")],
    comment: Annotated[str | None, Field(description="Worklog comment")] = None,
    billable_seconds: Annotated[int | None, Field(description="Billable time in seconds")] = None,
    end_date: Annotated[str | None, Field(description="End date for multi-day worklogs (yyyy-MM-dd)")] = None,
    include_non_working_days: Annotated[bool, Field(description="Include non-working days")] = False,
    remaining_estimate: Annotated[int | None, Field(description="Remaining estimate in seconds")] = None,
) -> str:
    """Create a Tempo worklog."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        wl = tempo.create_worklog(
            worker=worker, issue_key=issue_key, started=started,
            time_spent_seconds=time_spent_seconds, comment=comment,
            billable_seconds=billable_seconds, end_date=end_date,
            include_non_working_days=include_non_working_days,
            remaining_estimate=remaining_estimate,
        )
        return json.dumps({"success": True, "worklog": wl.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_create_worklog failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_update_worklog(
    ctx: Context,
    worklog_id: Annotated[int, Field(description="Tempo worklog ID")],
    started: Annotated[str | None, Field(description="New start date (yyyy-MM-dd)")] = None,
    time_spent_seconds: Annotated[int | None, Field(description="New time spent in seconds")] = None,
    comment: Annotated[str | None, Field(description="New comment")] = None,
    billable_seconds: Annotated[int | None, Field(description="New billable seconds")] = None,
    end_date: Annotated[str | None, Field(description="New end date (yyyy-MM-dd)")] = None,
    include_non_working_days: Annotated[bool | None, Field(description="Include non-working days")] = None,
    remaining_estimate: Annotated[int | None, Field(description="Remaining estimate in seconds")] = None,
) -> str:
    """Update an existing Tempo worklog."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        wl = tempo.update_worklog(
            worklog_id=worklog_id, started=started,
            time_spent_seconds=time_spent_seconds, comment=comment,
            billable_seconds=billable_seconds, end_date=end_date,
            include_non_working_days=include_non_working_days,
            remaining_estimate=remaining_estimate,
        )
        return json.dumps({"success": True, "worklog": wl.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_update_worklog failed for {worklog_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_delete_worklog(
    ctx: Context,
    worklog_id: Annotated[int, Field(description="Tempo worklog ID to delete")],
) -> str:
    """Delete a Tempo worklog."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        tempo.delete_worklog(worklog_id)
        return json.dumps({"success": True, "deleted": worklog_id}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_delete_worklog failed for {worklog_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Approval Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_approval_status(
    ctx: Context,
    user_key: Annotated[str, Field(description="User key")],
    period_start_date: Annotated[str, Field(description="Period start date (yyyy-MM-dd)")],
) -> str:
    """Get timesheet approval status for a user and period."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        approvals = tempo.get_approval_status(user_key, period_start_date)
        return json.dumps(
            {"success": True, "approvals": [a.to_simplified_dict() for a in approvals]},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_approval_status failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_pending_approvals(
    ctx: Context,
    reviewer_key: Annotated[str, Field(description="Reviewer user key")],
) -> str:
    """Get timesheets pending approval for a reviewer."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        approvals = tempo.get_pending_approvals(reviewer_key)
        return json.dumps(
            {"success": True, "approvals": [a.to_simplified_dict() for a in approvals]},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_pending_approvals failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_submit_approval(
    ctx: Context,
    user_key: Annotated[str, Field(description="Target user key")],
    period_date_from: Annotated[str, Field(description="Period start date (yyyy-MM-dd)")],
    action: Annotated[str, Field(description="Action: submit, approve, reject, or reopen")],
    comment: Annotated[str | None, Field(description="Optional comment")] = None,
    reviewer_key: Annotated[str | None, Field(description="Reviewer key (required for 'submit' action)")] = None,
) -> str:
    """Submit, approve, reject, or reopen a timesheet."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        approval = tempo.submit_approval(
            user_key=user_key, period_date_from=period_date_from,
            action=action, comment=comment, reviewer_key=reviewer_key,
        )
        return json.dumps({"success": True, "approval": approval.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_submit_approval failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Work Attributes & Schedule ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_work_attributes(ctx: Context) -> str:
    """List all configured Tempo work attributes."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        attrs = tempo.get_work_attributes()
        return json.dumps(
            {"success": True, "attributes": [a.to_simplified_dict() for a in attrs]},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_work_attributes failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_user_schedule(
    ctx: Context,
    user: Annotated[str | None, Field(description="Username (defaults to current user)")] = None,
    date_from: Annotated[str | None, Field(description="Start date (yyyy-MM-dd)")] = None,
    date_to: Annotated[str | None, Field(description="End date (yyyy-MM-dd)")] = None,
) -> str:
    """Get a user's work schedule (working days, required hours)."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        schedule = tempo.get_user_schedule(user=user, date_from=date_from, date_to=date_to)
        return json.dumps({"success": True, "schedule": schedule.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_get_user_schedule failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Team Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_teams(
    ctx: Context,
    expand: Annotated[str | None, Field(description="Expand fields: 'leaduser', 'teamprogram', or both")] = None,
) -> str:
    """List all Tempo teams."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        teams = tempo.get_teams(expand=expand)
        return json.dumps(
            {"success": True, "teams": [t.to_simplified_dict() for t in teams], "count": len(teams)},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_teams failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_team(
    ctx: Context,
    team_id: Annotated[int, Field(description="Tempo team ID")],
) -> str:
    """Get a single Tempo team by ID."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        team = tempo.get_team(team_id)
        return json.dumps({"success": True, "team": team.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        log_level = logging.WARNING if isinstance(e, ValueError) else logging.ERROR
        logger.log(log_level, f"tempo_get_team failed for {team_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_create_team(
    ctx: Context,
    name: Annotated[str, Field(description="Team name")],
    summary: Annotated[str | None, Field(description="Team summary/description")] = None,
    lead_user_key: Annotated[str | None, Field(description="Team lead user key")] = None,
) -> str:
    """Create a new Tempo team."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        team = tempo.create_team(name=name, summary=summary, lead_user_key=lead_user_key)
        return json.dumps({"success": True, "team": team.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_create_team failed for '{name}': {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_team_roles(ctx: Context) -> str:
    """List all available Tempo team roles."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        roles = tempo.get_team_roles()
        return json.dumps(
            {"success": True, "roles": [r.to_simplified_dict() for r in roles]},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_team_roles failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Team Member Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_get_team_members(
    ctx: Context,
    team_id: Annotated[int, Field(description="Tempo team ID")],
    member_type: Annotated[str | None, Field(description="Filter: 'USER' or 'GROUP'")] = None,
    only_active: Annotated[bool, Field(description="Only active members")] = True,
) -> str:
    """List members of a Tempo team."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        members = tempo.get_team_members(team_id, member_type=member_type, only_active=only_active)
        return json.dumps(
            {"success": True, "members": [m.to_simplified_dict() for m in members], "count": len(members)},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_get_team_members failed for team {team_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_add_team_member(
    ctx: Context,
    team_id: Annotated[int, Field(description="Tempo team ID")],
    member_key: Annotated[str, Field(description="User key or group name")],
    member_type: Annotated[str, Field(description="'USER' or 'GROUP'")] = "USER",
    role_id: Annotated[int | None, Field(description="Team role ID")] = None,
    availability: Annotated[int, Field(description="Availability percentage (0-100)")] = 100,
    date_from: Annotated[str | None, Field(description="Membership start date (yyyy-MM-dd)")] = None,
    date_to: Annotated[str | None, Field(description="Membership end date (yyyy-MM-dd)")] = None,
) -> str:
    """Add a member (user or group) to a Tempo team."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        member = tempo.add_team_member(
            team_id=team_id, member_key=member_key, member_type=member_type,
            role_id=role_id, availability=availability,
            date_from=date_from, date_to=date_to,
        )
        return json.dumps({"success": True, "member": member.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_add_team_member failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_update_team_member(
    ctx: Context,
    team_id: Annotated[int, Field(description="Tempo team ID")],
    member_id: Annotated[int, Field(description="Membership ID")],
    role_id: Annotated[int | None, Field(description="New role ID")] = None,
    availability: Annotated[int | None, Field(description="New availability percentage (0-100)")] = None,
    date_from: Annotated[str | None, Field(description="New start date (yyyy-MM-dd)")] = None,
    date_to: Annotated[str | None, Field(description="New end date (yyyy-MM-dd)")] = None,
) -> str:
    """Update a Tempo team membership."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        member = tempo.update_team_member(
            team_id=team_id, member_id=member_id,
            role_id=role_id, availability=availability,
            date_from=date_from, date_to=date_to,
        )
        return json.dumps({"success": True, "member": member.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_update_team_member failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_remove_team_member(
    ctx: Context,
    team_id: Annotated[int, Field(description="Tempo team ID")],
    member_id: Annotated[int, Field(description="Membership ID to remove")],
) -> str:
    """Remove a member from a Tempo team."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        tempo.remove_team_member(team_id=team_id, member_id=member_id)
        return json.dumps({"success": True, "removed_member_id": member_id}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_remove_team_member failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


# --- Allocation Tools ---


@tempo_mcp.tool(tags={"tempo", "read"})
async def tempo_search_allocations(
    ctx: Context,
    assignee_keys: Annotated[str | None, Field(description="Comma-separated user keys")] = None,
    assignee_type: Annotated[str | None, Field(description="'USER' or 'TEAM'")] = None,
    plan_item_id: Annotated[int | None, Field(description="Plan item ID (issue/project/epic)")] = None,
    plan_item_type: Annotated[str | None, Field(description="ISSUE, PROJECT, EPIC, SPRINT, VERSION, or COMPONENT")] = None,
    start_date: Annotated[str | None, Field(description="Start date filter (yyyy-MM-dd)")] = None,
    end_date: Annotated[str | None, Field(description="End date filter (yyyy-MM-dd)")] = None,
) -> str:
    """Search Tempo allocations by filters."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        allocations = tempo.search_allocations(
            assignee_keys=assignee_keys.split(",") if assignee_keys else None,
            assignee_type=assignee_type,
            plan_item_id=plan_item_id, plan_item_type=plan_item_type,
            start_date=start_date, end_date=end_date,
        )
        return json.dumps(
            {"success": True, "allocations": [a.to_simplified_dict() for a in allocations], "count": len(allocations)},
            indent=2, ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"tempo_search_allocations failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_create_allocation(
    ctx: Context,
    assignee_key: Annotated[str, Field(description="User key or team ID")],
    assignee_type: Annotated[str, Field(description="'USER' or 'TEAM'")],
    plan_item_id: Annotated[int, Field(description="Issue/project/epic ID")],
    plan_item_type: Annotated[str, Field(description="ISSUE, PROJECT, EPIC, SPRINT, VERSION, or COMPONENT")],
    commitment: Annotated[int, Field(description="Commitment percentage (1-100)")],
    seconds_per_day: Annotated[int, Field(description="Planned seconds per day")],
    start: Annotated[str, Field(description="Start date (yyyy-MM-dd)")],
    end: Annotated[str, Field(description="End date (yyyy-MM-dd)")],
    description: Annotated[str | None, Field(description="Description")] = None,
    include_non_working_days: Annotated[bool, Field(description="Include non-working days")] = False,
) -> str:
    """Create a Tempo resource allocation."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        allocation = tempo.create_allocation(
            assignee_key=assignee_key, assignee_type=assignee_type,
            plan_item_id=plan_item_id, plan_item_type=plan_item_type,
            commitment=commitment, seconds_per_day=seconds_per_day,
            start=start, end=end, description=description,
            include_non_working_days=include_non_working_days,
        )
        return json.dumps({"success": True, "allocation": allocation.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_create_allocation failed: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_update_allocation(
    ctx: Context,
    allocation_id: Annotated[int, Field(description="Allocation ID")],
    commitment: Annotated[int | None, Field(description="New commitment percentage (1-100)")] = None,
    seconds_per_day: Annotated[int | None, Field(description="New seconds per day")] = None,
    start: Annotated[str | None, Field(description="New start date (yyyy-MM-dd)")] = None,
    end: Annotated[str | None, Field(description="New end date (yyyy-MM-dd)")] = None,
    description: Annotated[str | None, Field(description="New description")] = None,
    include_non_working_days: Annotated[bool | None, Field(description="Include non-working days")] = None,
) -> str:
    """Update an existing Tempo allocation."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        allocation = tempo.update_allocation(
            allocation_id=allocation_id, commitment=commitment,
            seconds_per_day=seconds_per_day, start=start, end=end,
            description=description, include_non_working_days=include_non_working_days,
        )
        return json.dumps({"success": True, "allocation": allocation.to_simplified_dict()}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_update_allocation failed for {allocation_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@tempo_mcp.tool(tags={"tempo", "write"})
@check_write_access
async def tempo_delete_allocation(
    ctx: Context,
    allocation_id: Annotated[int, Field(description="Allocation ID to delete")],
) -> str:
    """Delete a Tempo allocation."""
    tempo = await get_tempo_fetcher(ctx)
    try:
        tempo.delete_allocation(allocation_id)
        return json.dumps({"success": True, "deleted": allocation_id}, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"tempo_delete_allocation failed for {allocation_id}: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
```

- [ ] **Step 3: Commit**

```bash
git add src/mcp_atlassian/servers/tempo.py src/mcp_atlassian/servers/tempo_dependencies.py
git commit -m "feat: add Tempo MCP server with 22 tools (worklogs, approvals, teams, allocations)"
```

---

### Task 10: Server Integration (mount, service detection, CLI, context)

**Files:**
- Modify: `src/mcp_atlassian/utils/environment.py`
- Modify: `src/mcp_atlassian/servers/context.py`
- Modify: `src/mcp_atlassian/servers/main.py`
- Modify: `src/mcp_atlassian/__init__.py`
- Modify: `src/mcp_atlassian/exceptions.py`

- [ ] **Step 1: Add TempoNotAvailableError**

Add to `src/mcp_atlassian/exceptions.py`:

```python
class TempoNotAvailableError(Exception):
    """Raised when Tempo plugin is not available on the Jira instance."""

    pass
```

- [ ] **Step 2: Add Tempo to service detection**

In `src/mcp_atlassian/utils/environment.py`, add after the Bitbucket section (before the "not configured" logging):

```python
    tempo_is_setup = False
    tempo_enabled = os.getenv("TEMPO_ENABLED", "").lower() in ("true", "1", "yes")
    if tempo_enabled and jira_is_setup:
        tempo_is_setup = True
        logger.info("Tempo enabled — will use Jira credentials for Tempo API access")
    elif tempo_enabled and not jira_is_setup:
        logger.warning("TEMPO_ENABLED is set but Jira is not configured. Tempo tools will be unavailable.")
```

Add `"tempo": tempo_is_setup` to the return dict. Add logging for Tempo not configured:

```python
    if not tempo_is_setup:
        logger.info(
            "Tempo is not enabled. Set TEMPO_ENABLED=true to enable Tempo tools."
        )
```

- [ ] **Step 3: Add Tempo config to MainAppContext**

In `src/mcp_atlassian/servers/context.py`, add:

```python
if TYPE_CHECKING:
    from mcp_atlassian.tempo.config import TempoConfig
```

And add to `MainAppContext`:

```python
    full_tempo_config: TempoConfig | None = None
```

- [ ] **Step 4: Update lifespan handler in main.py**

In `src/mcp_atlassian/servers/main.py`:

Add imports at top:
```python
from mcp_atlassian.tempo import TempoFetcher
from mcp_atlassian.tempo.config import TempoConfig
from .tempo import tempo_mcp
```

In `main_lifespan`, after the bitbucket config block, add:
```python
    loaded_tempo_config: TempoConfig | None = None

    if services.get("tempo"):
        try:
            tempo_config = TempoConfig.from_env()
            if tempo_config.is_auth_configured():
                loaded_tempo_config = tempo_config
                logger.info(
                    "Tempo configuration loaded and authentication is configured."
                )
            else:
                logger.warning(
                    "Tempo is enabled but Jira authentication is not configured. Tempo tools will be unavailable."
                )
        except Exception as e:
            logger.error(f"Failed to load Tempo configuration: {e}", exc_info=True)
```

Update `MainAppContext` creation:
```python
    app_context = MainAppContext(
        full_jira_config=loaded_jira_config,
        full_confluence_config=loaded_confluence_config,
        full_bitbucket_config=loaded_bitbucket_config,
        full_tempo_config=loaded_tempo_config,
        read_only=read_only,
        enabled_tools=enabled_tools,
    )
```

In `_mcp_list_tools`, add Tempo tool filtering (after the bitbucket check):
```python
            is_tempo_tool = "tempo" in tool_tags
```

And in the filtering logic:
```python
                if is_tempo_tool and not app_lifespan_state.full_tempo_config:
                    logger.debug(
                        f"Excluding Tempo tool '{registered_name}' as Tempo configuration is incomplete."
                    )
                    service_configured_and_available = False
```

Update the fallback warning condition:
```python
            elif is_jira_tool or is_confluence_tool or is_bitbucket_tool or is_tempo_tool:
```

Mount the Tempo server:
```python
main_mcp.mount("tempo", tempo_mcp)
```

- [ ] **Step 5: Add CLI flag**

In `src/mcp_atlassian/__init__.py`, add CLI option (after `--bitbucket-ssl-verify`):

```python
@click.option(
    "--tempo-enabled",
    is_flag=True,
    help="Enable Tempo Timesheets and Planner tools (requires Jira configuration)",
)
```

Add `tempo_enabled: bool` to `main()` params.

Add env var setting:
```python
    if click_ctx and was_option_provided(click_ctx, "tempo_enabled"):
        os.environ["TEMPO_ENABLED"] = str(tempo_enabled).lower()
```

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/unit/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/mcp_atlassian/utils/environment.py src/mcp_atlassian/servers/context.py src/mcp_atlassian/servers/main.py src/mcp_atlassian/__init__.py src/mcp_atlassian/exceptions.py
git commit -m "feat: integrate Tempo MCP server with service detection, CLI, and tool filtering"
```

---

### Task 11: Server-Level Tests

**Files:**
- Test: `tests/unit/servers/test_tempo_server.py`

- [ ] **Step 1: Write server-level tests**

Create `tests/unit/servers/test_tempo_server.py`:

```python
"""Tests for Tempo server tool registration and filtering."""

import pytest

from mcp_atlassian.servers.tempo import tempo_mcp


class TestTempoServerRegistration:
    """Verify tools are registered correctly on the Tempo MCP server."""

    @pytest.mark.asyncio
    async def test_tempo_tools_registered(self):
        """Check that all 22 Tempo tools are registered."""
        tools = await tempo_mcp.get_tools()
        assert len(tools) == 22, f"Expected 22 tools, got {len(tools)}: {list(tools.keys())}"

    @pytest.mark.asyncio
    async def test_tempo_read_tools_count(self):
        """Check read tool count."""
        tools = await tempo_mcp.get_tools()
        read_tools = [t for t in tools.values() if "read" in t.tags]
        assert len(read_tools) == 11, f"Expected 11 read tools, got {len(read_tools)}"

    @pytest.mark.asyncio
    async def test_tempo_write_tools_count(self):
        """Check write tool count."""
        tools = await tempo_mcp.get_tools()
        write_tools = [t for t in tools.values() if "write" in t.tags]
        assert len(write_tools) == 11, f"Expected 11 write tools, got {len(write_tools)}"

    @pytest.mark.asyncio
    async def test_all_tempo_tools_have_tempo_tag(self):
        """All tools must have the 'tempo' tag for service filtering."""
        tools = await tempo_mcp.get_tools()
        for name, tool in tools.items():
            assert "tempo" in tool.tags, f"Tool '{name}' missing 'tempo' tag"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/unit/servers/test_tempo_server.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/servers/test_tempo_server.py
git commit -m "test: add server-level tests for Tempo tool registration and filtering"
```

---

### Task 12: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/unit/ -v --timeout=30`
Expected: All tests PASS, no regressions

- [ ] **Step 2: Verify tool counts**

Run a quick check script:
```bash
python -c "
import asyncio
from mcp_atlassian.servers.jira import jira_mcp
from mcp_atlassian.servers.tempo import tempo_mcp

async def main():
    jira_tools = await jira_mcp.get_tools()
    tempo_tools = await tempo_mcp.get_tools()
    print(f'Jira tools: {len(jira_tools)}')
    print(f'Tempo tools: {len(tempo_tools)}')
    print(f'Total: {len(jira_tools) + len(tempo_tools)}')
asyncio.run(main())
"
```
Expected: Jira tools: 39, Tempo tools: 22, Total: 61

- [ ] **Step 3: Verify imports are clean**

```bash
python -c "from mcp_atlassian.tempo import TempoFetcher; print('TempoFetcher OK')"
python -c "from mcp_atlassian.jira import JiraFetcher; f = JiraFetcher.__mro__; print('GroupsMixin' in str(f))"
python -c "from mcp_atlassian.models.jira.group import JiraGroup; print('JiraGroup OK')"
python -c "from mcp_atlassian.models.tempo import TempoWorklog, TempoTeam; print('Tempo models OK')"
```

- [ ] **Step 4: Final commit with any cleanup**

If any cleanup needed:
```bash
git add -A
git commit -m "chore: final cleanup for Jira Groups + Tempo MCP server"
```
