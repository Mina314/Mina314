from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FONT = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif"


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    panel: str
    inner: str
    border: str
    text: str
    secondary: str
    muted: str
    blue: str
    violet: str
    cyan: str
    green: str
    track: str


DARK = Theme("dark", "#07111f", "#0b1727", "#101f32", "#223651",
             "#f3f7ff", "#a8b5c8", "#71829b", "#4ea1ff", "#9b6cff",
             "#49d5e7", "#31c48d", "#192b40")
LIGHT = Theme("light", "#f7f9fc", "#ffffff", "#f3f6fa", "#d8e0ea",
              "#172033", "#56657a", "#8793a5", "#2563eb", "#7c3aed",
              "#0891b2", "#16855b", "#e5ebf2")


def esc(v: Any) -> str:
    return html.escape(str(v), quote=True)


def txt(x, y, value, size, color, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def box(x, y, w, h, radius, fill, stroke="none", sw=1):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def render_svg(w, h, definitions, body):
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img">\n'
        f'<defs>{definitions}</defs>\n{body}\n</svg>'
    )


def gradients(theme: Theme, uid: str):
    return (
        f'<linearGradient id="{uid}-bg" x1="0" x2="1" y1="0" y2="1">'
        f'<stop offset="0%" stop-color="{theme.bg}"/>'
        f'<stop offset="100%" stop-color="{theme.panel}"/>'
        f'</linearGradient>'
        f'<linearGradient id="{uid}-accent" x1="0" x2="1">'
        f'<stop offset="0%" stop-color="{theme.blue}"/>'
        f'<stop offset="100%" stop-color="{theme.violet}"/>'
        f'</linearGradient>'
        f'<radialGradient id="{uid}-glow" cx="78%" cy="42%" r="48%">'
        f'<stop offset="0%" stop-color="{theme.blue}" stop-opacity=".16"/>'
        f'<stop offset="100%" stop-color="{theme.blue}" stop-opacity="0"/>'
        f'</radialGradient>'
    )


def icon(kind, x, y, theme):
    if kind == "agent":
        return (
            f'<rect x="{x}" y="{y}" width="44" height="34" rx="10" fill="none" '
            f'stroke="{theme.cyan}" stroke-width="2"/>'
            f'<circle cx="{x+14}" cy="{y+17}" r="3" fill="{theme.cyan}"/>'
            f'<circle cx="{x+30}" cy="{y+17}" r="3" fill="{theme.cyan}"/>'
        )
    if kind == "automation":
        return (
            f'<circle cx="{x+22}" cy="{y+18}" r="13" fill="none" '
            f'stroke="{theme.violet}" stroke-width="3"/>'
            f'<circle cx="{x+22}" cy="{y+18}" r="5" fill="{theme.violet}"/>'
        )
    return (
        f'<rect x="{x+3}" y="{y+22}" width="7" height="14" rx="2" fill="{theme.blue}"/>'
        f'<rect x="{x+16}" y="{y+13}" width="7" height="23" rx="2" fill="{theme.blue}"/>'
        f'<rect x="{x+29}" y="{y+3}" width="7" height="33" rx="2" fill="{theme.cyan}"/>'
    )


def pill(x, y, label, theme):
    w = max(96, len(label) * 7 + 28)
    return box(x, y, w, 34, 17, theme.inner, theme.border) + txt(x+14, y+22, label, 13, theme.secondary, 600)


def generate_intro(theme):
    uid = f"intro-{theme.name}"
    d = gradients(theme, uid)

    body = [
        box(
            8,
            8,
            944,
            430,
            26,
            f"url(#{uid}-bg)",
            theme.border,
            1.5,
        ),
        (
            f'<rect x="8" y="8" width="944" height="430" rx="26" '
            f'fill="url(#{uid}-glow)"/>'
        ),

        # Keep "Hi, I’m Mina." in one text element so spacing is consistent.
        (
            f'<text x="52" y="82" '
            f'font-family="{FONT}" '
            f'font-size="34" '
            f'font-weight="700" '
            f'fill="{theme.text}">'
            f'Hi, I’m '
            f'<tspan font-weight="800" fill="url(#{uid}-accent)">Mina.</tspan>'
            f'</text>'
        ),

        txt(
            52,
            138,
            "I build agentic workflows and",
            35,
            theme.text,
            700,
        ),
        txt(
            52,
            184,
            "AI-powered operational systems.",
            35,
            theme.text,
            700,
        ),

        txt(
            52,
            229,
            "Connecting AI, APIs, automation, data, and human review",
            16,
            theme.secondary,
        ),
        txt(
            52,
            254,
            "to turn operational complexity into clear, reviewable action.",
            16,
            theme.secondary,
        ),
    ]

    # Use explicit positions and widths so the pills stay in the left content area.
    intro_pills = [
        (52, "AI Systems", 104),
        (168, "Workflow Automation", 164),
        (344, "Operational Intelligence", 190),
        (546, "Human-in-the-loop", 160),
    ]

    for x, label, width in intro_pills:
        body.extend([
            box(
                x,
                292,
                width,
                34,
                17,
                theme.inner,
                theme.border,
            ),
            txt(
                x + width / 2,
                314,
                label,
                12,
                theme.secondary,
                600,
                "middle",
            ),
        ])

    # Clean AI workflow illustration on the right.
    diagram_x = 720
    card_width = 220
    card_height = 58

    diagram_cards = [
        (
            92,
            "AI Signals",
            "Summarize & classify",
            theme.blue,
        ),
        (
            178,
            "Orchestration",
            "Prioritize, route & track",
            theme.violet,
        ),
        (
            264,
            "Human Decisions",
            "Review, escalate & deliver",
            theme.cyan,
        ),
    ]


    for index, (y, title, subtitle, accent) in enumerate(diagram_cards):
        body.extend([
            box(
                diagram_x,
                y,
                card_width,
                card_height,
                14,
                theme.inner,
                theme.border,
                1.5,
            ),
            box(
                diagram_x + 14,
                y + 15,
                28,
                28,
                8,
                accent,
                accent,
            ),
            txt(
                diagram_x + 28,
                y + 34,
                str(index + 1),
                12,
                theme.bg,
                800,
                "middle",
            ),
            txt(
                diagram_x + 54,
                y + 24,
                title,
                14,
                theme.text,
                750,
            ),
            txt(
                diagram_x + 54,
                y + 43,
                subtitle,
                9,
                theme.secondary,
                500,
            ),
        ])

        if index < len(diagram_cards) - 1:
            connector_x = diagram_x + card_width / 2
            connector_y1 = y + card_height
            connector_y2 = diagram_cards[index + 1][0]

            body.extend([
                (
                    f'<line '
                    f'x1="{connector_x}" '
                    f'y1="{connector_y1 + 5}" '
                    f'x2="{connector_x}" '
                    f'y2="{connector_y2 - 8}" '
                    f'stroke="{theme.border}" '
                    f'stroke-width="2"/>'
                ),
                (
                    f'<path '
                    f'd="M {connector_x - 4} {connector_y2 - 13} '
                    f'L {connector_x} {connector_y2 - 8} '
                    f'L {connector_x + 4} {connector_y2 - 13}" '
                    f'fill="none" '
                    f'stroke="{theme.border}" '
                    f'stroke-width="2"/>'
                ),
            ])

    return render_svg(
        960,
        446,
        d,
        "\n".join(body),
    )


FOCUS = {
    "agentic": ("Agentic Workflows", "Triage, classification, scoring,", "routing, and human review.", "agent"),
    "automation": ("Automation Systems", "GitHub, Jira, Slack, APIs,", "n8n, and internal tools.", "automation"),
    "intelligence": ("Operational Intelligence", "Signals for risk, ownership,", "incidents, SLAs, and delivery.", "signal"),
}


def generate_focus(theme, key):
    title, line1, line2, kind = FOCUS[key]
    uid = f"focus-{key}-{theme.name}"
    body = [
        box(4, 4, 292, 180, 18, f"url(#{uid}-bg)", theme.border),
        icon(kind, 24, 28, theme),
        txt(82, 52, title, 17, theme.text, 700),
        txt(24, 106, line1, 14, theme.secondary),
        txt(24, 130, line2, 14, theme.secondary),
        txt(268, 101, "›", 28, theme.muted, 400, "middle"),
    ]
    return render_svg(300, 188, gradients(theme, uid), "\n".join(body))


PROJECTS = {
    "portfolio": ("GitHub Portfolio", "Intelligence", "LIVE", "green",
                  "Self-updating repository analytics", "and responsive profile insights.", "Python · GitHub API"),
    "triage": ("Agentic Issue", "Triage", "IN DEVELOPMENT", "blue",
               "Issue summaries, risk scoring,", "routing, and human review.", "Agentic AI · Workflow"),
    "patterns": ("Workflow", "Patterns", "PLANNED", "violet",
                 "Reusable intake, approval,", "routing, and escalation designs.", "System Design · APIs"),
}


def generate_project(theme, key):
    title1, title2, status, color_name, desc1, desc2, tags = PROJECTS[key]
    uid = f"project-{key}-{theme.name}"
    status_color = getattr(theme, color_name)
    body = [
        box(4, 4, 292, 260, 18, f"url(#{uid}-bg)", theme.border),
        box(22, 22, 50, 50, 13, theme.inner, theme.border),
        icon("agent" if key == "triage" else ("automation" if key == "patterns" else "signal"), 25, 31, theme),
        txt(22, 112, title1, 20, theme.text, 750),
        txt(22, 138, title2, 20, theme.text, 750),
        box(22, 154, max(68, len(status) * 7 + 20), 24, 12, theme.inner, status_color, 1.5),
        txt(32, 171, status, 11, status_color, 800),
        txt(22, 207, desc1, 13, theme.secondary),
        txt(22, 228, desc2, 13, theme.secondary),
        txt(22, 249, tags, 12, theme.muted, 600),
    ]
    return render_svg(300, 268, gradients(theme, uid), "\n".join(body))


def generate_insights(data, theme):
    uid = f"insights-{theme.name}"
    contributions = data.get("contributions", {})
    metrics = [
        ("Repositories", str(data.get("repo_count", 0)), "public, non-archived"),
        (
            "Commits",
            (
                str(contributions.get("commits_current_month"))
                if contributions.get("commits_current_month") is not None
                else "N/A"
            ),
            "current calendar month",
        ),
        ("Top Language", data.get("top_language", "N/A"), "by GitHub language bytes"),
        (
            "Longest Streak",
            f"{contributions.get('longest_streak')} days"
            if contributions.get("longest_streak") is not None
            else "N/A",
            "all-time contribution activity",
        )
    ]
    body = [
        box(8, 8, 944, 246, 22, f"url(#{uid}-bg)", theme.border),
        txt(34, 44, "Portfolio Insights", 22, theme.text, 750),
    ]
    for i, (label, value, note) in enumerate(metrics):
        x = 28 + i * 230
        body.extend([
            box(x, 66, 210, 154, 16, theme.inner, theme.border),
            txt(x+18, 96, label, 13, theme.muted, 650),
            txt(x+18, 142, value, 28 if len(value) < 12 else 20, theme.text, 800),
            txt(x+18, 174, note, 12, theme.secondary),
        ])
        pts = [(x+18,202),(x+52,193),(x+86,198),(x+120,182),(x+154,188),(x+190,176)]
        body.append(f'<path d="M {" L ".join(f"{px} {py}" for px,py in pts)}" fill="none" stroke="{theme.blue if i%2==0 else theme.violet}" stroke-width="2.5"/>')
    return render_svg(960, 262, gradients(theme, uid), "\n".join(body))


def relative_time(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        if delta.days:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours:
            return f"{hours}h ago"
        return f"{max(1, delta.seconds // 60)}m ago"
    except ValueError:
        return ""

def generate_activity(data, theme):
    uid = f"activity-{theme.name}"
    items = data.get("activity", [])[:5]

    item_count = max(len(items), 1)

    header_height = 68
    row_height = 62
    bottom_padding = 28

    card_height = (
        header_height
        + item_count * row_height
        + bottom_padding
    )

    svg_height = card_height + 16

    body = [
        box(
            8,
            8,
            944,
            card_height,
            22,
            f"url(#{uid}-bg)",
            theme.border,
        ),
        txt(
            34,
            44,
            "Recent Activity",
            22,
            theme.text,
            750,
        ),
    ]

    if not items:
        body.append(
            txt(
                34,
                94,
                "No recent public activity found.",
                16,
                theme.secondary,
            )
        )
    else:
        colors = [
            theme.blue,
            theme.green,
            theme.violet,
            theme.cyan,
        ]

        for i, item in enumerate(items):
            y = 82 + i * 62
            color = colors[i % len(colors)]

            body.append(
                f'<circle cx="46" cy="{y}" r="8" fill="{color}"/>'
            )

            if i < len(items) - 1:
                body.append(
                    f'<line '
                    f'x1="46" y1="{y + 10}" '
                    f'x2="46" y2="{y + 52}" '
                    f'stroke="{theme.border}" '
                    f'stroke-width="2"/>'
                )

            body.append(
                txt(
                    70,
                    y + 5,
                    item.get("action", ""),
                    15,
                    theme.text,
                    650,
                )
            )

            detail = item.get("detail", "")
            if detail:
                words = detail.split()
                lines = []
                current_line = ""

                for word in words:
                    candidate = (
                        f"{current_line} {word}".strip()
                    )

                    if len(candidate) <= 44:
                        current_line = candidate
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word

                if current_line:
                    lines.append(current_line)

                for line_index, line in enumerate(lines[:2]):
                    body.append(
                        txt(
                            644,
                            y + 25 + line_index * 16,
                            line,
                            10,
                            theme.secondary,
                        )
                    )

            body.append(
                txt(
                    918,
                    y + 5,
                    relative_time(item.get("created_at", "")),
                    12,
                    theme.muted,
                    500,
                    "end",
                )
            )

    return render_svg(
        960,
        svg_height,
        gradients(theme, uid),
        "\n".join(body),
    )

def generate_insights_activity(data: dict[str, Any], theme: Theme) -> str:
    uid = f"insights-activity-{theme.name}"

    width = 960
    height = 440

    contributions = data.get("contributions", {})
    languages = data.get("language_distribution", [])
    activity = data.get("activity", [])[:4]

    repo_count = data.get("repo_count", 0)
    language_count = data.get("language_count", 0)

    commits = contributions.get("commits_current_month")
    commits_text = str(commits) if commits is not None else "N/A"

    body = [
        # Portfolio Insights panel.
        box(
            8,
            8,
            570,
            424,
            22,
            f"url(#{uid}-bg)",
            theme.border,
            1.5,
        ),
        txt(
            32,
            48,
            "Portfolio Insights",
            21,
            theme.text,
            750,
        ),

        # Activity panel.
        box(
            592,
            8,
            360,
            424,
            22,
            f"url(#{uid}-bg)",
            theme.border,
            1.5,
        ),
        txt(
            616,
            48,
            "Activity",
            21,
            theme.text,
            750,
        ),
    ]

    # Top portfolio metric cards.
    metrics = [
        (
            "Repositories",
            str(repo_count),
            "public, non-archived",
            theme.blue,
        ),
        (
            "Commits",
            commits_text,
            "current calendar month",
            theme.violet,
        ),
        (
            "Languages Used",
            str(language_count),
            "across public repositories",
            theme.cyan,
        ),
    ]

    card_width = 164
    card_height = 112
    card_gap = 12

    for index, (label, value, note, color) in enumerate(metrics):
        x = 28 + index * (card_width + card_gap)

        body.extend([
            box(
                x,
                68,
                card_width,
                card_height,
                14,
                theme.inner,
                theme.border,
            ),
            txt(
                x + 16,
                94,
                label,
                11,
                theme.muted,
                650,
            ),
            txt(
                x + 16,
                132,
                value,
                27,
                theme.text,
                800,
            ),
            txt(
                x + 16,
                150,
                note,
                9,
                theme.secondary,
            ),
        ])


        points = [
            (x + 16, 171),
            (x + 48, 164),
            (x + 80, 168),
            (x + 112, 158),
            (x + 146, 163),
        ]


        body.append(
            f'<path '
            f'd="M {" L ".join(f"{px} {py}" for px, py in points)}" '
            f'fill="none" '
            f'stroke="{color}" '
            f'stroke-width="2.5"/>'
        )

    # Language distribution heading.
    body.append(
        txt(
            32,
            220,
            "Language Distribution",
            14,
            theme.text,
            700,
        )
    )

    # Donut chart.
    donut_cx = 112
    donut_cy = 302
    donut_radius = 52
    donut_stroke = 20
    circumference = 2 * 3.14159 * donut_radius

    language_colors = [
        theme.blue,
        theme.violet,
        theme.cyan,
        theme.green,
        theme.muted,
    ]

    # Background donut track.
    body.append(
        f'<circle '
        f'cx="{donut_cx}" '
        f'cy="{donut_cy}" '
        f'r="{donut_radius}" '
        f'fill="none" '
        f'stroke="{theme.track}" '
        f'stroke-width="{donut_stroke}"/>'
    )

    offset = 0.0

    for index, language in enumerate(languages):
        percentage = float(language.get("percentage", 0))
        segment = circumference * percentage / 100
        color = language_colors[index % len(language_colors)]

        body.append(
            f'<circle '
            f'cx="{donut_cx}" '
            f'cy="{donut_cy}" '
            f'r="{donut_radius}" '
            f'fill="none" '
            f'stroke="{color}" '
            f'stroke-width="{donut_stroke}" '
            f'stroke-dasharray="{segment} {circumference - segment}" '
            f'stroke-dashoffset="{-offset}" '
            f'transform="rotate(-90 {donut_cx} {donut_cy})"/>'
        )

        offset += segment

    body.extend([
        txt(
            donut_cx,
            donut_cy - 2,
            data.get("top_language", "N/A"),
            12,
            theme.text,
            700,
            "middle",
        ),
        txt(
            donut_cx,
            donut_cy + 16,
            "Top language",
            9,
            theme.muted,
            500,
            "middle",
        ),
    ])

    # Language legend.
    for index, language in enumerate(languages):
        legend_x = 210
        legend_y = 254 + index * 27
        color = language_colors[index % len(language_colors)]

        body.extend([
            (
                f'<circle '
                f'cx="{legend_x}" '
                f'cy="{legend_y}" '
                f'r="5" '
                f'fill="{color}"/>'
            ),
            txt(
                legend_x + 14,
                legend_y + 4,
                language.get("name", ""),
                11,
                theme.secondary,
                600,
            ),
            txt(
                548,
                legend_y + 4,
                f'{language.get("percentage", 0)}%',
                11,
                theme.muted,
                600,
                "end",
            ),
        ])

    # Recent activity timeline.
    if not activity:
        body.append(
            txt(
                616,
                94,
                "No recent public activity found.",
                13,
                theme.secondary,
            )
        )
    else:
        activity_colors = [
            theme.blue,
            theme.green,
            theme.violet,
            theme.cyan,
        ]

        for index, item in enumerate(activity):
            y = 94 + index * 88
            color = activity_colors[index % len(activity_colors)]

            body.append(
                f'<circle cx="622" cy="{y}" r="8" fill="{color}"/>'
            )

            if index < len(activity) - 1:
                body.append(
                    f'<line '
                    f'x1="622" y1="{y + 10}" '
                    f'x2="622" y2="{y + 78}" '
                    f'stroke="{theme.border}" '
                    f'stroke-width="2"/>'
                )

            body.append(
                txt(
                    644,
                    y + 4,
                    item.get("action", ""),
                    12,
                    theme.text,
                    700,
                )
            )


            detail = item.get("detail", "").strip()

            if detail:
                if not detail.endswith((".", "!", "?")):
                    detail += "."

                # Short details stay at normal size.
                if len(detail) <= 34:
                    body.append(
                        txt(
                            644,
                            y + 25,
                            detail,
                            10,
                            theme.secondary,
                        )
                    )

                # Medium details stay on one line with a slightly smaller font.
                elif len(detail) <= 55:
                    body.append(
                        txt(
                            644,
                            y + 25,
                            detail,
                            8.5,
                            theme.secondary,
                        )
                    )

                # Longer details wrap naturally across two lines.
                else:
                    words = detail.split()
                    lines: list[str] = []
                    current_line = ""

                    for word in words:
                        candidate = f"{current_line} {word}".strip()

                        if len(candidate) <= 42:
                            current_line = candidate
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = word

                    if current_line:
                        lines.append(current_line)

                    for line_index, line in enumerate(lines[:2]):
                        body.append(
                            txt(
                                644,
                                y + 25 + line_index * 16,
                                line,
                                9,
                                theme.secondary,
                            )
                        )



            body.append(
                txt(
                    928,
                    y + 4,
                    relative_time(
                        item.get("created_at", "")
                    ),
                    10,
                    theme.muted,
                    500,
                    "end",
                )
            )

    return render_svg(
        width,
        height,
        gradients(theme, uid),
        "\n".join(body),
    )


def generate_all_assets(
    data: dict[str, Any],
    assets_dir: Path,
) -> None:
    assets_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for theme in (DARK, LIGHT):
        (
            assets_dir / f"intro_{theme.name}.svg"
        ).write_text(
            generate_intro(theme),
            encoding="utf-8",
        )

        for key in FOCUS:
            (
                assets_dir / f"focus_{key}_{theme.name}.svg"
            ).write_text(
                generate_focus(theme, key),
                encoding="utf-8",
            )

        for key in PROJECTS:
            (
                assets_dir / f"project_{key}_{theme.name}.svg"
            ).write_text(
                generate_project(theme, key),
                encoding="utf-8",
            )

        (
            assets_dir / f"insights_activity_{theme.name}.svg"
        ).write_text(
            generate_insights_activity(data, theme),
            encoding="utf-8",
        )

    for path in assets_dir.glob("*.svg"):
        ET.parse(path)

