"""Synthetic task generator for CodeForge demos and tests.

Generates mock GitHub issues, plans, and code changes to demo the pipeline.
"""

from __future__ import annotations

import json
import random
from pathlib import Path


SAMPLE_ISSUES = [
    {
        "title": "Add dark mode toggle to settings page",
        "body": "Users have requested a dark mode option. Add a toggle in /settings that persists in localStorage.",
        "complexity": "small",
    },
    {
        "title": "Bug: search returns no results for hyphenated terms",
        "body": "When a user searches for 'state-of-the-art', the API returns 0 results. The tokenizer splits on hyphens. Fix the search to handle hyphens correctly.",
        "complexity": "small",
    },
    {
        "title": "Refactor: extract user authentication to a separate service",
        "body": "The auth logic is currently mixed in the main API module. Extract it to a separate auth service with its own endpoints. Update all callers.",
        "complexity": "large",
    },
    {
        "title": "Add CSV export to the reports page",
        "body": "Add a button on /reports that exports the current data as CSV. Include all visible columns and respect current filters.",
        "complexity": "medium",
    },
    {
        "title": "Bug: login session expires too quickly",
        "body": "Users are being logged out after 5 minutes of inactivity. Increase to 1 hour. Also add a 'remember me' option for 30-day sessions.",
        "complexity": "small",
    },
]


def main() -> int:
    out = Path("output")
    out.mkdir(exist_ok=True)
    issues = []
    for i, issue in enumerate(SAMPLE_ISSUES, 1):
        issue["issue_number"] = 100 + i
        issue["repo"] = "cloud-ai-architect/codeforge-swe-team-demo"
        issues.append(issue)
    (out / "issues.json").write_text(json.dumps(issues, indent=2))
    print(f"Wrote {len(issues)} sample issues to {out / 'issues.json'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
