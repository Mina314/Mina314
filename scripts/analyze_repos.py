#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from svg_assets import generate_all_assets

USERNAME = "Mina314"
API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data/repo_stats.json"
ASSETS_DIR = ROOT / "assets"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    token = os.getenv("GITHUB_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    else:
        log.warning("GITHUB_TOKEN is not set; contribution stats will show N/A.")
    return s


def fetch_repositories(s: requests.Session) -> list[dict[str, Any]]:
    repos = []
    page = 1
    while True:
        r = s.get(
            f"{API}/users/{USERNAME}/repos",
            params={"type": "owner", "sort": "updated", "per_page": 100, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return [r for r in repos if not r.get("fork") and not r.get("archived")]


def fetch_languages(s: requests.Session, name: str) -> dict[str, int]:
    r = s.get(f"{API}/repos/{USERNAME}/{name}/languages", timeout=30)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()

def fetch_contributions(s: requests.Session) -> dict[str, Any]:
    """
    Return:
    - commits: recognized commit contributions during the last 12 months
    - longest_streak: longest contribution streak across all available history
    """
    if "Authorization" not in s.headers:
        return {
            "commits": None,
            "longest_streak": None,
        }

    now = datetime.now(timezone.utc)

    # Get the account creation date so we know where to begin.
    user_response = s.get(
        f"{API}/users/{USERNAME}",
        timeout=30,
    )
    user_response.raise_for_status()

    created_at_value = user_response.json().get("created_at")
    if not created_at_value:
        account_created_at = now - timedelta(days=365)
    else:
        account_created_at = datetime.fromisoformat(
            created_at_value.replace("Z", "+00:00")
        )

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          contributionCalendar {
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """

    def query_period(
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        response = s.post(
            GRAPHQL,
            json={
                "query": query,
                "variables": {
                    "login": USERNAME,
                    "from": period_start.isoformat(),
                    "to": period_end.isoformat(),
                },
            },
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()

        if payload.get("errors"):
            raise RuntimeError(payload["errors"])

        user = payload.get("data", {}).get("user")
        if not user:
            raise RuntimeError(
                f"GitHub user {USERNAME} was not returned by GraphQL."
            )

        return user["contributionsCollection"]

    # Commit count for the most recent 12 months.
    last_year_start = now - timedelta(days=365)
    recent_collection = query_period(
        last_year_start,
        now,
    )
    commits_last_12_months = recent_collection[
        "totalCommitContributions"
    ]

    # Collect daily contribution counts across the account's history.
    contribution_days: dict[str, int] = {}

    window_start = account_created_at

    while window_start < now:
        # Keep each GraphQL contribution window under one year.
        window_end = min(
            window_start + timedelta(days=364),
            now,
        )

        collection = query_period(
            window_start,
            window_end,
        )

        for week in collection["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                day_date = day["date"]

                # Protect against any overlapping boundary dates.
                contribution_days[day_date] = max(
                    contribution_days.get(day_date, 0),
                    day["contributionCount"],
                )

        window_start = window_end + timedelta(days=1)

    # Calculate the longest all-time consecutive-day streak.
    longest_streak = 0
    current_streak = 0
    previous_date = None

    for date_string in sorted(contribution_days):
        current_date = datetime.strptime(
            date_string,
            "%Y-%m-%d",
        ).date()

        count = contribution_days[date_string]

        if count <= 0:
            current_streak = 0
            previous_date = current_date
            continue

        if (
            previous_date is not None
            and current_date == previous_date + timedelta(days=1)
        ):
            current_streak += 1
        else:
            current_streak = 1

        longest_streak = max(
            longest_streak,
            current_streak,
        )
        previous_date = current_date

    return {
        "commits": commits_last_12_months,
        "longest_streak": longest_streak,
    }


def fetch_current_month_commit_summary(
    s: requests.Session,
) -> dict[str, Any]:
    """
    Fetch GitHub-qualified commit contributions for the current calendar month.

    Returns:
    {
        "total": 16,
        "by_repository": {
            "Mina314": 16
        }
    }
    """
    if "Authorization" not in s.headers:
        return {
            "total": None,
            "by_repository": {},
        }

    now = datetime.now(timezone.utc)
    month_start = datetime(
        now.year,
        now.month,
        1,
        tzinfo=timezone.utc,
    )

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          commitContributionsByRepository(maxRepositories: 100) {
            repository {
              name
            }
            contributions(first: 100) {
              totalCount
            }
          }
        }
      }
    }
    """

    response = s.post(
        GRAPHQL,
        json={
            "query": query,
            "variables": {
                "login": USERNAME,
                "from": month_start.isoformat(),
                "to": now.isoformat(),
            },
        },
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    collection = payload["data"]["user"]["contributionsCollection"]

    by_repository: dict[str, int] = {}

    for item in collection.get(
        "commitContributionsByRepository",
        [],
    ):
        repo_name = item["repository"]["name"]
        count = item["contributions"]["totalCount"]
        by_repository[repo_name] = count

    return {
        "total": collection["totalCommitContributions"],
        "by_repository": by_repository,
    }

def fetch_activity(
    s: requests.Session,
    month_commits: dict[str, Any],
) -> list[dict[str, str]]:
    response = s.get(
        f"{API}/users/{USERNAME}/events/public",
        params={"per_page": 100},
        timeout=30,
    )
    response.raise_for_status()

    items: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    for event in response.json():
        event_type = event.get("type", "")
        repo = event.get("repo", {}).get("name", "").replace(
            f"{USERNAME}/",
            "",
        )
        payload = event.get("payload", {})
        created_at = event.get("created_at", "")

        action = ""
        detail = ""
        dedupe_key = ""

        if event_type == "PushEvent":
            # Keep only the newest push summary for each repository.
            dedupe_key = f"push:{repo}"

            if dedupe_key in seen_keys:
                continue

            action = f"Updated {repo}"

            commit_count = month_commits.get(
                "by_repository",
                {},
            ).get(repo)

            latest_message = ""

            before = payload.get("before")
            head = payload.get("head")
            zero_sha = "0" * 40

            if (
                before
                and head
                and before != zero_sha
                and head != zero_sha
                and before != head
            ):
                compare_response = s.get(
                    f"{API}/repos/{USERNAME}/{repo}/compare/{before}...{head}",
                    timeout=30,
                )

                if compare_response.status_code == 200:
                    commits = compare_response.json().get("commits", [])

                    if commits:
                        latest_message = (
                            commits[-1]
                            .get("commit", {})
                            .get("message", "")
                            .splitlines()[0]
                            .strip()
                        )

            if commit_count is not None and latest_message:
                detail = (
                    f"{commit_count} commit"
                    f"{'s' if commit_count != 1 else ''} this month"
                    f" · Latest: {latest_message}"
                )
            elif commit_count is not None:
                detail = (
                    f"{commit_count} commit"
                    f"{'s' if commit_count != 1 else ''} this month"
                )
            else:
                detail = "Repository updated"

        elif event_type == "PullRequestEvent":
            pull_request = payload.get("pull_request", {})
            action_name = payload.get("action", "updated").capitalize()

            dedupe_key = (
                f"pr:{repo}:"
                f"{pull_request.get('number', event.get('id', ''))}"
            )

            action = f"{action_name} pull request in {repo}"
            detail = pull_request.get("title", "")

        elif event_type == "IssuesEvent":
            issue = payload.get("issue", {})
            action_name = payload.get("action", "updated").capitalize()

            dedupe_key = (
                f"issue:{repo}:"
                f"{issue.get('number', event.get('id', ''))}"
            )

            action = f"{action_name} issue in {repo}"
            detail = issue.get("title", "")

        elif event_type == "ReleaseEvent":
            release = payload.get("release", {})
            tag = release.get("tag_name", "")

            dedupe_key = f"release:{repo}:{tag or event.get('id', '')}"

            action = f"Released {tag} in {repo}".strip()
            detail = release.get("name") or "New release published"

        elif event_type == "CreateEvent":
            ref_type = payload.get("ref_type", "item")
            ref = payload.get("ref") or ""

            dedupe_key = f"create:{repo}:{ref_type}:{ref}"

            action = f"Created {ref_type} in {repo}"
            detail = ref

        elif event_type == "ForkEvent":
            dedupe_key = f"fork:{repo}"
            action = f"Forked {repo}"
            detail = "Created a repository fork"

        elif event_type == "WatchEvent":
            dedupe_key = f"star:{repo}"
            action = f"Starred {repo}"
            detail = "Added repository to starred projects"

        else:
            continue

        if dedupe_key in seen_keys:
            continue

        seen_keys.add(dedupe_key)

        items.append(
            {
                "action": action,
                "detail": detail[:110],
                "created_at": created_at,
            }
        )

        if len(items) >= 5:
            break

    return items


def main() -> None:
    s = build_session()
    repos = fetch_repositories(s)

    language_totals: dict[str, int] = {}
    normalized = []

    for repo in repos:
        languages = fetch_languages(s, repo["name"])

        for language, amount in languages.items():
            language_totals[language] = (
                language_totals.get(language, 0) + amount
            )

        normalized.append(
            {
                "name": repo["name"],
                "url": repo["html_url"],
                "description": repo.get("description"),
                "languages": languages,
                "pushed_at": repo.get("pushed_at"),
            }
        )

    top_language = (
        max(language_totals, key=language_totals.get)
        if language_totals
        else "N/A"
    )

    contribution_data = fetch_contributions(s)
    monthly_commit_summary = fetch_current_month_commit_summary(s)

    contribution_data["commits_current_month"] = (
        monthly_commit_summary["total"]
    )

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "username": USERNAME,
        "repo_count": len(repos),
        "top_language": top_language,
        "repositories": normalized,
        "contributions": contribution_data,
        "activity": fetch_activity(s, monthly_commit_summary),
    }

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    DATA_PATH.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    generate_all_assets(data, ASSETS_DIR)
    log.info("Updated profile assets.")



if __name__ == "__main__":
    main()
