"""Tempo Timesheets mixin for worklog, approval, attribute, and schedule operations."""

import logging
from typing import Any

from requests.exceptions import HTTPError

from ..models.tempo.timesheets import (
    TempoApproval,
    TempoUserSchedule,
    TempoWorkAttribute,
    TempoWorklog,
)
from .client import TempoClient

logger = logging.getLogger("mcp-tempo")

_WORKLOGS_BASE = "rest/tempo-timesheets/4/worklogs"
_APPROVAL_BASE = "rest/tempo-timesheets/4/timesheet-approval"
_CORE_BASE = "rest/tempo-core/1"


class TempoTimesheetsMixin(TempoClient):
    """Mixin providing Tempo Timesheets worklog, approval, attribute, and schedule methods."""

    # ------------------------------------------------------------------
    # Worklog methods
    # ------------------------------------------------------------------

    def search_worklogs(
        self,
        date_from: str,
        date_to: str,
        worker_keys: list[str] | None = None,
        project_keys: list[str] | None = None,
        team_ids: list[str] | None = None,
        epic_keys: list[str] | None = None,
        task_keys: list[str] | None = None,
    ) -> list[TempoWorklog]:
        """
        Search for worklogs matching the given criteria.

        Args:
            date_from: Start date in ISO format (YYYY-MM-DD).
            date_to: End date in ISO format (YYYY-MM-DD).
            worker_keys: Optional list of worker (user) keys to filter by.
            project_keys: Optional list of project keys to filter by.
            team_ids: Optional list of Tempo team IDs to filter by.
            epic_keys: Optional list of epic issue keys to filter by.
            task_keys: Optional list of task issue keys to filter by.

        Returns:
            List of TempoWorklog instances; empty list on error.
        """
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

        try:
            response = self.jira.post(f"{_WORKLOGS_BASE}/search", data=body)
            if not isinstance(response, list):
                logger.warning(
                    "Unexpected response type from worklogs search: %s", type(response)
                )
                return []
            return [TempoWorklog.from_api_response(item) for item in response]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to search worklogs: %s", exc)
            return []

    def get_worklog(self, worklog_id: int) -> TempoWorklog:
        """
        Retrieve a single worklog by its Tempo worklog ID.

        Args:
            worklog_id: The Tempo worklog ID.

        Returns:
            A TempoWorklog instance.

        Raises:
            ValueError: If the worklog is not found (HTTP 404).
            HTTPError: For other HTTP errors.
        """
        try:
            response = self.jira.get(f"{_WORKLOGS_BASE}/{worklog_id}")
            return TempoWorklog.from_api_response(response)
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise ValueError(f"Worklog {worklog_id} not found") from exc
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
        attributes: list[dict[str, Any]] | None = None,
        remaining_estimate: str | None = None,
    ) -> TempoWorklog:
        """
        Create a new Tempo worklog entry.

        Args:
            worker: The worker (user) key.
            issue_key: The Jira issue key (e.g. ``PROJ-123``).
            started: The start date/time in ISO format.
            time_spent_seconds: Time spent in seconds.
            comment: Optional free-text comment.
            billable_seconds: Optional billable time in seconds.
            end_date: Optional end date for the worklog period.
            include_non_working_days: Whether to include non-working days.
            attributes: Optional list of custom work attribute value objects.
            remaining_estimate: Optional remaining estimate string (e.g. ``1h``).

        Returns:
            The created TempoWorklog instance.

        Raises:
            HTTPError: If the API call fails.
        """
        body: dict[str, Any] = {
            "worker": worker,
            "originTaskId": issue_key,
            "started": started,
            "timeSpentSeconds": time_spent_seconds,
            "includeNonWorkingDays": include_non_working_days,
        }
        if comment is not None:
            body["comment"] = comment
        if billable_seconds is not None:
            body["billableSeconds"] = billable_seconds
        if end_date is not None:
            body["endDate"] = end_date
        if attributes is not None:
            body["attributes"] = attributes
        if remaining_estimate is not None:
            body["remainingEstimate"] = remaining_estimate

        try:
            response = self.jira.post(_WORKLOGS_BASE, data=body)
            # API may return a list (with single item) or a dict
            if isinstance(response, list) and len(response) > 0:
                response = response[0]
            return TempoWorklog.from_api_response(response)
        except Exception as exc:
            logger.error("Failed to create worklog for issue %s: %s", issue_key, exc)
            raise

    def update_worklog(
        self,
        worklog_id: int,
        started: str | None = None,
        time_spent_seconds: int | None = None,
        comment: str | None = None,
        billable_seconds: int | None = None,
        end_date: str | None = None,
        include_non_working_days: bool | None = None,
        attributes: list[dict[str, Any]] | None = None,
        remaining_estimate: str | None = None,
    ) -> TempoWorklog:
        """
        Update an existing Tempo worklog entry.

        Only fields explicitly provided are included in the request body.

        Args:
            worklog_id: The Tempo worklog ID to update.
            started: Optional new start date/time.
            time_spent_seconds: Optional new time spent in seconds.
            comment: Optional new comment.
            billable_seconds: Optional new billable time in seconds.
            end_date: Optional new end date.
            include_non_working_days: Optional flag for non-working days.
            attributes: Optional new list of custom work attribute value objects.
            remaining_estimate: Optional new remaining estimate string.

        Returns:
            The updated TempoWorklog instance.

        Raises:
            HTTPError: If the API call fails.
        """
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

        try:
            response = self.jira.put(f"{_WORKLOGS_BASE}/{worklog_id}", data=body)
            if isinstance(response, list) and len(response) > 0:
                response = response[0]
            return TempoWorklog.from_api_response(response)
        except Exception as exc:
            logger.error("Failed to update worklog %s: %s", worklog_id, exc)
            raise

    def delete_worklog(self, worklog_id: int) -> None:
        """
        Delete a Tempo worklog entry.

        Args:
            worklog_id: The Tempo worklog ID to delete.

        Raises:
            HTTPError: If the API call fails.
        """
        try:
            self.jira.delete(f"{_WORKLOGS_BASE}/{worklog_id}")
        except Exception as exc:
            logger.error("Failed to delete worklog %s: %s", worklog_id, exc)
            raise

    # ------------------------------------------------------------------
    # Approval methods
    # ------------------------------------------------------------------

    def get_approval_status(
        self, user_key: str, period_start_date: str
    ) -> list[TempoApproval]:
        """
        Retrieve the timesheet approval status for a user and period.

        The API may return either a list or a single object; both are
        normalised to a list before returning.

        Args:
            user_key: The Jira user key.
            period_start_date: The start date of the approval period (YYYY-MM-DD).

        Returns:
            List of TempoApproval instances; empty list on error.
        """
        params = {"userKey": user_key, "periodStartDate": period_start_date}
        try:
            response = self.jira.get(
                f"{_APPROVAL_BASE}/current", params=params
            )
            return _normalise_approval_response(response)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to get approval status for user %s: %s", user_key, exc
            )
            return []

    def get_pending_approvals(self, reviewer_key: str) -> list[TempoApproval]:
        """
        Retrieve all pending timesheet approvals for a given reviewer.

        Args:
            reviewer_key: The Jira user key of the reviewer.

        Returns:
            List of TempoApproval instances; empty list on error.
        """
        params = {"reviewerKey": reviewer_key}
        try:
            response = self.jira.get(f"{_APPROVAL_BASE}/pending", params=params)
            return _normalise_approval_response(response)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to get pending approvals for reviewer %s: %s",
                reviewer_key,
                exc,
            )
            return []

    def submit_approval(
        self,
        user_key: str,
        period_date_from: str,
        action: str,
        comment: str | None = None,
        reviewer_key: str | None = None,
    ) -> TempoApproval:
        """
        Submit a timesheet approval action.

        Args:
            user_key: The Jira user key of the timesheet owner.
            period_date_from: The start date of the approval period (YYYY-MM-DD).
            action: The action name (e.g. ``SUBMIT``, ``APPROVE``, ``REJECT``).
            comment: Optional comment accompanying the action.
            reviewer_key: Optional Jira user key of the reviewer.

        Returns:
            The resulting TempoApproval instance.

        Raises:
            HTTPError: If the API call fails.
        """
        action_payload: dict[str, Any] = {"name": action}
        if comment is not None:
            action_payload["comment"] = comment
        if reviewer_key is not None:
            action_payload["reviewer"] = {"key": reviewer_key}

        body: dict[str, Any] = {
            "user": {"key": user_key},
            "period": {"dateFrom": period_date_from},
            "action": action_payload,
        }

        try:
            response = self.jira.post(_APPROVAL_BASE, data=body)
            return TempoApproval.from_api_response(response)
        except Exception as exc:
            logger.error(
                "Failed to submit approval action '%s' for user %s: %s",
                action,
                user_key,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Attribute / Schedule methods
    # ------------------------------------------------------------------

    def get_work_attributes(self) -> list[TempoWorkAttribute]:
        """
        Retrieve all Tempo work attribute definitions.

        Returns:
            List of TempoWorkAttribute instances; empty list on error.
        """
        try:
            response = self.jira.get(f"{_CORE_BASE}/work-attribute")
            if not isinstance(response, list):
                logger.warning(
                    "Unexpected response type from work-attribute endpoint: %s",
                    type(response),
                )
                return []
            return [TempoWorkAttribute.from_api_response(item) for item in response]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to get work attributes: %s", exc)
            return []

    def get_user_schedule(
        self,
        user: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> TempoUserSchedule:
        """
        Retrieve the Tempo schedule for a user over a date range.

        Args:
            user: Optional Jira user key; defaults to the authenticated user.
            date_from: Optional start date (YYYY-MM-DD).
            date_to: Optional end date (YYYY-MM-DD).

        Returns:
            A TempoUserSchedule instance; empty schedule on error.
        """
        params: dict[str, str] = {}
        if user is not None:
            params["user"] = user
        if date_from is not None:
            params["from"] = date_from
        if date_to is not None:
            params["to"] = date_to

        try:
            response = self.jira.get(f"{_CORE_BASE}/user/schedule", params=params)
            return TempoUserSchedule.from_api_response(response)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to get user schedule for user %s: %s", user, exc)
            return TempoUserSchedule()


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _normalise_approval_response(response: Any) -> list[TempoApproval]:
    """
    Normalise a Tempo approval API response to a list of TempoApproval objects.

    The approval endpoints may return either a single dict or a list of dicts.

    Args:
        response: Raw response from the Tempo API.

    Returns:
        List of TempoApproval instances.
    """
    if isinstance(response, list):
        return [TempoApproval.from_api_response(item) for item in response]
    if isinstance(response, dict):
        return [TempoApproval.from_api_response(response)]
    logger.warning(
        "Unexpected approval response type %s; returning empty list", type(response)
    )
    return []
