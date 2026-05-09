"""
Tempo Timesheets entity models.

This module provides Pydantic models for Tempo Timesheets entities including
worklogs, approvals, work attributes, schedule days, and user schedules.
"""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import EMPTY_STRING

logger = logging.getLogger(__name__)


class TempoWorklog(ApiModel):
    """
    Model representing a Tempo worklog entry.

    Maps to the Tempo Timesheets API worklog resource, handling both legacy
    and current field name variants returned by different API versions.
    """

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
        """
        Create a TempoWorklog from a Tempo API response.

        Handles multiple field name variants:
        - Issue key: ``issue.key`` or ``originTaskId``
        - Worker: ``worker`` or ``workerKey``
        - Start date: ``startDate`` or ``started``
        - Created: ``dateCreated``
        - Updated: ``dateUpdated``

        Args:
            data: The worklog data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoWorklog instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # Resolve issue key from nested object or flat field
        issue_key = EMPTY_STRING
        issue_data = data.get("issue")
        if isinstance(issue_data, dict):
            issue_key = str(issue_data.get("key", EMPTY_STRING))
        if not issue_key:
            issue_key = str(data.get("originTaskId", EMPTY_STRING))

        # Resolve worker key from either field name variant
        worker_key = str(data.get("worker", data.get("workerKey", EMPTY_STRING)))

        # Resolve start date from either field name variant
        started = str(data.get("startDate", data.get("started", EMPTY_STRING)))

        # Safely coerce integer fields
        tempo_worklog_id = _safe_int(data.get("tempoWorklogId"), -1)
        jira_worklog_id = _safe_int(data.get("jiraWorklogId"), None)
        time_spent_seconds = _safe_int(data.get("timeSpentSeconds"), 0)
        billable_seconds = _safe_int(data.get("billableSeconds"), 0)

        return cls(
            tempo_worklog_id=tempo_worklog_id,
            jira_worklog_id=jira_worklog_id,
            issue_key=issue_key,
            worker_key=worker_key,
            updater_key=data.get("updaterKey"),
            started=started,
            time_spent_seconds=time_spent_seconds,
            billable_seconds=billable_seconds,
            comment=data.get("comment"),
            attributes=data.get("attributes"),
            created=str(data.get("dateCreated", EMPTY_STRING)),
            updated=str(data.get("dateUpdated", EMPTY_STRING)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
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
        if self.updater_key is not None:
            result["updater_key"] = self.updater_key
        if self.comment is not None:
            result["comment"] = self.comment
        if self.attributes is not None:
            result["attributes"] = self.attributes
        if self.created:
            result["created"] = self.created
        if self.updated:
            result["updated"] = self.updated

        return result


class TempoApproval(ApiModel):
    """
    Model representing a Tempo timesheet approval entry.

    Handles the nested user, period, and reviewer objects returned by the
    Tempo Timesheets approval API.
    """

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
        """
        Create a TempoApproval from a Tempo API response.

        Handles nested objects:
        - ``user.key`` → ``user_key``
        - ``period.dateFrom`` → ``period_start``
        - ``period.dateTo`` → ``period_end``
        - ``reviewer.key`` → ``reviewer_key``

        Args:
            data: The approval data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoApproval instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # Resolve user key from nested user object
        user_key = EMPTY_STRING
        user_data = data.get("user")
        if isinstance(user_data, dict):
            user_key = str(user_data.get("key", EMPTY_STRING))

        # Resolve period dates from nested period object
        period_start = EMPTY_STRING
        period_end = EMPTY_STRING
        period_data = data.get("period")
        if isinstance(period_data, dict):
            period_start = str(period_data.get("dateFrom", EMPTY_STRING))
            period_end = str(period_data.get("dateTo", EMPTY_STRING))

        # Resolve optional reviewer key
        reviewer_key = None
        reviewer_data = data.get("reviewer")
        if isinstance(reviewer_data, dict):
            raw_key = reviewer_data.get("key")
            if raw_key is not None:
                reviewer_key = str(raw_key)

        return cls(
            status=str(data.get("status", EMPTY_STRING)),
            worked_seconds=_safe_int(data.get("workedSeconds"), 0),
            submitted_seconds=_safe_int(data.get("submittedSeconds"), 0),
            required_seconds=_safe_int(data.get("requiredSeconds"), 0),
            user_key=user_key,
            period_start=period_start,
            period_end=period_end,
            reviewer_key=reviewer_key,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {
            "status": self.status,
            "user_key": self.user_key,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "worked_seconds": self.worked_seconds,
            "submitted_seconds": self.submitted_seconds,
            "required_seconds": self.required_seconds,
        }

        if self.reviewer_key is not None:
            result["reviewer_key"] = self.reviewer_key

        return result


class TempoWorkAttribute(ApiModel):
    """
    Model representing a Tempo work attribute definition.

    Work attributes are custom fields that can be attached to worklogs
    in the Tempo Timesheets configuration.
    """

    id: int = -1
    name: str = EMPTY_STRING
    type: str = EMPTY_STRING
    required: bool = False

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "TempoWorkAttribute":
        """
        Create a TempoWorkAttribute from a Tempo API response.

        Args:
            data: The work attribute data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoWorkAttribute instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # type may be a string or nested dict {"name": "...", "value": "STATIC_LIST"}
        type_data = data.get("type", EMPTY_STRING)
        if isinstance(type_data, dict):
            type_value = str(type_data.get("value", type_data.get("name", EMPTY_STRING)))
        else:
            type_value = str(type_data)

        return cls(
            id=_safe_int(data.get("id"), -1),
            name=str(data.get("name", EMPTY_STRING)),
            type=type_value,
            required=bool(data.get("required", False)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "required": self.required,
        }


class TempoScheduleDay(ApiModel):
    """
    Model representing a single day within a Tempo user schedule.

    The day type indicates whether it is a working day, non-working day,
    holiday, or a combination thereof.
    """

    date: str = EMPTY_STRING
    required_seconds: int = 0
    type: str = EMPTY_STRING
    holiday_name: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "TempoScheduleDay":
        """
        Create a TempoScheduleDay from a Tempo API response.

        Handles nested holiday object: ``holiday.name`` → ``holiday_name``.

        Args:
            data: The schedule day data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoScheduleDay instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        # Resolve optional holiday name from nested holiday object
        holiday_name = None
        holiday_data = data.get("holiday")
        if isinstance(holiday_data, dict):
            raw_name = holiday_data.get("name")
            if raw_name is not None:
                holiday_name = str(raw_name)

        return cls(
            date=str(data.get("date", EMPTY_STRING)),
            required_seconds=_safe_int(data.get("requiredSeconds"), 0),
            type=str(data.get("type", EMPTY_STRING)),
            holiday_name=holiday_name,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        result: dict[str, Any] = {
            "date": self.date,
            "required_seconds": self.required_seconds,
            "type": self.type,
        }

        if self.holiday_name is not None:
            result["holiday_name"] = self.holiday_name

        return result


class TempoUserSchedule(ApiModel):
    """
    Model representing a Tempo user schedule for a given period.

    Aggregates schedule day entries along with summary totals for
    working days and required seconds in the period.
    """

    number_of_working_days: int = 0
    required_seconds: int = 0
    days: list[TempoScheduleDay] = []

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], **kwargs: Any
    ) -> "TempoUserSchedule":
        """
        Create a TempoUserSchedule from a Tempo API response.

        Args:
            data: The user schedule data from the Tempo API
            **kwargs: Additional context parameters (unused)

        Returns:
            A TempoUserSchedule instance
        """
        if not data:
            return cls()

        if not isinstance(data, dict):
            logger.debug("Received non-dictionary data, returning default instance")
            return cls()

        days: list[TempoScheduleDay] = []
        days_data = data.get("days", [])
        if isinstance(days_data, list):
            for day_data in days_data:
                days.append(TempoScheduleDay.from_api_response(day_data))

        return cls(
            number_of_working_days=_safe_int(data.get("numberOfWorkingDays"), 0),
            required_seconds=_safe_int(data.get("requiredSeconds"), 0),
            days=days,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response."""
        return {
            "number_of_working_days": self.number_of_working_days,
            "required_seconds": self.required_seconds,
            "days": [day.to_simplified_dict() for day in self.days],
        }


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
