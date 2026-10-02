"""Draw the README's diagram as plain SVG, in GitHub's light and dark colours.

    python3 docs/images/diagram.py docs/images
"""
import sys
from pathlib import Path

THEMES = {
    "light": dict(box="#f6f8fa", edge="#d0d7de", text="#1f2328", note="#59636e", arrow="#59636e",
                  accent="#ddf4ff", accent_edge="#54aeff"),
    "dark": dict(box="#151b23", edge="#3d444d", text="#f0f6fc", note="#9198a1", arrow="#9198a1",
                 accent="#0d2a4d", accent_edge="#1f6feb"),
}
W, H, BOX_H = 920, 270, 54
ROWS = (24, 108, 192)
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
PROFILES = (("claude", "~/.claude"), ("claude-work", "~/.claude-work"), ("claude-personal", "~/.claude-personal"))
LOGINS = ("Claude Code-credentials", "Claude Code-credentials-1f3a…", "Claude Code-credentials-9c0e…")


def box(c, x, y, w, h, lines, accent=False):
    fill, edge = (c["accent"], c["accent_edge"]) if accent else (c["box"], c["edge"])
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{edge}" stroke-width="1.5"/>']
    first = y + h / 2 - (len(lines) - 1) * 9 + 5
    for i, (text, small) in enumerate(lines):
        size, color = (12, c["note"]) if small else (14, c["text"])
        weight = "600" if not small else "400"
        out.append(f'<text x="{x + w / 2}" y="{first + i * 18}" text-anchor="middle" font-size="{size}" '
                   f'font-weight="{weight}" fill="{color}">{text}</text>')
    return "\n".join(out)


def arrow(c, x1, y1, x2, y2):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c["arrow"]}" stroke-width="1.5" '
            f'marker-end="url(#head)"/>')


def diagram(c):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{c["arrow"]}"/></marker></defs>',
        f'<text x="140" y="14" text-anchor="middle" font-size="12" fill="{c["note"]}">its own login (Keychain)</text>',
        f'<text x="460" y="14" text-anchor="middle" font-size="12" fill="{c["note"]}">its own settings, tools, model</text>',
        f'<text x="780" y="14" text-anchor="middle" font-size="12" fill="{c["note"]}">one history for all</text>',
        box(c, 640, ROWS[0], 260, ROWS[-1] + BOX_H - ROWS[0],
            [("Shared history", False), ("~/.claude-shared-history", True), ("", True),
             ("transcripts, checkpoints,", True), ("prompt history", True)], accent=True),
    ]
    for row, (command, directory), login in zip(ROWS, PROFILES, LOGINS):
        middle = row + BOX_H / 2
        parts += [
            box(c, 20, row, 240, BOX_H, [(login, True)]),
            box(c, 340, row, 240, BOX_H, [(command, False), (directory, True)]),
            arrow(c, 340, middle, 264, middle),
            arrow(c, 580, middle, 636, middle),
        ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


for name, colors in THEMES.items():
    Path(sys.argv[1], f"profiles-{name}.svg").write_text(diagram(colors))
