"""Unit tests for TempoTimesheetsMixin."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.models.tempo.timesheets import (
    TempoApproval,
    TempoUserSchedule,
    TempoWorkAttribute,
    TempoWorklog,
)
from mcp_atlassian.tempo.timesheets import TempoTimesheetsMixin


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ts_mixin(tempo_client):
    """Return a TempoTimesheetsMixin wired to the shared mock Jira instance."""
    mixin = TempoTimesheetsMixin(config=tempo_client.config)
    mixin.jira = tempo_client.jira
    return mixin


# ---------------------------------------------------------------------------
# Sample API payloads
# ---------------------------------------------------------------------------

WORKLOG_PAYLOAD = {
    "tempoWorklogId": 101,
    "jiraWorklogId": 202,
    "originTaskId": "PROJ-1",
    "worker": "john.doe",
    "startDate": "2024-01-15",
    "timeSpentSeconds": 3600,
    "billableSeconds": 3600,
    "comment": "Worked on feature",
    "dateCreated": "2024-01-15T10:00:00",
    "dateUpdated": "2024-01-15T10:05:00",
}

APPROVAL_PAYLOAD = {
    "status": "OPEN",
    "workedSeconds": 28800,
    "submittedSeconds": 0,
    "requiredSeconds": 28800,
    "user": {"key": "john.doe"},
    "period": {"dateFrom": "2024-01-01", "dateTo": "2024-01-31"},
}

WORK_ATTRIBUTE_PAYLOAD = {
    "id": 5,
    "name": "Billing Account",
    "type": "ACCOUNT",
    "required": True,
}

USER_SCHEDULE_PAYLOAD = {
    "numberOfWorkingDays": 5,
    "requiredSeconds": 144000,
    "days": [
        {"date": "2024-01-15", "requiredSeconds": 28800, "type": "WORKING_DAY"},
        {
            "date": "2024-01-20",
            "requiredSeconds": 0,
            "type": "HOLIDAY",
            "holiday": {"name": "Bank Holiday"},
        },
    ],
}


# ---------------------------------------------------------------------------
# search_worklogs
# ---------------------------------------------------------------------------


class TestSearchWorklogs:
    def test_returns_list_of_worklogs_on_success(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=[WORKLOG_PAYLOAD])

        result = ts_mixin.search_worklogs("2024-01-01", "2024-01-31")

        assert len(result) == 1
        assert isinstance(result[0], TempoWorklog)
        assert result[0].tempo_worklog_id == 101
        assert result[0].issue_key == "PROJ-1"
        assert result[0].worker_key == "john.doe"

    def test_passes_all_filter_parameters_in_body(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=[])

        ts_mixin.search_worklogs(
            "2024-01-01",
            "2024-01-31",
            worker_keys=["alice"],
            project_keys=["PROJ"],
            team_ids=["42"],
            epic_keys=["PROJ-100"],
            task_keys=["PROJ-50"],
        )

        call_body = ts_mixin.jira.post.call_args[1]["data"]
        assert call_body["from"] == "2024-01-01"
        assert call_body["to"] == "2024-01-31"
        assert call_body["worker"] == ["alice"]
        assert call_body["projectKey"] == ["PROJ"]
        assert call_body["teamId"] == ["42"]
        assert call_body["epicKey"] == ["PROJ-100"]
        assert call_body["taskKey"] == ["PROJ-50"]

    def test_omits_none_filter_parameters(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=[])

        ts_mixin.search_worklogs("2024-01-01", "2024-01-31")

        call_body = ts_mixin.jira.post.call_args[1]["data"]
        assert "worker" not in call_body
        assert "projectKey" not in call_body

    def test_returns_empty_list_on_api_error(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(side_effect=RuntimeError("connection refused"))

        result = ts_mixin.search_worklogs("2024-01-01", "2024-01-31")

        assert result == []

    def test_returns_empty_list_when_response_is_not_list(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value={"error": "unexpected"})

        result = ts_mixin.search_worklogs("2024-01-01", "2024-01-31")

        assert result == []

    def test_returns_multiple_worklogs(self, ts_mixin):
        second = {**WORKLOG_PAYLOAD, "tempoWorklogId": 102, "originTaskId": "PROJ-2"}
        ts_mixin.jira.post = MagicMock(return_value=[WORKLOG_PAYLOAD, second])

        result = ts_mixin.search_worklogs("2024-01-01", "2024-01-31")

        assert len(result) == 2
        assert result[1].tempo_worklog_id == 102


# ---------------------------------------------------------------------------
# get_worklog
# ---------------------------------------------------------------------------


class TestGetWorklog:
    def test_returns_worklog_on_success(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=WORKLOG_PAYLOAD)

        result = ts_mixin.get_worklog(101)

        assert isinstance(result, TempoWorklog)
        assert result.tempo_worklog_id == 101

    def test_raises_value_error_on_404(self, ts_mixin):
        http_error = _make_http_error(404)
        ts_mixin.jira.get = MagicMock(side_effect=http_error)

        with pytest.raises(ValueError, match="101"):
            ts_mixin.get_worklog(101)

    def test_reraises_non_404_http_error(self, ts_mixin):
        http_error = _make_http_error(500)
        ts_mixin.jira.get = MagicMock(side_effect=http_error)

        with pytest.raises(HTTPError):
            ts_mixin.get_worklog(101)

    def test_calls_correct_url(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=WORKLOG_PAYLOAD)

        ts_mixin.get_worklog(42)

        ts_mixin.jira.get.assert_called_once_with(
            "rest/tempo-timesheets/4/worklogs/42"
        )


# ---------------------------------------------------------------------------
# create_worklog
# ---------------------------------------------------------------------------


class TestCreateWorklog:
    def test_returns_worklog_on_success(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=WORKLOG_PAYLOAD)

        result = ts_mixin.create_worklog(
            worker="john.doe",
            issue_key="PROJ-1",
            started="2024-01-15",
            time_spent_seconds=3600,
        )

        assert isinstance(result, TempoWorklog)
        assert result.tempo_worklog_id == 101

    def test_required_fields_in_body(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=WORKLOG_PAYLOAD)

        ts_mixin.create_worklog(
            worker="john.doe",
            issue_key="PROJ-1",
            started="2024-01-15",
            time_spent_seconds=3600,
        )

        body = ts_mixin.jira.post.call_args[1]["data"]
        assert body["worker"] == "john.doe"
        assert body["originTaskId"] == "PROJ-1"
        assert body["started"] == "2024-01-15"
        assert body["timeSpentSeconds"] == 3600
        assert body["includeNonWorkingDays"] is False

    def test_optional_fields_included_when_provided(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=WORKLOG_PAYLOAD)

        ts_mixin.create_worklog(
            worker="john.doe",
            issue_key="PROJ-1",
            started="2024-01-15",
            time_spent_seconds=3600,
            comment="Test comment",
            billable_seconds=1800,
            end_date="2024-01-16",
            include_non_working_days=True,
            attributes=[{"key": "_BillingAccount_", "value": "ACME"}],
            remaining_estimate="2h",
        )

        body = ts_mixin.jira.post.call_args[1]["data"]
        assert body["comment"] == "Test comment"
        assert body["billableSeconds"] == 1800
        assert body["endDate"] == "2024-01-16"
        assert body["includeNonWorkingDays"] is True
        assert body["attributes"] == [{"key": "_BillingAccount_", "value": "ACME"}]
        assert body["remainingEstimate"] == "2h"

    def test_optional_fields_absent_when_not_provided(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=WORKLOG_PAYLOAD)

        ts_mixin.create_worklog(
            worker="john.doe",
            issue_key="PROJ-1",
            started="2024-01-15",
            time_spent_seconds=3600,
        )

        body = ts_mixin.jira.post.call_args[1]["data"]
        assert "comment" not in body
        assert "billableSeconds" not in body
        assert "endDate" not in body
        assert "attributes" not in body
        assert "remainingEstimate" not in body

    def test_raises_on_api_error(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(side_effect=RuntimeError("server error"))

        with pytest.raises(RuntimeError):
            ts_mixin.create_worklog(
                worker="john.doe",
                issue_key="PROJ-1",
                started="2024-01-15",
                time_spent_seconds=3600,
            )


# ---------------------------------------------------------------------------
# update_worklog
# ---------------------------------------------------------------------------


class TestUpdateWorklog:
    def test_returns_updated_worklog(self, ts_mixin):
        updated = {**WORKLOG_PAYLOAD, "timeSpentSeconds": 7200}
        ts_mixin.jira.put = MagicMock(return_value=updated)

        result = ts_mixin.update_worklog(101, time_spent_seconds=7200)

        assert isinstance(result, TempoWorklog)
        assert result.time_spent_seconds == 7200

    def test_only_provided_fields_sent_in_body(self, ts_mixin):
        ts_mixin.jira.put = MagicMock(return_value=WORKLOG_PAYLOAD)

        ts_mixin.update_worklog(101, comment="Updated comment")

        body = ts_mixin.jira.put.call_args[1]["data"]
        assert body == {"comment": "Updated comment"}

    def test_calls_correct_url(self, ts_mixin):
        ts_mixin.jira.put = MagicMock(return_value=WORKLOG_PAYLOAD)

        ts_mixin.update_worklog(99, started="2024-02-01")

        ts_mixin.jira.put.assert_called_once()
        url = ts_mixin.jira.put.call_args[0][0]
        assert url == "rest/tempo-timesheets/4/worklogs/99"

    def test_raises_on_api_error(self, ts_mixin):
        ts_mixin.jira.put = MagicMock(side_effect=_make_http_error(403))

        with pytest.raises(HTTPError):
            ts_mixin.update_worklog(101, comment="fail")


# ---------------------------------------------------------------------------
# delete_worklog
# ---------------------------------------------------------------------------


class TestDeleteWorklog:
    def test_calls_delete_endpoint(self, ts_mixin):
        ts_mixin.jira.delete = MagicMock(return_value=None)

        ts_mixin.delete_worklog(101)

        ts_mixin.jira.delete.assert_called_once_with(
            "rest/tempo-timesheets/4/worklogs/101"
        )

    def test_returns_none_on_success(self, ts_mixin):
        ts_mixin.jira.delete = MagicMock(return_value=None)

        result = ts_mixin.delete_worklog(101)

        assert result is None

    def test_raises_on_api_error(self, ts_mixin):
        ts_mixin.jira.delete = MagicMock(side_effect=_make_http_error(404))

        with pytest.raises(HTTPError):
            ts_mixin.delete_worklog(999)


# ---------------------------------------------------------------------------
# get_approval_status
# ---------------------------------------------------------------------------


class TestGetApprovalStatus:
    def test_returns_list_from_dict_response(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=APPROVAL_PAYLOAD)

        result = ts_mixin.get_approval_status("john.doe", "2024-01-01")

        assert len(result) == 1
        assert isinstance(result[0], TempoApproval)
        assert result[0].status == "OPEN"
        assert result[0].user_key == "john.doe"

    def test_returns_list_from_list_response(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[APPROVAL_PAYLOAD, APPROVAL_PAYLOAD])

        result = ts_mixin.get_approval_status("john.doe", "2024-01-01")

        assert len(result) == 2

    def test_passes_query_params(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=APPROVAL_PAYLOAD)

        ts_mixin.get_approval_status("alice", "2024-03-01")

        ts_mixin.jira.get.assert_called_once_with(
            "rest/tempo-timesheets/4/timesheet-approval/current",
            params={"userKey": "alice", "periodStartDate": "2024-03-01"},
        )

    def test_returns_empty_list_on_error(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(side_effect=RuntimeError("timeout"))

        result = ts_mixin.get_approval_status("john.doe", "2024-01-01")

        assert result == []


# ---------------------------------------------------------------------------
# get_pending_approvals
# ---------------------------------------------------------------------------


class TestGetPendingApprovals:
    def test_returns_approvals_on_success(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[APPROVAL_PAYLOAD])

        result = ts_mixin.get_pending_approvals("manager.key")

        assert len(result) == 1
        assert isinstance(result[0], TempoApproval)

    def test_passes_reviewer_key_param(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[])

        ts_mixin.get_pending_approvals("mgr")

        ts_mixin.jira.get.assert_called_once_with(
            "rest/tempo-timesheets/4/timesheet-approval/pending",
            params={"reviewerKey": "mgr"},
        )

    def test_returns_empty_list_on_error(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(side_effect=RuntimeError("error"))

        result = ts_mixin.get_pending_approvals("mgr")

        assert result == []


# ---------------------------------------------------------------------------
# submit_approval
# ---------------------------------------------------------------------------


class TestSubmitApproval:
    def test_returns_approval_on_success(self, ts_mixin):
        response = {**APPROVAL_PAYLOAD, "status": "SUBMITTED"}
        ts_mixin.jira.post = MagicMock(return_value=response)

        result = ts_mixin.submit_approval("john.doe", "2024-01-01", "SUBMIT")

        assert isinstance(result, TempoApproval)
        assert result.status == "SUBMITTED"

    def test_builds_correct_body_minimal(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=APPROVAL_PAYLOAD)

        ts_mixin.submit_approval("john.doe", "2024-01-01", "SUBMIT")

        body = ts_mixin.jira.post.call_args[1]["data"]
        assert body["user"] == {"key": "john.doe"}
        assert body["period"] == {"dateFrom": "2024-01-01"}
        assert body["action"] == {"name": "SUBMIT"}

    def test_builds_correct_body_with_comment_and_reviewer(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(return_value=APPROVAL_PAYLOAD)

        ts_mixin.submit_approval(
            "john.doe", "2024-01-01", "APPROVE", comment="Looks good", reviewer_key="mgr"
        )

        body = ts_mixin.jira.post.call_args[1]["data"]
        assert body["action"]["comment"] == "Looks good"
        assert body["action"]["reviewer"] == {"key": "mgr"}

    def test_raises_on_api_error(self, ts_mixin):
        ts_mixin.jira.post = MagicMock(side_effect=_make_http_error(400))

        with pytest.raises(HTTPError):
            ts_mixin.submit_approval("john.doe", "2024-01-01", "SUBMIT")


# ---------------------------------------------------------------------------
# get_work_attributes
# ---------------------------------------------------------------------------


class TestGetWorkAttributes:
    def test_returns_list_of_attributes(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[WORK_ATTRIBUTE_PAYLOAD])

        result = ts_mixin.get_work_attributes()

        assert len(result) == 1
        assert isinstance(result[0], TempoWorkAttribute)
        assert result[0].id == 5
        assert result[0].name == "Billing Account"
        assert result[0].required is True

    def test_calls_correct_url(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=[])

        ts_mixin.get_work_attributes()

        ts_mixin.jira.get.assert_called_once_with("rest/tempo-core/1/work-attribute")

    def test_returns_empty_list_on_api_error(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(side_effect=RuntimeError("error"))

        result = ts_mixin.get_work_attributes()

        assert result == []

    def test_returns_empty_list_when_response_not_list(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value={"unexpected": "dict"})

        result = ts_mixin.get_work_attributes()

        assert result == []


# ---------------------------------------------------------------------------
# get_user_schedule
# ---------------------------------------------------------------------------


class TestGetUserSchedule:
    def test_returns_schedule_on_success(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=USER_SCHEDULE_PAYLOAD)

        result = ts_mixin.get_user_schedule(
            user="john.doe", date_from="2024-01-15", date_to="2024-01-19"
        )

        assert isinstance(result, TempoUserSchedule)
        assert result.number_of_working_days == 5
        assert result.required_seconds == 144000
        assert len(result.days) == 2

    def test_passes_query_params_when_provided(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=USER_SCHEDULE_PAYLOAD)

        ts_mixin.get_user_schedule(
            user="john.doe", date_from="2024-01-01", date_to="2024-01-31"
        )

        ts_mixin.jira.get.assert_called_once_with(
            "rest/tempo-core/1/user/schedule",
            params={"user": "john.doe", "from": "2024-01-01", "to": "2024-01-31"},
        )

    def test_omits_none_params(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=USER_SCHEDULE_PAYLOAD)

        ts_mixin.get_user_schedule()

        params = ts_mixin.jira.get.call_args[1]["params"]
        assert params == {}

    def test_returns_empty_schedule_on_error(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(side_effect=RuntimeError("network error"))

        result = ts_mixin.get_user_schedule(user="john.doe")

        assert isinstance(result, TempoUserSchedule)
        assert result.number_of_working_days == 0
        assert result.days == []

    def test_holiday_name_parsed_in_schedule_days(self, ts_mixin):
        ts_mixin.jira.get = MagicMock(return_value=USER_SCHEDULE_PAYLOAD)

        result = ts_mixin.get_user_schedule()

        holiday_day = result.days[1]
        assert holiday_day.type == "HOLIDAY"
        assert holiday_day.holiday_name == "Bank Holiday"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _make_http_error(status_code: int) -> HTTPError:
    """Create an HTTPError with a mocked response for the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = HTTPError(response=mock_response)
    return error
