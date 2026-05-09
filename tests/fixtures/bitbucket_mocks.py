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

MOCK_BB_PR_COMMENT = {
    "id": 10,
    "text": "LGTM",
    "author": {"displayName": "John Doe"},
    "createdDate": 1710000000000,
}

MOCK_BB_PR_CHANGES = [
    {"path": {"toString": "src/main.py"}, "type": "MODIFY"},
    {"path": {"toString": "tests/test_main.py"}, "type": "ADD"},
]

MOCK_BB_DIFF = [
    {
        "source": {"toString": "src/main.py"},
        "destination": {"toString": "src/main.py"},
        "hunks": [
            {
                "segments": [
                    {"type": "REMOVED", "lines": [{"line": "old"}]},
                    {"type": "ADDED", "lines": [{"line": "new"}]},
                ]
            }
        ],
    }
]

MOCK_BB_FILE_LIST = ["src/main.py", "README.md", "setup.py"]

MOCK_BB_TAGS = [
    {"displayId": "v1.0.0", "latestCommit": "abc123def456", "type": "TAG"},
    {"displayId": "v0.9.0", "latestCommit": "789abc012def", "type": "TAG"},
]

MOCK_BB_PR_COMMENTS = [
    {
        "id": 10,
        "text": "LGTM",
        "author": {"displayName": "John Doe"},
        "createdDate": 1710000000000,
    },
    {
        "id": 11,
        "text": "Please fix the typo on line 42",
        "author": {"displayName": "Jane Smith"},
        "createdDate": 1710001000000,
    },
]

MOCK_BB_REPO = {
    "slug": "my-repo",
    "name": "My Repo",
    "project": {"key": "PROJ"},
    "links": {"clone": [{"href": "https://bitbucket.example.com/scm/proj/my-repo.git", "name": "http"}]},
}

MOCK_BB_COMMIT = {
    "id": "abc123def456",
    "displayId": "abc123d",
    "message": "Fix login bug",
    "author": {"name": "John Doe", "emailAddress": "john@example.com"},
    "authorTimestamp": 1710000000000,
    "parents": [{"id": "parent123"}],
}

MOCK_BB_SEARCH_RESULTS = [
    {
        "file": {"path": "src/main.py", "repository": {"slug": "my-repo"}},
        "hitCount": 2,
        "pathMatches": [],
    },
]

MOCK_BB_PR_DIFF = b"diff --git a/src/main.py b/src/main.py\n--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"

MOCK_BB_PR_TASKS = [
    {"id": 1, "text": "Fix failing tests", "state": "OPEN"},
    {"id": 2, "text": "Update docs", "state": "RESOLVED"},
]
