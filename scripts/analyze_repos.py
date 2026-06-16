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
import requests
from matplotlib.patches import FancyBboxPatch
from matplotlib import rcParams

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

# Dashboard styling — SaaS analytics card aesthetic for GitHub README (~600px).
FONT_FAMILY = "DejaVu Sans"
ACCENT = "#6366F1"
ACCENT_LIGHT = "#818CF8"
CARD_BG = "#1c2128"
CARD_BORDER = "#373e47"
TEXT_PRIMARY = "#c9d1d9"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED = "#6e7681"
TRACK_BG = "#30363d"
PROGRESS_BG = "#21262d"
PORTFOLIO_EXAMPLES_URL = "https://www.datascienceportfol.io/mina"

# Professional impact metrics (not derived from GitHub API).
IMPACT_METRICS: list[tuple[str, str, str]] = [
    ("62%", "Backlog reduction", "High-priority engineering backlog"),
    ("3×", "Faster P0 response", "Incident escalation performance"),
    ("15+", "Engineering teams", "Workflows supported"),
    ("240+", "Execution risks", "High-priority risks surfaced"),
    ("28K", "Daily CI jobs", "Pipeline operations supported"),
    ("8%", "Unknown root cause", "Down from ~54–60%"),
]

# Technology capability groups — edit keywords to tune technology_mix.svg.
TECHNOLOGY_CAPABILITIES: dict[str, list[str]] = {
    "AI and agents": [
        "agent", "agentic", "llm", "ai", "machine learning", "ml",
        "copilot", "prompt", "classification", "recommendation",
    ],
    "Automation and APIs": [
        "automation", "api", "workflow", "integration", "webhook",
        "microservice", "microservices", "event", "service", "java",
    ],
    "Data and analytics": [
        "data", "analytics", "jupyter", "notebook", "pandas", "sql",
        "visualization", "visualisation", "analysis", "forecasting",
    ],
    "Infrastructure": [
        "docker", "cloud", "iot", "aws", "kubernetes", "infrastructure",
        "real-time", "processing", "stream", "typescript",
    ],
    "Developer tooling": [
        "cli", "devtool", "developer", "tool", "flashcard", "testing",
        "ci", "cd", "pipeline", "productivity",
    ],
}

CAPABILITY_ORDER = list(TECHNOLOGY_CAPABILITIES.keys())
MAX_CHART_CATEGORIES = 5

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


def classify_capability(
    name: str,
    description: str | None,
    topics: list[str],
    primary_language: str | None,
    category: str,
) -> str:
    """Assign a repository to a technology capability group."""
    category_map = {
        "Agentic AI Workflows": "AI and agents",
        "Automation & APIs": "Automation and APIs",
        "Data & Analytics": "Data and analytics",
        "Developer Tools": "Developer tooling",
        "Web Applications": "Infrastructure",
        "Learning & Experiments": "Developer tooling",
    }

    corpus = build_corpus(name, description, topics, primary_language, "")
    scores: dict[str, int] = {}
    for capability, keywords in TECHNOLOGY_CAPABILITIES.items():
        scores[capability] = count_keyword_hits(corpus, keywords)

    max_score = max(scores.values()) if scores else 0
    if max_score > 0:
        best = [cap for cap, score in scores.items() if score == max_score]
        for capability in CAPABILITY_ORDER:
            if capability in best:
                return capability

    return category_map.get(category, "Developer tooling")


def top_n_with_other(
    counts: dict[str, int], order: list[str], max_items: int = MAX_CHART_CATEGORIES
) -> list[tuple[str, int]]:
    """Return top N categories by count, rolling remainder into Other."""
    ranked = sorted(
        ((label, counts.get(label, 0)) for label in order),
        key=lambda item: item[1],
        reverse=True,
    )
    ranked = [(label, value) for label, value in ranked if value > 0]

    if len(ranked) <= max_items:
        return ranked

    top = ranked[: max_items - 1]
    other_count = sum(value for _, value in ranked[max_items - 1 :])
    if other_count > 0:
        top.append(("Other", other_count))
    return top


def build_summary(repos: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate summary statistics from normalized repository records."""
    category_counts = {cat: 0 for cat in CATEGORY_ORDER}
    maturity_counts = {label: 0 for label in MATURITY_LABELS}

    capability_counts = {cap: 0 for cap in CAPABILITY_ORDER}
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

        capability = classify_capability(
            repo["name"],
            repo.get("description"),
            repo.get("topics") or [],
            repo.get("primary_language"),
            cat,
        )
        capability_counts[capability] = capability_counts.get(capability, 0) + 1

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
        "capability_counts": capability_counts,
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
# Dashboard SVG generation
# ---------------------------------------------------------------------------


def configure_dashboard_fonts() -> None:
    """Apply modern sans-serif typography for dashboard SVGs."""
    rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [FONT_FAMILY, "Inter", "Arial", "Helvetica", "sans-serif"],
            "axes.unicode_minus": False,
        }
    )


def draw_rounded_card(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float = 0.012,
    facecolor: str = CARD_BG,
    edgecolor: str = CARD_BORDER,
    alpha: float = 0.96,
) -> FancyBboxPatch:
    """Draw a rounded dashboard card in axes coordinates."""
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        transform=ax.transAxes,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=1.0,
        alpha=alpha,
        clip_on=False,
        zorder=1,
    )
    ax.add_patch(patch)
    return patch


def draw_progress_bar(
    ax: plt.Axes,
    y: float,
    fraction: float,
    bar_left: float = 0.28,
    bar_width: float = 0.52,
    bar_height: float = 0.018,
    label: str = "",
    value_label: str = "",
) -> None:
    """Draw a thin horizontal progress bar with direct labels."""
    track = FancyBboxPatch(
        (bar_left, y - bar_height / 2),
        bar_width,
        bar_height,
        boxstyle="round,pad=0,rounding_size=0.004",
        transform=ax.transAxes,
        facecolor=TRACK_BG,
        edgecolor="none",
        zorder=2,
    )
    ax.add_patch(track)

    fill_width = max(bar_width * min(max(fraction, 0.0), 1.0), 0.001)
    fill = FancyBboxPatch(
        (bar_left, y - bar_height / 2),
        fill_width,
        bar_height,
        boxstyle="round,pad=0,rounding_size=0.004",
        transform=ax.transAxes,
        facecolor=ACCENT,
        edgecolor="none",
        zorder=3,
    )
    ax.add_patch(fill)

    ax.text(
        0.04,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="center",
        fontsize=10,
        color=TEXT_PRIMARY,
        zorder=4,
    )
    ax.text(
        bar_left + bar_width + 0.02,
        y,
        value_label,
        transform=ax.transAxes,
        ha="left",
        va="center",
        fontsize=10,
        color=TEXT_SECONDARY,
        zorder=4,
    )


def new_dashboard_figure(width: float, height: float) -> tuple[plt.Figure, plt.Axes]:
    """Create a transparent figure with a single axes, no chrome."""
    configure_dashboard_fonts()
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_alpha(0)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def save_dashboard(fig: plt.Figure, output_path: Path) -> None:
    """Save dashboard SVG with transparent background."""
    fig.savefig(output_path, format="svg", transparent=True, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    logger.info("Saved %s", output_path)


def draw_portfolio_examples_footer(ax: plt.Axes) -> None:
    """Add a clickable footer linking to the external project portfolio."""
    footer = ax.text(
        0.5,
        0.015,
        "Project examples → datascienceportfol.io/mina",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8,
        color=ACCENT_LIGHT,
        zorder=5,
    )
    footer.set_url(PORTFOLIO_EXAMPLES_URL)


def chart_impact_summary(output_path: Path) -> None:
    """Generate wide KPI card with selected professional impact metrics."""
    fig, ax = new_dashboard_figure(10, 3.2)
    draw_rounded_card(ax, 0.02, 0.06, 0.96, 0.88)

    ax.text(
        0.05,
        0.82,
        "Selected Professional Impact",
        transform=ax.transAxes,
        fontsize=14,
        fontweight="bold",
        color=TEXT_PRIMARY,
        ha="left",
        va="top",
    )
    ax.text(
        0.05,
        0.74,
        "Representative program outcomes — not GitHub repository statistics",
        transform=ax.transAxes,
        fontsize=9,
        color=TEXT_MUTED,
        ha="left",
        va="top",
    )

    cols = 3
    rows = 2
    card_w = 0.28
    card_h = 0.24
    start_x = 0.05
    start_y = 0.58
    x_gap = 0.03
    y_gap = 0.04

    for index, (value, title, subtitle) in enumerate(IMPACT_METRICS):
        col = index % cols
        row = index // cols
        x = start_x + col * (card_w + x_gap)
        y = start_y - row * (card_h + y_gap)

        draw_rounded_card(
            ax,
            x,
            y,
            card_w,
            card_h,
            radius=0.008,
            facecolor=PROGRESS_BG,
            edgecolor=CARD_BORDER,
            alpha=0.9,
        )
        ax.text(
            x + 0.03,
            y + card_h - 0.05,
            value,
            transform=ax.transAxes,
            fontsize=18,
            fontweight="bold",
            color=ACCENT_LIGHT,
            ha="left",
            va="top",
        )
        ax.text(
            x + 0.03,
            y + card_h - 0.13,
            title,
            transform=ax.transAxes,
            fontsize=10,
            fontweight="bold",
            color=TEXT_PRIMARY,
            ha="left",
            va="top",
        )
        ax.text(
            x + 0.03,
            y + 0.04,
            subtitle,
            transform=ax.transAxes,
            fontsize=8,
            color=TEXT_SECONDARY,
            ha="left",
            va="bottom",
        )

    save_dashboard(fig, output_path)


def chart_project_focus(summary: dict[str, Any], output_path: Path) -> None:
    """Generate compact horizontal progress bars for top project categories."""
    items = top_n_with_other(summary["category_counts"], CATEGORY_ORDER)
    total = sum(value for _, value in items) or 1
    row_count = max(len(items), 1)
    fig, ax = new_dashboard_figure(10, 1.8 + row_count * 0.55)

    draw_rounded_card(ax, 0.02, 0.04, 0.96, 0.92)
    ax.text(
        0.05,
        0.9,
        "Project Focus",
        transform=ax.transAxes,
        fontsize=14,
        fontweight="bold",
        color=TEXT_PRIMARY,
        ha="left",
    )
    ax.text(
        0.05,
        0.82,
        "Public repository distribution by category",
        transform=ax.transAxes,
        fontsize=9,
        color=TEXT_MUTED,
        ha="left",
    )

    start_y = 0.68
    row_step = 0.12
    short_labels = {
        "Agentic AI Workflows": "Agentic AI",
        "Automation & APIs": "Automation & APIs",
        "Data & Analytics": "Data & Analytics",
        "Developer Tools": "Developer Tools",
        "Web Applications": "Web Apps",
        "Learning & Experiments": "Learning",
    }

    for index, (label, count) in enumerate(items):
        pct = 100.0 * count / total
        draw_progress_bar(
            ax,
            y=start_y - index * row_step,
            fraction=pct / 100.0,
            label=short_labels.get(label, label),
            value_label=f"{pct:.0f}%  ({count})",
        )

    draw_portfolio_examples_footer(ax)
    save_dashboard(fig, output_path)


def chart_technology_mix(summary: dict[str, Any], output_path: Path) -> None:
    """Generate capability-grouped technology mix as a segmented bar."""
    items = top_n_with_other(summary["capability_counts"], CAPABILITY_ORDER)
    total = sum(value for _, value in items) or 1
    fig, ax = new_dashboard_figure(10, 3.0)

    draw_rounded_card(ax, 0.02, 0.06, 0.96, 0.88)
    ax.text(
        0.05,
        0.82,
        "Technology Mix",
        transform=ax.transAxes,
        fontsize=14,
        fontweight="bold",
        color=TEXT_PRIMARY,
        ha="left",
    )
    ax.text(
        0.05,
        0.74,
        "Grouped by capability using repository metadata and topics",
        transform=ax.transAxes,
        fontsize=9,
        color=TEXT_MUTED,
        ha="left",
    )

    bar_left = 0.05
    bar_width = 0.9
    bar_y = 0.58
    bar_height = 0.045
    cursor = bar_left

    for index, (label, count) in enumerate(items):
        fraction = count / total
        segment_width = bar_width * fraction
        if segment_width <= 0:
            continue
        shade = ACCENT if index == 0 else ACCENT_LIGHT
        alpha = 1.0 - (index * 0.08)
        segment = FancyBboxPatch(
            (cursor, bar_y),
            segment_width,
            bar_height,
            boxstyle="round,pad=0,rounding_size=0.003",
            transform=ax.transAxes,
            facecolor=shade,
            edgecolor="none",
            alpha=max(alpha, 0.45),
            zorder=3,
        )
        ax.add_patch(segment)
        cursor += segment_width

    label_y = 0.42
    label_step = 0.11
    for index, (label, count) in enumerate(items):
        pct = 100.0 * count / total
        y = label_y - index * label_step
        ax.plot(
            [0.05, 0.07],
            [y, y],
            transform=ax.transAxes,
            color=ACCENT if index == 0 else ACCENT_LIGHT,
            linewidth=3,
            solid_capstyle="round",
            zorder=4,
        )
        ax.text(
            0.08,
            y,
            f"{label}  ·  {pct:.0f}% ({count})",
            transform=ax.transAxes,
            fontsize=10,
            color=TEXT_PRIMARY,
            va="center",
            ha="left",
        )

    draw_portfolio_examples_footer(ax)
    save_dashboard(fig, output_path)


def generate_charts(data: dict[str, Any]) -> None:
    """Generate all dashboard SVG assets."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    summary = data["summary"]

    chart_impact_summary(ASSETS_DIR / "impact_summary.svg")
    chart_project_focus(summary, ASSETS_DIR / "project_focus.svg")
    chart_technology_mix(summary, ASSETS_DIR / "technology_mix.svg")

    legacy_files = [
        "portfolio_summary.svg",
        "language_distribution.svg",
        "repo_maturity.svg",
        "repository_activity.svg",
    ]
    for legacy in legacy_files:
        legacy_path = ASSETS_DIR / legacy
        if legacy_path.exists():
            legacy_path.unlink()
            logger.info("Removed legacy asset %s", legacy_path)


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
