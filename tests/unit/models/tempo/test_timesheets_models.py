"""
Tests for Tempo Timesheets Pydantic models.

Covers TempoWorklog, TempoApproval, TempoWorkAttribute, TempoScheduleDay,
and TempoUserSchedule including valid responses, empty inputs, nested objects,
and to_simplified_dict output.
"""

from typing import Any

import pytest

from src.mcp_atlassian.models.constants import EMPTY_STRING
from src.mcp_atlassian.models.tempo.timesheets import (
    TempoApproval,
    TempoScheduleDay,
    TempoUserSchedule,
    TempoWorkAttribute,
    TempoWorklog,
)


# ---------------------------------------------------------------------------
# TempoWorklog
# ---------------------------------------------------------------------------


class TestTempoWorklog:
    """Tests for the TempoWorklog model."""

    def _valid_api_response(self) -> dict[str, Any]:
        return {
            "tempoWorklogId": 42,
            "jiraWorklogId": 100,
            "issue": {"key": "PROJ-1"},
            "worker": "jdoe",
            "updaterKey": "jadmin",
            "startDate": "2024-03-15",
            "timeSpentSeconds": 3600,
            "billableSeconds": 3600,
            "comment": "Worked on feature",
            "attributes": {"_Account_": {"name": "Account", "value": "ACME"}},
            "dateCreated": "2024-03-15T08:00:00.000Z",
            "dateUpdated": "2024-03-15T09:00:00.000Z",
        }

    def test_from_api_response_valid(self):
        """Parse a fully-populated API response."""
        worklog = TempoWorklog.from_api_response(self._valid_api_response())

        assert worklog.tempo_worklog_id == 42
        assert worklog.jira_worklog_id == 100
        assert worklog.issue_key == "PROJ-1"
        assert worklog.worker_key == "jdoe"
        assert worklog.updater_key == "jadmin"
        assert worklog.started == "2024-03-15"
        assert worklog.time_spent_seconds == 3600
        assert worklog.billable_seconds == 3600
        assert worklog.comment == "Worked on feature"
        assert worklog.attributes is not None
        assert worklog.created == "2024-03-15T08:00:00.000Z"
        assert worklog.updated == "2024-03-15T09:00:00.000Z"

    def test_from_api_response_issue_key_fallback_to_origin_task_id(self):
        """When no nested issue object is present, fall back to originTaskId."""
        data = {
            "tempoWorklogId": 10,
            "originTaskId": "PROJ-99",
            "worker": "jdoe",
            "startDate": "2024-01-01",
            "timeSpentSeconds": 1800,
            "billableSeconds": 0,
        }
        worklog = TempoWorklog.from_api_response(data)

        assert worklog.issue_key == "PROJ-99"

    def test_from_api_response_worker_key_variant(self):
        """Accept workerKey as an alternative to worker."""
        data = {
            "tempoWorklogId": 5,
            "originTaskId": "PROJ-1",
            "workerKey": "jsmith",
            "startDate": "2024-01-01",
            "timeSpentSeconds": 900,
            "billableSeconds": 900,
        }
        worklog = TempoWorklog.from_api_response(data)

        assert worklog.worker_key == "jsmith"

    def test_from_api_response_started_field_variant(self):
        """Accept started as an alternative to startDate."""
        data = {
            "tempoWorklogId": 7,
            "originTaskId": "PROJ-2",
            "worker": "jdoe",
            "started": "2024-02-20",
            "timeSpentSeconds": 7200,
            "billableSeconds": 0,
        }
        worklog = TempoWorklog.from_api_response(data)

        assert worklog.started == "2024-02-20"

    def test_from_api_response_empty_dict(self):
        """Empty dict returns default instance without raising."""
        worklog = TempoWorklog.from_api_response({})

        assert worklog.tempo_worklog_id == -1
        assert worklog.issue_key == EMPTY_STRING
        assert worklog.worker_key == EMPTY_STRING
        assert worklog.time_spent_seconds == 0

    def test_from_api_response_non_dict(self):
        """Non-dict input returns default instance without raising."""
        worklog = TempoWorklog.from_api_response("not-a-dict")  # type: ignore[arg-type]

        assert worklog.tempo_worklog_id == -1

    def test_to_simplified_dict_required_fields(self):
        """to_simplified_dict always includes required fields."""
        worklog = TempoWorklog.from_api_response(self._valid_api_response())
        result = worklog.to_simplified_dict()

        assert result["tempo_worklog_id"] == 42
        assert result["issue_key"] == "PROJ-1"
        assert result["worker_key"] == "jdoe"
        assert result["started"] == "2024-03-15"
        assert result["time_spent_seconds"] == 3600
        assert result["billable_seconds"] == 3600

    def test_to_simplified_dict_optional_fields_present(self):
        """Optional fields appear in simplified dict when set."""
        worklog = TempoWorklog.from_api_response(self._valid_api_response())
        result = worklog.to_simplified_dict()

        assert result["jira_worklog_id"] == 100
        assert result["updater_key"] == "jadmin"
        assert result["comment"] == "Worked on feature"
        assert result["attributes"] is not None

    def test_to_simplified_dict_optional_fields_absent(self):
        """Optional fields are absent in simplified dict when not set."""
        worklog = TempoWorklog.from_api_response({
            "tempoWorklogId": 1,
            "originTaskId": "PROJ-1",
            "worker": "jdoe",
            "startDate": "2024-01-01",
            "timeSpentSeconds": 0,
            "billableSeconds": 0,
        })
        result = worklog.to_simplified_dict()

        assert "jira_worklog_id" not in result
        assert "updater_key" not in result
        assert "comment" not in result
        assert "attributes" not in result


# ---------------------------------------------------------------------------
# TempoApproval
# ---------------------------------------------------------------------------


class TestTempoApproval:
    """Tests for the TempoApproval model."""

    def _valid_api_response(self) -> dict[str, Any]:
        return {
            "status": "approved",
            "workedSeconds": 28800,
            "submittedSeconds": 28800,
            "requiredSeconds": 28800,
            "user": {"key": "jdoe"},
            "period": {"dateFrom": "2024-03-01", "dateTo": "2024-03-31"},
            "reviewer": {"key": "jadmin"},
        }

    def test_from_api_response_valid(self):
        """Parse a fully-populated API response with nested objects."""
        approval = TempoApproval.from_api_response(self._valid_api_response())

        assert approval.status == "approved"
        assert approval.worked_seconds == 28800
        assert approval.submitted_seconds == 28800
        assert approval.required_seconds == 28800
        assert approval.user_key == "jdoe"
        assert approval.period_start == "2024-03-01"
        assert approval.period_end == "2024-03-31"
        assert approval.reviewer_key == "jadmin"

    def test_from_api_response_nested_user(self):
        """user.key is correctly extracted."""
        data = {
            "status": "open",
            "workedSeconds": 0,
            "submittedSeconds": 0,
            "requiredSeconds": 14400,
            "user": {"key": "alice"},
            "period": {"dateFrom": "2024-01-01", "dateTo": "2024-01-14"},
        }
        approval = TempoApproval.from_api_response(data)

        assert approval.user_key == "alice"

    def test_from_api_response_nested_period(self):
        """period.dateFrom and period.dateTo are correctly extracted."""
        data = {
            "status": "waiting_for_approval",
            "workedSeconds": 3600,
            "submittedSeconds": 3600,
            "requiredSeconds": 3600,
            "user": {"key": "bob"},
            "period": {"dateFrom": "2024-06-01", "dateTo": "2024-06-15"},
        }
        approval = TempoApproval.from_api_response(data)

        assert approval.period_start == "2024-06-01"
        assert approval.period_end == "2024-06-15"

    def test_from_api_response_reviewer_absent(self):
        """reviewer_key is None when reviewer is not in the response."""
        data = {
            "status": "ready_to_submit",
            "workedSeconds": 7200,
            "submittedSeconds": 0,
            "requiredSeconds": 7200,
            "user": {"key": "carol"},
            "period": {"dateFrom": "2024-02-01", "dateTo": "2024-02-28"},
        }
        approval = TempoApproval.from_api_response(data)

        assert approval.reviewer_key is None

    def test_from_api_response_empty_dict(self):
        """Empty dict returns default instance without raising."""
        approval = TempoApproval.from_api_response({})

        assert approval.status == EMPTY_STRING
        assert approval.user_key == EMPTY_STRING
        assert approval.period_start == EMPTY_STRING
        assert approval.period_end == EMPTY_STRING
        assert approval.reviewer_key is None

    def test_from_api_response_non_dict(self):
        """Non-dict input returns default instance without raising."""
        approval = TempoApproval.from_api_response(None)  # type: ignore[arg-type]

        assert approval.status == EMPTY_STRING

    def test_to_simplified_dict(self):
        """to_simplified_dict includes all expected fields."""
        approval = TempoApproval.from_api_response(self._valid_api_response())
        result = approval.to_simplified_dict()

        assert result["status"] == "approved"
        assert result["user_key"] == "jdoe"
        assert result["period_start"] == "2024-03-01"
        assert result["period_end"] == "2024-03-31"
        assert result["worked_seconds"] == 28800
        assert result["submitted_seconds"] == 28800
        assert result["required_seconds"] == 28800
        assert result["reviewer_key"] == "jadmin"

    def test_to_simplified_dict_without_reviewer(self):
        """reviewer_key is absent from simplified dict when not set."""
        data = {
            "status": "open",
            "workedSeconds": 0,
            "submittedSeconds": 0,
            "requiredSeconds": 0,
            "user": {"key": "dave"},
            "period": {"dateFrom": "2024-01-01", "dateTo": "2024-01-31"},
        }
        approval = TempoApproval.from_api_response(data)
        result = approval.to_simplified_dict()

        assert "reviewer_key" not in result


# ---------------------------------------------------------------------------
# TempoWorkAttribute
# ---------------------------------------------------------------------------


class TestTempoWorkAttribute:
    """Tests for the TempoWorkAttribute model."""

    def test_from_api_response_valid(self):
        """Parse a fully-populated API response."""
        data = {"id": 3, "name": "Account", "type": "ACCOUNT", "required": True}
        attr = TempoWorkAttribute.from_api_response(data)

        assert attr.id == 3
        assert attr.name == "Account"
        assert attr.type == "ACCOUNT"
        assert attr.required is True

    def test_from_api_response_not_required(self):
        """required defaults to False when absent."""
        data = {"id": 7, "name": "Team", "type": "STATIC_LIST"}
        attr = TempoWorkAttribute.from_api_response(data)

        assert attr.required is False

    def test_from_api_response_empty_dict(self):
        """Empty dict returns default instance without raising."""
        attr = TempoWorkAttribute.from_api_response({})

        assert attr.id == -1
        assert attr.name == EMPTY_STRING
        assert attr.type == EMPTY_STRING
        assert attr.required is False

    def test_from_api_response_non_dict(self):
        """Non-dict input returns default instance without raising."""
        attr = TempoWorkAttribute.from_api_response(42)  # type: ignore[arg-type]

        assert attr.id == -1

    def test_to_simplified_dict(self):
        """to_simplified_dict includes all four fields."""
        data = {"id": 1, "name": "Billable", "type": "CHECKBOX", "required": False}
        attr = TempoWorkAttribute.from_api_response(data)
        result = attr.to_simplified_dict()

        assert result == {"id": 1, "name": "Billable", "type": "CHECKBOX", "required": False}


# ---------------------------------------------------------------------------
# TempoScheduleDay
# ---------------------------------------------------------------------------


class TestTempoScheduleDay:
    """Tests for the TempoScheduleDay model."""

    def test_from_api_response_working_day(self):
        """Parse a standard working day with no holiday."""
        data = {
            "date": "2024-03-18",
            "requiredSeconds": 28800,
            "type": "WORKING_DAY",
        }
        day = TempoScheduleDay.from_api_response(data)

        assert day.date == "2024-03-18"
        assert day.required_seconds == 28800
        assert day.type == "WORKING_DAY"
        assert day.holiday_name is None

    def test_from_api_response_holiday_with_nested_name(self):
        """Parse a holiday day with nested holiday object."""
        data = {
            "date": "2024-03-29",
            "requiredSeconds": 0,
            "type": "HOLIDAY",
            "holiday": {"name": "Easter"},
        }
        day = TempoScheduleDay.from_api_response(data)

        assert day.type == "HOLIDAY"
        assert day.holiday_name == "Easter"

    def test_from_api_response_non_working_day(self):
        """Parse a non-working day (weekend)."""
        data = {
            "date": "2024-03-16",
            "requiredSeconds": 0,
            "type": "NON_WORKING_DAY",
        }
        day = TempoScheduleDay.from_api_response(data)

        assert day.type == "NON_WORKING_DAY"
        assert day.holiday_name is None

    def test_from_api_response_holiday_and_non_working(self):
        """Parse a combined holiday-and-non-working-day type."""
        data = {
            "date": "2024-12-25",
            "requiredSeconds": 0,
            "type": "HOLIDAY_AND_NON_WORKING_DAY",
            "holiday": {"name": "Christmas Day"},
        }
        day = TempoScheduleDay.from_api_response(data)

        assert day.type == "HOLIDAY_AND_NON_WORKING_DAY"
        assert day.holiday_name == "Christmas Day"

    def test_from_api_response_empty_dict(self):
        """Empty dict returns default instance without raising."""
        day = TempoScheduleDay.from_api_response({})

        assert day.date == EMPTY_STRING
        assert day.required_seconds == 0
        assert day.type == EMPTY_STRING
        assert day.holiday_name is None

    def test_from_api_response_non_dict(self):
        """Non-dict input returns default instance without raising."""
        day = TempoScheduleDay.from_api_response("2024-01-01")  # type: ignore[arg-type]

        assert day.date == EMPTY_STRING

    def test_to_simplified_dict_without_holiday(self):
        """holiday_name absent from simplified dict when None."""
        data = {"date": "2024-03-18", "requiredSeconds": 28800, "type": "WORKING_DAY"}
        day = TempoScheduleDay.from_api_response(data)
        result = day.to_simplified_dict()

        assert result == {"date": "2024-03-18", "required_seconds": 28800, "type": "WORKING_DAY"}
        assert "holiday_name" not in result

    def test_to_simplified_dict_with_holiday(self):
        """holiday_name present in simplified dict when set."""
        data = {
            "date": "2024-03-29",
            "requiredSeconds": 0,
            "type": "HOLIDAY",
            "holiday": {"name": "Good Friday"},
        }
        day = TempoScheduleDay.from_api_response(data)
        result = day.to_simplified_dict()

        assert result["holiday_name"] == "Good Friday"


# ---------------------------------------------------------------------------
# TempoUserSchedule
# ---------------------------------------------------------------------------


class TestTempoUserSchedule:
    """Tests for the TempoUserSchedule model."""

    def _valid_api_response(self) -> dict[str, Any]:
        return {
            "numberOfWorkingDays": 21,
            "requiredSeconds": 604800,
            "days": [
                {"date": "2024-03-18", "requiredSeconds": 28800, "type": "WORKING_DAY"},
                {"date": "2024-03-19", "requiredSeconds": 28800, "type": "WORKING_DAY"},
                {
                    "date": "2024-03-29",
                    "requiredSeconds": 0,
                    "type": "HOLIDAY",
                    "holiday": {"name": "Good Friday"},
                },
                {"date": "2024-03-30", "requiredSeconds": 0, "type": "NON_WORKING_DAY"},
                {"date": "2024-03-31", "requiredSeconds": 0, "type": "NON_WORKING_DAY"},
            ],
        }

    def test_from_api_response_valid(self):
        """Parse a schedule with mixed day types."""
        schedule = TempoUserSchedule.from_api_response(self._valid_api_response())

        assert schedule.number_of_working_days == 21
        assert schedule.required_seconds == 604800
        assert len(schedule.days) == 5

    def test_from_api_response_days_parsed_correctly(self):
        """Each day in the days list is fully parsed."""
        schedule = TempoUserSchedule.from_api_response(self._valid_api_response())
        holiday_day = schedule.days[2]

        assert holiday_day.date == "2024-03-29"
        assert holiday_day.type == "HOLIDAY"
        assert holiday_day.holiday_name == "Good Friday"

    def test_from_api_response_empty_days_list(self):
        """A schedule with no days parses without error."""
        data = {"numberOfWorkingDays": 0, "requiredSeconds": 0, "days": []}
        schedule = TempoUserSchedule.from_api_response(data)

        assert schedule.number_of_working_days == 0
        assert schedule.days == []

    def test_from_api_response_empty_dict(self):
        """Empty dict returns default instance without raising."""
        schedule = TempoUserSchedule.from_api_response({})

        assert schedule.number_of_working_days == 0
        assert schedule.required_seconds == 0
        assert schedule.days == []

    def test_from_api_response_non_dict(self):
        """Non-dict input returns default instance without raising."""
        schedule = TempoUserSchedule.from_api_response([])  # type: ignore[arg-type]

        assert schedule.number_of_working_days == 0
        assert schedule.days == []

    def test_to_simplified_dict_structure(self):
        """to_simplified_dict contains number_of_working_days, required_seconds, days."""
        schedule = TempoUserSchedule.from_api_response(self._valid_api_response())
        result = schedule.to_simplified_dict()

        assert result["number_of_working_days"] == 21
        assert result["required_seconds"] == 604800
        assert isinstance(result["days"], list)
        assert len(result["days"]) == 5

    def test_to_simplified_dict_days_content(self):
        """Each entry in the days list is a simplified dict from TempoScheduleDay."""
        schedule = TempoUserSchedule.from_api_response(self._valid_api_response())
        result = schedule.to_simplified_dict()
        first_day = result["days"][0]

        assert first_day["date"] == "2024-03-18"
        assert first_day["type"] == "WORKING_DAY"
        assert "holiday_name" not in first_day

    def test_to_simplified_dict_empty_schedule(self):
        """to_simplified_dict of a default instance has an empty days list."""
        schedule = TempoUserSchedule.from_api_response({})
        result = schedule.to_simplified_dict()

        assert result["days"] == []
