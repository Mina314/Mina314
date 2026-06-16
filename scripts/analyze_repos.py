#!/usr/bin/env python3
"""
GitHub profile repository analytics for Mina314.

Fetches public repositories via the GitHub REST API, classifies projects
using transparent keyword rules (see PROJECT_CATEGORIES), computes maturity
scores, and generates SVG charts plus normalized JSON output.

Classification tie-break priority (highest first):
Agentic AI Workflows > Automation & APIs > Data & Analytics >
Developer Tools > Web Applications > Learning & Experiments > Other
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

USERNAME = "Mina314"
PROFILE_REPO_NAME = "Mina314"
API_BASE = "https://api.github.com"

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ASSETS_DIR = REPO_ROOT / "assets"
DATA_DIR = REPO_ROOT / "data"
OUTPUT_JSON = DATA_DIR / "repo_stats.json"

# Languages treated as markup/generated for filtering and chart exclusion.
MARKUP_LANGUAGES = {"HTML", "CSS", "JSON", "YAML", "Markdown", "XML", "SVG"}

# Maturity labels in display order.
MATURITY_LABELS = ["Production-ready", "MVP", "Prototype", "Experiment"]

# Category display order for charts.
CATEGORY_ORDER = [
    "Agentic AI Workflows",
    "Automation & APIs",
    "Data & Analytics",
    "Developer Tools",
    "Web Applications",
    "Learning & Experiments",
    "Other",
]

# ---------------------------------------------------------------------------
# Project classification keywords — edit this dictionary to tune categories.
# ---------------------------------------------------------------------------

PROJECT_CATEGORIES: dict[str, list[str]] = {
    "Agentic AI Workflows": [
        "agent",
        "agentic",
        "llm",
        "ai workflow",
        "copilot",
        "prompt",
        "human in the loop",
        "triage",
        "routing",
        "orchestration",
    ],
    "Automation & APIs": [
        "automation",
        "api",
        "workflow",
        "integration",
        "webhook",
        "apps script",
        "slack",
        "jira",
        "github actions",
        "n8n",
    ],
    "Data & Analytics": [
        "analytics",
        "dashboard",
        "data",
        "sql",
        "pandas",
        "visualization",
        "tableau",
        "reporting",
        "metrics",
        "forecasting",
    ],
    "Developer Tools": [
        "cli",
        "devtool",
        "developer productivity",
        "testing",
        "ci",
        "cd",
        "pipeline",
        "code quality",
    ],
    "Web Applications": [
        "web",
        "frontend",
        "react",
        "next.js",
        "flask",
        "fastapi",
        "streamlit",
        "dashboard app",
    ],
    "Learning & Experiments": [
        "tutorial",
        "course",
        "practice",
        "demo",
        "sample",
        "learning",
        "experiment",
    ],
}

CATEGORY_PRIORITY = CATEGORY_ORDER  # tie-break order (first = highest priority)

# Chart styling — muted palette, readable on light and dark GitHub themes.
CHART_COLORS = ["#4A90A4", "#6B8E7B", "#8B7BA8", "#A67C52", "#7A8B99", "#5C7A8A", "#9B8AA5"]
TEXT_COLOR = "#3d444d"
SUBTITLE_COLOR = "#57606a"
GRID_COLOR = "#d0d7de"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def build_session() -> requests.Session:
    """Create a requests session with optional GitHub token authentication."""
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
        logger.info("Using authenticated GitHub API requests (GITHUB_TOKEN set).")
    else:
        logger.warning(
            "GITHUB_TOKEN not set — using unauthenticated API (60 req/hr limit)."
        )
    return session


def log_rate_limit(response: requests.Response) -> None:
    """Log remaining API rate limit from response headers."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    limit = response.headers.get("X-RateLimit-Limit")
    if remaining is not None:
        logger.debug("Rate limit: %s/%s remaining", remaining, limit)


def parse_link_header(link_header: str | None) -> dict[str, str]:
    """Parse GitHub Link header into rel -> url mapping."""
    if not link_header:
        return {}
    links: dict[str, str] = {}
    for part in link_header.split(","):
        section = part.strip().split(";")
        if len(section) < 2:
            continue
        url = section[0].strip()[1:-1]
        rel_match = re.search(r'rel="([^"]+)"', section[1])
        if rel_match:
            links[rel_match.group(1)] = url
    return links


def api_get(session: requests.Session, url: str, **kwargs: Any) -> requests.Response:
    """Perform a GET request with error handling and rate-limit logging."""
    response = session.get(url, timeout=30, **kwargs)
    log_rate_limit(response)

    if response.status_code == 403 and "rate limit" in response.text.lower():
        logger.error(
            "GitHub API rate limit exceeded. Set GITHUB_TOKEN for higher limits."
        )
        response.raise_for_status()

    return response


def fetch_paginated(
    session: requests.Session, url: str, params: dict[str, Any] | None = None
) -> list[Any]:
    """Fetch all pages from a paginated GitHub API endpoint."""
    results: list[Any] = []
    current_url = url
    current_params = params

    while current_url:
        response = api_get(session, current_url, params=current_params)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            results.extend(data)
        else:
            results.append(data)

        links = parse_link_header(response.headers.get("Link"))
        if "next" in links:
            current_url = links["next"]
            current_params = None  # params are embedded in next URL
        else:
            break

    return results


def fetch_all_repos(session: requests.Session) -> list[dict[str, Any]]:
    """Fetch all public repositories owned by the configured user."""
    url = f"{API_BASE}/users/{USERNAME}/repos"
    params = {"type": "owner", "sort": "updated", "per_page": 100}
    repos = fetch_paginated(session, url, params)
    logger.info("Fetched %d public repositories for %s.", len(repos), USERNAME)
    return repos


def fetch_languages(session: requests.Session, repo_name: str) -> dict[str, int]:
    """Fetch language byte counts for a repository."""
    url = f"{API_BASE}/repos/{USERNAME}/{repo_name}/languages"
    response = api_get(session, url)
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    return response.json()


def fetch_readme(session: requests.Session, repo_name: str) -> tuple[bool, str]:
    """Fetch README text; returns (exists, text)."""
    url = f"{API_BASE}/repos/{USERNAME}/{repo_name}/readme"
    response = api_get(
        session, url, headers={"Accept": "application/vnd.github.raw"}
    )
    if response.status_code == 404:
        return False, ""
    response.raise_for_status()
    return True, response.text[:2000]


def fetch_has_release_or_tag(session: requests.Session, repo_name: str) -> bool:
    """Check whether a repo has at least one release or tag."""
    releases_url = f"{API_BASE}/repos/{USERNAME}/{repo_name}/releases"
    releases_resp = api_get(session, releases_url, params={"per_page": 1})
    if releases_resp.status_code == 200 and releases_resp.json():
        return True

    tags_url = f"{API_BASE}/repos/{USERNAME}/{repo_name}/tags"
    tags_resp = api_get(session, tags_url, params={"per_page": 1})
    if tags_resp.status_code == 200 and tags_resp.json():
        return True

    return False


def fetch_has_actions(session: requests.Session, repo_name: str) -> bool:
    """Check whether a repository has GitHub Actions workflow files."""
    url = f"{API_BASE}/repos/{USERNAME}/{repo_name}/contents/.github/workflows"
    response = api_get(session, url)
    if response.status_code == 404:
        return False
    if response.status_code == 200:
        data = response.json()
        return isinstance(data, list) and len(data) > 0
    return False


# ---------------------------------------------------------------------------
# Repository filtering
# ---------------------------------------------------------------------------


def has_meaningful_source(size_kb: int, languages: dict[str, int]) -> bool:
    """
    Determine whether a repository contains meaningful source code.

    Excludes repos that are too small, have no language data, or contain
    only markup/generated languages with trivial size.
    """
    if size_kb < 10:
        return False

    if not languages or sum(languages.values()) == 0:
        return False

    non_markup = {lang for lang in languages if lang not in MARKUP_LANGUAGES}
    if not non_markup and size_kb < 50:
        return False

    return True


def get_basic_exclusion_reason(repo: dict[str, Any]) -> str | None:
    """Return exclusion reason for fork/archived/profile checks only."""
    name = repo.get("name", "")

    if repo.get("fork"):
        return "fork"
    if repo.get("archived"):
        return "archived"
    if name == PROFILE_REPO_NAME:
        return "profile repository"

    return None


def get_source_exclusion_reason(
    repo: dict[str, Any], languages: dict[str, int]
) -> str | None:
    """Return exclusion reason when a repo lacks meaningful source content."""
    size_kb = repo.get("size", 0)
    if not has_meaningful_source(size_kb, languages):
        return "no meaningful source files"
    return None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def build_corpus(
    name: str,
    description: str | None,
    topics: list[str],
    primary_language: str | None,
    readme_text: str,
) -> str:
    """Build a lowercase searchable text corpus for keyword matching."""
    parts = [
        name,
        description or "",
        " ".join(topics),
        primary_language or "",
        readme_text[:2000],
    ]
    return " ".join(parts).lower()


def count_keyword_hits(corpus: str, keywords: list[str]) -> int:
    """Count keyword matches in corpus (word-boundary or phrase substring)."""
    hits = 0
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if " " in keyword_lower:
            if keyword_lower in corpus:
                hits += 1
        else:
            if re.search(rf"\b{re.escape(keyword_lower)}\b", corpus):
                hits += 1
    return hits


def classify_repo(
    name: str,
    description: str | None,
    topics: list[str],
    primary_language: str | None,
    readme_text: str,
) -> str:
    """
    Classify a repository into a project category using keyword rules.

    Scores each category by keyword hits; highest score wins. Ties are broken
    by CATEGORY_PRIORITY order.
    """
    corpus = build_corpus(name, description, topics, primary_language, readme_text)

    scores: dict[str, int] = {}
    for category, keywords in PROJECT_CATEGORIES.items():
        scores[category] = count_keyword_hits(corpus, keywords)

    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        return "Other"

    best_categories = [cat for cat, score in scores.items() if score == max_score]
    for category in CATEGORY_PRIORITY:
        if category in best_categories:
            return category

    return "Other"


# ---------------------------------------------------------------------------
# Maturity scoring
# ---------------------------------------------------------------------------


def days_between(iso_date: str | None, reference: datetime | None = None) -> int | None:
    """Compute days between an ISO date string and a reference datetime."""
    if not iso_date:
        return None
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        ref = reference or datetime.now(timezone.utc)
        return (ref - dt).days
    except (ValueError, TypeError):
        return None


def has_version_indicator(
    description: str | None,
    topics: list[str],
    has_release_or_tag: bool,
) -> bool:
    """Check for release/tag existence or version-related keywords."""
    if has_release_or_tag:
        return True
    corpus = f"{description or ''} {' '.join(topics)}".lower()
    version_keywords = ["v1", "version", "release", "v2", "semver"]
    return any(kw in corpus for kw in version_keywords)


def compute_maturity_label(score: int) -> str:
    """Map a numeric maturity score to a label."""
    if score >= 80:
        return "Production-ready"
    if score >= 60:
        return "MVP"
    if score >= 35:
        return "Prototype"
    return "Experiment"


def compute_maturity_score(
    has_readme: bool,
    description: str | None,
    topics: list[str],
    has_license: bool,
    has_actions: bool,
    days_since_push: int | None,
    has_version: bool,
    size_kb: int,
    languages: dict[str, int],
) -> int:
    """
    Compute repository maturity score (0–100).

    Formula:
      README exists .......................... 20 pts
      Description exists ..................... 10 pts
      Topics exist (>=1) ..................... 10 pts
      License exists ......................... 10 pts
      GitHub Actions workflows exist ......... 15 pts
      Recent activity (push within 90 days) .. 15 pts
      Release/tag/version indicator .......... 10 pts
      Meaningful size or multiple languages .. 10 pts
    """
    score = 0

    if has_readme:
        score += 20
    if description and description.strip():
        score += 10
    if topics:
        score += 10
    if has_license:
        score += 10
    if has_actions:
        score += 15
    if days_since_push is not None and days_since_push <= 90:
        score += 15
    if has_version:
        score += 10

    non_markup_langs = [lang for lang in languages if lang not in MARKUP_LANGUAGES]
    if size_kb >= 50 or len(non_markup_langs) >= 2:
        score += 10

    return min(score, 100)


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------


def normalize_repo(
    repo: dict[str, Any],
    languages: dict[str, int],
    has_readme: bool,
    readme_text: str,
    has_actions: bool,
    has_release_or_tag: bool,
    now: datetime,
) -> dict[str, Any]:
    """Build a normalized repository record with classification and maturity."""
    name = repo["name"]
    description = repo.get("description")
    topics = repo.get("topics") or []
    license_info = repo.get("license")
    has_license = license_info is not None

    created_at = repo.get("created_at")
    pushed_at = repo.get("pushed_at")
    age_days = days_between(created_at, now)
    days_since_push = days_between(pushed_at, now)

    category = classify_repo(
        name, description, topics, repo.get("language"), readme_text
    )

    version_indicator = has_version_indicator(description, topics, has_release_or_tag)

    maturity_score = compute_maturity_score(
        has_readme=has_readme,
        description=description,
        topics=topics,
        has_license=has_license,
        has_actions=has_actions,
        days_since_push=days_since_push,
        has_version=version_indicator,
        size_kb=repo.get("size", 0),
        languages=languages,
    )

    return {
        "name": name,
        "description": description,
        "url": repo.get("html_url", ""),
        "primary_language": repo.get("language"),
        "languages": languages,
        "topics": topics,
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "created_at": created_at,
        "updated_at": repo.get("updated_at"),
        "pushed_at": pushed_at,
        "archived": repo.get("archived", False),
        "fork": repo.get("fork", False),
        "size_kb": repo.get("size", 0),
        "has_readme": has_readme,
        "has_license": has_license,
        "has_actions": has_actions,
        "age_days": age_days,
        "days_since_push": days_since_push,
        "category": category,
        "maturity_score": maturity_score,
        "maturity_label": compute_maturity_label(maturity_score),
    }


def build_summary(repos: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate summary statistics from normalized repository records."""
    category_counts = {cat: 0 for cat in CATEGORY_ORDER}
    maturity_counts = {label: 0 for label in MATURITY_LABELS}

    language_bytes: dict[str, int] = {}
    readme_count = 0
    actions_count = 0
    maturity_scores: list[int] = []
    agentic_or_automation = 0

    for repo in repos:
        cat = repo["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

        label = repo["maturity_label"]
        maturity_counts[label] = maturity_counts.get(label, 0) + 1

        if repo["has_readme"]:
            readme_count += 1
        if repo["has_actions"]:
            actions_count += 1

        maturity_scores.append(repo["maturity_score"])

        if cat in ("Agentic AI Workflows", "Automation & APIs"):
            agentic_or_automation += 1

        for lang, bytes_count in repo["languages"].items():
            language_bytes[lang] = language_bytes.get(lang, 0) + bytes_count

    # Filter markup languages for top-language calculation unless only language.
    filtered_bytes = {
        lang: b
        for lang, b in language_bytes.items()
        if lang not in MARKUP_LANGUAGES or len(language_bytes) == 1
    }
    most_used = (
        max(filtered_bytes, key=filtered_bytes.get)
        if filtered_bytes
        else (max(language_bytes, key=language_bytes.get) if language_bytes else "N/A")
    )

    avg_maturity = round(sum(maturity_scores) / len(maturity_scores), 1) if maturity_scores else 0.0

    return {
        "category_counts": category_counts,
        "maturity_counts": maturity_counts,
        "top_languages": dict(
            sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)
        ),
        "avg_maturity_score": avg_maturity,
        "agentic_or_automation_count": agentic_or_automation,
        "readme_count": readme_count,
        "actions_count": actions_count,
        "most_used_language": most_used,
    }


def analyze_repositories(session: requests.Session) -> dict[str, Any]:
    """Main analysis pipeline: fetch, filter, enrich, classify, and summarize."""
    now = datetime.now(timezone.utc)
    raw_repos = fetch_all_repos(session)
    analyzed: list[dict[str, Any]] = []

    for repo in raw_repos:
        name = repo.get("name", "")

        basic_reason = get_basic_exclusion_reason(repo)
        if basic_reason:
            logger.info("Excluded %s: %s", name, basic_reason)
            continue

        languages = fetch_languages(session, name)

        source_reason = get_source_exclusion_reason(repo, languages)
        if source_reason:
            logger.info("Excluded %s: %s", name, source_reason)
            continue

        has_readme, readme_text = fetch_readme(session, name)
        has_actions = fetch_has_actions(session, name)
        has_release_or_tag = fetch_has_release_or_tag(session, name)

        record = normalize_repo(
            repo, languages, has_readme, readme_text, has_actions, has_release_or_tag, now
        )
        analyzed.append(record)
        logger.info(
            "Analyzed %s → %s (maturity: %d, %s)",
            name,
            record["category"],
            record["maturity_score"],
            record["maturity_label"],
        )

    summary = build_summary(analyzed)

    return {
        "generated_at": now.isoformat(),
        "username": USERNAME,
        "repo_count": len(analyzed),
        "repos": analyzed,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------


def apply_chart_style(ax: plt.Axes, fig: plt.Figure) -> None:
    """Apply transparent background and theme-friendly styling."""
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    ax.tick_params(colors=TEXT_COLOR, labelsize=10)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.grid(axis="x", color=GRID_COLOR, alpha=0.5, linewidth=0.5)


def aggregate_language_percentages(
    repos: list[dict[str, Any]],
) -> pd.Series:
    """Aggregate language bytes across repos, filter markup, return percentages."""
    totals: dict[str, int] = {}
    for repo in repos:
        langs = repo["languages"]
        non_markup = {k: v for k, v in langs.items() if k not in MARKUP_LANGUAGES}
        use_langs = non_markup if non_markup else langs
        for lang, nbytes in use_langs.items():
            totals[lang] = totals.get(lang, 0) + nbytes

    if not totals:
        return pd.Series({"No data": 100.0})

    total_bytes = sum(totals.values())
    sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)

    top_n = 8
    top = sorted_langs[:top_n]
    other_bytes = sum(b for _, b in sorted_langs[top_n:])

    labels: list[str] = []
    pcts: list[float] = []
    for lang, nbytes in top:
        labels.append(lang)
        pcts.append(round(100.0 * nbytes / total_bytes, 1))

    if other_bytes > 0:
        labels.append("Other")
        pcts.append(round(100.0 * other_bytes / total_bytes, 1))

    return pd.Series(pcts, index=labels)


def chart_language_distribution(repos: list[dict[str, Any]], output_path: Path) -> None:
    """Generate horizontal bar chart of language distribution by percentage."""
    series = aggregate_language_percentages(repos)
    fig, ax = plt.subplots(figsize=(9, max(3, len(series) * 0.45 + 1.5)))

    colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(series))]
    bars = ax.barh(series.index, series.values, color=colors, height=0.6)
    apply_chart_style(ax, fig)

    ax.set_xlabel("Share of source-code bytes (%)")
    ax.set_title("Languages Across My Projects", fontsize=14, fontweight="bold", pad=12)
    ax.invert_yaxis()

    for bar, val in zip(bars, series.values):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center",
            ha="left",
            fontsize=9,
            color=TEXT_COLOR,
        )

    fig.text(
        0.5,
        0.02,
        "Based on source-code bytes across public repositories",
        ha="center",
        fontsize=9,
        color=SUBTITLE_COLOR,
    )

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_path, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", output_path)


def chart_horizontal_counts(
    counts: dict[str, int],
    order: list[str],
    title: str,
    output_path: Path,
    xlabel: str = "Repositories",
) -> None:
    """Generate a generic horizontal bar chart for count data."""
    labels = [label for label in order if counts.get(label, 0) > 0]
    values = [counts[label] for label in labels]

    if not labels:
        labels = ["No data"]
        values = [0]

    fig, ax = plt.subplots(figsize=(9, max(3, len(labels) * 0.5 + 1.5)))
    colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(labels))]
    bars = ax.barh(labels, values, color=colors, height=0.6)
    apply_chart_style(ax, fig)

    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.invert_yaxis()

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.05,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            ha="left",
            fontsize=10,
            color=TEXT_COLOR,
        )

    plt.tight_layout()
    fig.savefig(output_path, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", output_path)


def chart_portfolio_summary(summary: dict[str, Any], repo_count: int, output_path: Path) -> None:
    """Generate a compact card-style portfolio summary chart."""
    fig, ax = plt.subplots(figsize=(9, 3.5))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    ax.axis("off")

    metrics = [
        ("Public Repositories Analyzed", str(repo_count)),
        ("Agentic AI & Automation Projects", str(summary["agentic_or_automation_count"])),
        ("Repositories with READMEs", str(summary["readme_count"])),
        ("Repositories with GitHub Actions", str(summary["actions_count"])),
        ("Most-Used Language", summary["most_used_language"]),
        ("Average Maturity Score", f"{summary['avg_maturity_score']:.1f}"),
    ]

    ax.set_title(
        "Portfolio Summary",
        fontsize=14,
        fontweight="bold",
        color=TEXT_COLOR,
        pad=16,
        loc="left",
    )

    col_width = 0.48
    row_height = 0.22
    start_y = 0.72

    for i, (label, value) in enumerate(metrics):
        col = i % 2
        row = i // 2
        x = 0.02 + col * col_width
        y = start_y - row * row_height

        ax.add_patch(
            plt.Rectangle(
                (x, y - 0.08),
                col_width - 0.04,
                row_height - 0.06,
                fill=True,
                facecolor="#f6f8fa",
                edgecolor=GRID_COLOR,
                linewidth=0.8,
                alpha=0.35,
                transform=ax.transAxes,
                clip_on=False,
            )
        )

        ax.text(
            x + 0.02,
            y + 0.04,
            label,
            transform=ax.transAxes,
            fontsize=9,
            color=SUBTITLE_COLOR,
            va="top",
        )
        ax.text(
            x + 0.02,
            y - 0.02,
            value,
            transform=ax.transAxes,
            fontsize=13,
            fontweight="bold",
            color=TEXT_COLOR,
            va="top",
        )

    plt.tight_layout()
    fig.savefig(output_path, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", output_path)


def generate_charts(data: dict[str, Any]) -> None:
    """Generate all SVG chart assets."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    repos = data["repos"]
    summary = data["summary"]

    chart_language_distribution(repos, ASSETS_DIR / "language_distribution.svg")

    chart_horizontal_counts(
        summary["category_counts"],
        CATEGORY_ORDER,
        "Project Focus",
        ASSETS_DIR / "project_focus.svg",
    )

    chart_horizontal_counts(
        summary["maturity_counts"],
        MATURITY_LABELS,
        "Project Maturity",
        ASSETS_DIR / "repo_maturity.svg",
    )

    chart_portfolio_summary(summary, data["repo_count"], ASSETS_DIR / "portfolio_summary.svg")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_json(data: dict[str, Any], path: Path) -> None:
    """Write analysis results to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved %s", path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the full analytics pipeline."""
    try:
        session = build_session()
        data = analyze_repositories(session)
        save_json(data, OUTPUT_JSON)
        generate_charts(data)
        logger.info(
            "Analysis complete: %d repositories analyzed.", data["repo_count"]
        )
        return 0
    except requests.HTTPError as exc:
        logger.error("GitHub API error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
