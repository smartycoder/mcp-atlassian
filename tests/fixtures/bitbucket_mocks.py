"""Mock data for Bitbucket unit tests."""

MOCK_BB_PROJECTS = [
    {"key": "PROJ", "name": "My Project", "description": "Test project", "type": "NORMAL"},
]

MOCK_BB_REPOS = [
    {"slug": "my-repo", "name": "My Repo", "project": {"key": "PROJ"}},
]

MOCK_BB_PULL_REQUESTS = [
    {
        "id": 1,
        "title": "Fix bug in login",
        "state": "OPEN",
        "fromRef": {"displayId": "feature/fix-login"},
        "toRef": {"displayId": "main"},
        "author": {"user": {"displayName": "John Doe"}},
    }
]

MOCK_BB_COMMITS = [
    {"id": "abc123def456", "message": "Fix login bug", "author": {"name": "John Doe"}},
]

MOCK_BB_BRANCHES = [
    {"displayId": "main", "isDefault": True},
    {"displayId": "feature/fix-login", "isDefault": False},
]
