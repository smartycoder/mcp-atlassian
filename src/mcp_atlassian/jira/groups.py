"""Module for Jira group operations."""

import logging
from typing import Any

from requests.exceptions import HTTPError

from ..exceptions import MCPAtlassianAuthenticationError
from ..models.jira import JiraGroup, JiraGroupMembersResult
from .client import JiraClient

logger = logging.getLogger("mcp-jira")


class GroupsMixin(JiraClient):
    """Mixin for Jira group operations."""

    def search_groups(self, query: str, max_results: int = 50) -> list[JiraGroup]:
        """
        Search for Jira groups by name.

        Args:
            query: The search query string to filter groups by name.
            max_results: Maximum number of groups to return (default 50).

        Returns:
            List of JiraGroup models matching the query. Returns an empty list
            on any error.
        """
        try:
            result = self.jira.get(
                "rest/api/2/groups/picker",
                params={"query": query, "maxResults": max_results},
            )
            if not isinstance(result, dict):
                logger.warning(
                    f"Unexpected return value type from `jira.get`: {type(result)}"
                )
                return []

            groups_data = result.get("groups", [])
            return [JiraGroup.from_api_response(g) for g in groups_data]

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
        """
        Get members of a Jira group.

        Args:
            group_name: The name of the group whose members to retrieve.
            include_inactive: Whether to include inactive users (default False).
            start_at: Index of the first result to return for pagination (default 0).
            max_results: Maximum number of members to return (default 50).

        Returns:
            JiraGroupMembersResult containing paginated group members.

        Raises:
            ValueError: If the group does not exist (HTTP 404).
            MCPAtlassianAuthenticationError: If authentication fails (HTTP 401/403).
        """
        try:
            result = self.jira.get(
                "rest/api/2/group/member",
                params={
                    "groupname": group_name,
                    "includeInactiveUsers": include_inactive,
                    "startAt": start_at,
                    "maxResults": max_results,
                },
            )
            if not isinstance(result, dict):
                msg = f"Unexpected return value type from `jira.get`: {type(result)}"
                logger.error(msg)
                raise TypeError(msg)

            return JiraGroupMembersResult.from_api_response(result)

        except HTTPError as http_err:
            if http_err.response is not None:
                status = http_err.response.status_code
                if status == 404:
                    raise ValueError(
                        f"Group '{group_name}' not found."
                    ) from http_err
                if status in (401, 403):
                    error_msg = (
                        f"Authentication failed for Jira API ({status}). "
                        "Token may be expired or invalid. Please verify credentials."
                    )
                    logger.error(error_msg)
                    raise MCPAtlassianAuthenticationError(error_msg) from http_err
            raise

    def create_group(self, name: str) -> dict[str, Any]:
        """
        Create a new Jira group.

        Args:
            name: The name of the group to create.

        Returns:
            The API response dictionary for the created group.

        Raises:
            Exception: If there is an error creating the group.
        """
        try:
            result = self.jira.post("rest/api/2/group", data={"name": name})
            if not isinstance(result, dict):
                msg = f"Unexpected return value type from `jira.post`: {type(result)}"
                logger.error(msg)
                raise TypeError(msg)
            return result
        except Exception as e:
            logger.error(f"Error creating group '{name}': {e}")
            raise

    def delete_group(
        self, group_name: str, swap_group: str | None = None
    ) -> None:
        """
        Delete a Jira group.

        Args:
            group_name: The name of the group to delete.
            swap_group: Optional name of a group to transfer the deleted group's
                        restrictions to.

        Raises:
            Exception: If there is an error deleting the group.
        """
        params: dict[str, str] = {"groupname": group_name}
        if swap_group is not None:
            params["swapGroup"] = swap_group

        self.jira.delete("rest/api/2/group", params=params)

    def add_user_to_group(self, group_name: str, username: str) -> None:
        """
        Add a user to a Jira group.

        Args:
            group_name: The name of the group.
            username: The username (key) of the user to add.

        Raises:
            Exception: If there is an error adding the user to the group.
        """
        self.jira.post(
            "rest/api/2/group/user",
            params={"groupname": group_name},
            data={"name": username},
        )

    def remove_user_from_group(self, group_name: str, username: str) -> None:
        """
        Remove a user from a Jira group.

        Args:
            group_name: The name of the group.
            username: The username (key) of the user to remove.

        Raises:
            Exception: If there is an error removing the user from the group.
        """
        self.jira.delete(
            "rest/api/2/group/user",
            params={"groupname": group_name, "username": username},
        )
