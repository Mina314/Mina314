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

    # Move the illustration farther right and keep all lines away from the pills.
    stack_x = 746

    stack_layers = [
        (stack_x, 278, 154, theme.violet),
        (stack_x + 10, 232, 154, theme.blue),
        (stack_x + 20, 186, 154, theme.cyan),
    ]

    for x, y, width, color in stack_layers:
        body.extend([
            box(
                x,
                y,
                width,
                32,
                9,
                color,
                color,
            ),
            (
                f'<rect x="{x}" y="{y}" width="{width}" height="32" '
                f'rx="9" fill="{color}" opacity=".22"/>'
            ),
        ])

    # Cards above and beside the stack.
    body.extend([
        box(
            766,
            84,
            60,
            52,
            13,
            theme.inner,
            theme.border,
        ),
        txt(
            796,
            116,
            "AI",
            16,
            theme.blue,
            800,
            "middle",
        ),

        box(
            846,
            116,
            64,
            52,
            13,
            theme.inner,
            theme.border,
        ),
        txt(
            878,
            148,
            "</>",
            15,
            theme.violet,
            800,
            "middle",
        ),

        box(
            858,
            220,
            58,
            52,
            13,
            theme.inner,
            theme.border,
        ),
        txt(
            887,
            252,
            "▥",
            22,
            theme.cyan,
            800,
            "middle",
        ),
    ])

    # Keep the workflow nodes and connector lines entirely on the right.
    nodes = [
        (722, 318),
        (792, 338),
        (878, 310),
        (902, 166),
    ]

    for nx, ny in nodes:
        body.append(
            f'<circle cx="{nx}" cy="{ny}" r="6" fill="{theme.blue}"/>'
        )

    for (x1, y1), (x2, y2) in zip(nodes, nodes[1:]):
        body.append(
            f'<line '
            f'x1="{x1}" y1="{y1}" '
            f'x2="{x2}" y2="{y2}" '
            f'stroke="{theme.violet}" '
            f'stroke-width="1.5" '
            f'opacity=".7"/>'
        )

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

def generate_work_dashboard(theme: Theme) -> str:
    uid = f"work-dashboard-{theme.name}"

    width = 960
    height = 390

    outer_x = 8
    outer_y = 8
    outer_width = 944
    outer_height = 374

    left_x = 24
    left_y = 24
    left_width = 286
    left_height = 342

    right_x = 326
    right_y = 24
    right_width = 610
    right_height = 342

    body = [
        # Entire dashboard background.
        box(
            outer_x,
            outer_y,
            outer_width,
            outer_height,
            24,
            f"url(#{uid}-bg)",
            theme.border,
            1.5,
        ),

        # Left Focus Areas panel.
        box(
            left_x,
            left_y,
            left_width,
            left_height,
            20,
            theme.panel,
            theme.border,
        ),
        txt(
            left_x + 20,
            left_y + 38,
            "Focus Areas",
            20,
            theme.text,
            750,
        ),

        # Right Selected Projects panel.
        box(
            right_x,
            right_y,
            right_width,
            right_height,
            20,
            theme.panel,
            theme.border,
        ),
        txt(
            right_x + 20,
            right_y + 38,
            "Selected Projects",
            20,
            theme.text,
            750,
        ),
        txt(
            right_x + right_width - 20,
            right_y + 38,
            "View all",
            12,
            theme.blue,
            650,
            "end",
        ),
    ]

    focus_rows = [
        {
            "title": "Agentic Workflows",
            "line1": "Triage, classification, scoring,",
            "line2": "routing, and human review.",
            "kind": "agent",
            "color": theme.cyan,
        },
        {
            "title": "Automation Systems",
            "line1": "GitHub, Jira, Slack, APIs,",
            "line2": "n8n, and internal tools.",
            "kind": "automation",
            "color": theme.violet,
        },
        {
            "title": "Operational Intelligence",
            "line1": "Signals for risk, ownership,",
            "line2": "incidents, SLAs, and delivery.",
            "kind": "signal",
            "color": theme.blue,
        },
    ]

    focus_row_x = left_x + 16
    focus_row_width = left_width - 32
    focus_row_height = 78

    for index, item in enumerate(focus_rows):
        row_y = left_y + 58 + index * 88

        body.extend([
            box(
                focus_row_x,
                row_y,
                focus_row_width,
                focus_row_height,
                14,
                theme.inner,
                theme.border,
            ),
            icon(
                item["kind"],
                focus_row_x + 14,
                row_y + 21,
                theme,
            ),
            txt(
                focus_row_x + 70,
                row_y + 27,
                item["title"],
                14,
                theme.text,
                700,
            ),
            txt(
                focus_row_x + 70,
                row_y + 49,
                item["line1"],
                11,
                theme.secondary,
            ),
            txt(
                focus_row_x + 70,
                row_y + 65,
                item["line2"],
                11,
                theme.secondary,
            ),
            txt(
                focus_row_x + focus_row_width - 18,
                row_y + 48,
                "›",
                24,
                theme.muted,
                500,
                "middle",
            ),
        ])

    project_cards = [
        {
            "title1": "Agentic Issue",
            "title2": "Triage",
            "desc1": "Issue summaries, risk scoring,",
            "desc2": "routing, and human review.",
            "tag": "Agentic AI",
            "kind": "agent",
            "color": theme.cyan,
        },
        {
            "title1": "GitHub Portfolio",
            "title2": "Intelligence",
            "desc1": "Self-updating repository",
            "desc2": "analytics and profile insights.",
            "tag": "Python · GitHub API",
            "kind": "signal",
            "color": theme.blue,
        },
        {
            "title1": "Workflow",
            "title2": "Patterns",
            "desc1": "Reusable intake, approval,",
            "desc2": "routing, and escalation designs.",
            "tag": "System Design · APIs",
            "kind": "automation",
            "color": theme.violet,
        },
    ]

    card_gap = 12
    card_width = 182
    card_height = 264
    card_start_x = right_x + 20
    card_y = right_y + 58

    for index, item in enumerate(project_cards):
        card_x = card_start_x + index * (card_width + card_gap)

        body.extend([
            box(
                card_x,
                card_y,
                card_width,
                card_height,
                16,
                theme.inner,
                theme.border,
            ),

            # Project icon container.
            box(
                card_x + 14,
                card_y + 14,
                50,
                50,
                13,
                theme.panel,
                theme.border,
            ),
            icon(
                item["kind"],
                card_x + 17,
                card_y + 22,
                theme,
            ),

            # Small decorative workflow line.
            (
                f'<path '
                f'd="M {card_x + 78} {card_y + 44} '
                f'L {card_x + 102} {card_y + 34} '
                f'L {card_x + 128} {card_y + 48} '
                f'L {card_x + 160} {card_y + 28}" '
                f'fill="none" '
                f'stroke="{item["color"]}" '
                f'stroke-width="1.5" '
                f'opacity=".65"/>'
            ),
            (
                f'<circle '
                f'cx="{card_x + 102}" '
                f'cy="{card_y + 34}" '
                f'r="2.5" '
                f'fill="{item["color"]}"/>'
            ),
            (
                f'<circle '
                f'cx="{card_x + 128}" '
                f'cy="{card_y + 48}" '
                f'r="2.5" '
                f'fill="{item["color"]}"/>'
            ),
            (
                f'<circle '
                f'cx="{card_x + 160}" '
                f'cy="{card_y + 28}" '
                f'r="2.5" '
                f'fill="{item["color"]}"/>'
            ),

            txt(
                card_x + 14,
                card_y + 102,
                item["title1"],
                16,
                theme.text,
                750,
            ),
            txt(
                card_x + 14,
                card_y + 125,
                item["title2"],
                16,
                theme.text,
                750,
            ),

            txt(
                card_x + 14,
                card_y + 162,
                item["desc1"],
                11,
                theme.secondary,
            ),
            txt(
                card_x + 14,
                card_y + 181,
                item["desc2"],
                11,
                theme.secondary,
            ),

            # Bottom metadata separator.
            (
                f'<line '
                f'x1="{card_x + 14}" '
                f'y1="{card_y + 214}" '
                f'x2="{card_x + card_width - 14}" '
                f'y2="{card_y + 214}" '
                f'stroke="{theme.border}" '
                f'stroke-width="1"/>'
            ),
            (
                f'<circle '
                f'cx="{card_x + 20}" '
                f'cy="{card_y + 236}" '
                f'r="5" '
                f'fill="{item["color"]}"/>'
            ),
            txt(
                card_x + 32,
                card_y + 240,
                item["tag"],
                10,
                theme.muted,
                600,
            ),
        ])

    return render_svg(
        width,
        height,
        gradients(theme, uid),
        "\n".join(body),
    )



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
                body.append(
                    txt(
                        70,
                        y + 28,
                        detail,
                        12,
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

        (
            assets_dir / f"work_dashboard_{theme.name}.svg"
        ).write_text(
            generate_work_dashboard(theme),
            encoding="utf-8",
        )

        (
            assets_dir / f"portfolio_insights_{theme.name}.svg"
        ).write_text(
            generate_insights(data, theme),
            encoding="utf-8",
        )

        (
            assets_dir / f"activity_{theme.name}.svg"
        ).write_text(
            generate_activity(data, theme),
            encoding="utf-8",
        )

    for path in assets_dir.glob("*.svg"):
        ET.parse(path)
