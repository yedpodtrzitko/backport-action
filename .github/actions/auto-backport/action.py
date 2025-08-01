#!/usr/bin/env python


import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BRANCH_FROM = "main"
BRANCH_TO = "develop"
PR_TITLE = f"[bot] backport {BRANCH_FROM} to {BRANCH_TO}"

GITHUB_TOKEN = os.getenv("BACKPORT_TOKEN") or ""
GITHUB_REPO = os.getenv("GITHUB_REPO") or "yedpodtrzitko/backport-action"
assert GITHUB_REPO, "repo not defined"
assert GITHUB_TOKEN, "token not defined"

BASE_URL = "https://api.github.com"
REQUEST_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "master-backport-bot",
}


class GitHubAPI:
    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{BASE_URL}/repos/{GITHUB_REPO}/{endpoint}"

        data = kwargs.get("json")
        if data:
            data = json.dumps(data).encode("utf-8")

        print("sending request to", url, data, method)
        req = Request(url, data=data, headers=REQUEST_HEADERS, method=method)

        try:
            with urlopen(req) as response:
                response_data = response.read().decode("utf-8")
                return json.loads(response_data)
        except HTTPError as e:
            if e.code == 403:
                print("403 error, most likely wrong token perms")
            else:
                print(f"GitHub API error: {e.code} - {e.read().decode('utf-8')}")
            raise

    def compare_commits(self, base: str, head: str) -> dict[str, Any]:
        """Compare two commits or branches."""
        return self._make_request("GET", f"compare/{base}...{head}")

    def get_pull_requests(self, state: str = "open") -> list[dict[str, Any]]:
        """List pull requests."""
        result = self._make_request("GET", f"pulls?state={state}")
        return result if isinstance(result, list) else []

    def create_pull_request(
        self, title: str, body: str, head: str, base: str
    ) -> dict[str, Any]:
        """Create a pull request."""
        data = {"title": title, "body": body, "head": head, "base": base}
        return self._make_request("POST", "pulls", json=data)


gh_client = GitHubAPI()


def has_commits_to_backport(branch_from: str, branch_to: str) -> bool:
    """Get commits that are in master but not in develop."""
    try:
        # Compare master and develop branches
        comparison = gh_client.compare_commits(branch_to, branch_from)

        if comparison["status"] == "identical":
            print(f"{branch_from} and {branch_to} branches are identical")
            return False

        if comparison["status"] == "behind":
            print(f"{branch_from} is behind {branch_to} - no backport needed")
            return False

        # Get commits that are ahead (in master but not in develop)
        commits_ahead = comparison.get("commits")
        return bool(commits_ahead)

    except Exception as e:
        print(f"Error comparing branches: {e}")
        raise


def check_existing_pull_request(title: str) -> bool:
    """Check if a pull request with the given title already exists."""
    try:
        pull_requests = gh_client.get_pull_requests("open")

        for pr in pull_requests:
            if pr["title"] == title:
                print(
                    f"Pull request with title '{title}' already exists: #{pr['number']}"
                )
                return True

        print("No existing pull request found with title:", title)
        return False

    except Exception as e:
        print(f"Error checking existing pull requests: {e}")
        raise


def create_backport_pull_request(branch_from, branch_to) -> None:
    try:
        pull_request = gh_client.create_pull_request(
            title=PR_TITLE,
            body=(
                f"## Backport from {branch_from} to {branch_to}\n\n"
                f"This pull request was automatically created to backport changes."
            ),
            head=branch_from,
            base=branch_to,
        )

        print(f"Successfully created pull request: #{pull_request['number']}")
        print(f"Pull request URL: {pull_request['html_url']}")

    except Exception as e:
        print(f"Error creating pull request: {e}")
        raise


def main():
    try:
        print(f"Starting {BRANCH_FROM} to {BRANCH_TO} backport check")

        if check_existing_pull_request(PR_TITLE):
            print("Pull request already exists, exiting")
            return

        if not has_commits_to_backport(BRANCH_FROM, BRANCH_TO):
            print("No commits to backport")
            return

        # Create pull request
        create_backport_pull_request(BRANCH_FROM, BRANCH_TO)
        print("Backport process completed successfully")

    except Exception as e:
        print(f"Backport process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
