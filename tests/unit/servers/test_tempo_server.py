"""Tests for Tempo server tool registration and filtering."""

import pytest

from mcp_atlassian.servers.tempo import tempo_mcp


class TestTempoServerRegistration:

    @pytest.mark.anyio
    async def test_tempo_tools_registered(self):
        """Check that all 22 Tempo tools are registered."""
        tools = await tempo_mcp.get_tools()
        assert len(tools) == 22, f"Expected 22 tools, got {len(tools)}: {list(tools.keys())}"

    @pytest.mark.anyio
    async def test_tempo_read_tools_count(self):
        """Check read tool count (11 read tools)."""
        tools = await tempo_mcp.get_tools()
        read_tools = [name for name, t in tools.items() if "read" in t.tags]
        assert len(read_tools) == 11, f"Expected 11 read tools, got {len(read_tools)}: {read_tools}"

    @pytest.mark.anyio
    async def test_tempo_write_tools_count(self):
        """Check write tool count (11 write tools)."""
        tools = await tempo_mcp.get_tools()
        write_tools = [name for name, t in tools.items() if "write" in t.tags]
        assert len(write_tools) == 11, f"Expected 11 write tools, got {len(write_tools)}: {write_tools}"

    @pytest.mark.anyio
    async def test_all_tempo_tools_have_tempo_tag(self):
        """All tools must have the 'tempo' tag for service filtering."""
        tools = await tempo_mcp.get_tools()
        for name, tool in tools.items():
            assert "tempo" in tool.tags, f"Tool '{name}' missing 'tempo' tag"

    @pytest.mark.anyio
    async def test_expected_tool_names(self):
        """Verify key tool names are present."""
        tools = await tempo_mcp.get_tools()
        expected = [
            "tempo_search_worklogs", "tempo_get_worklog", "tempo_create_worklog",
            "tempo_update_worklog", "tempo_delete_worklog",
            "tempo_get_approval_status", "tempo_get_pending_approvals", "tempo_submit_approval",
            "tempo_get_work_attributes", "tempo_get_user_schedule",
            "tempo_get_teams", "tempo_get_team", "tempo_create_team", "tempo_get_team_roles",
            "tempo_get_team_members", "tempo_add_team_member", "tempo_update_team_member", "tempo_remove_team_member",
            "tempo_search_allocations", "tempo_create_allocation", "tempo_update_allocation", "tempo_delete_allocation",
        ]
        tool_names = set(tools.keys())
        for name in expected:
            assert name in tool_names, f"Expected tool '{name}' not found"
