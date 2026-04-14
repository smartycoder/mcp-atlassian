"""Tempo API module for mcp_atlassian."""

from .client import TempoClient
from .config import TempoConfig
from .planner import TempoPlannerMixin

try:
    from .timesheets import TempoTimesheetsMixin

    class TempoFetcher(TempoTimesheetsMixin, TempoPlannerMixin):
        """Main Tempo client providing access to all Tempo operations."""

except ImportError:  # timesheets mixin not yet available

    class TempoFetcher(TempoPlannerMixin):  # type: ignore[no-redef]
        """Main Tempo client providing access to all Tempo operations."""

__all__ = ["TempoFetcher", "TempoClient", "TempoConfig"]
