#!/usr/bin/env python3

import argparse
import os
import sys
import textwrap
import unicodedata

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.textpath import TextPath


def _parse_legacy(line: str):
    parts = [p.strip() for p in line.split(",", 2)]
    if len(parts) != 3:
        raise ValueError(f"Line must have 3 comma-separated fields: {line}")
    step, flow, actions = parts

    # Normalize arrows to '>'
    flow_tokens = [
        token.strip()
        for token in flow.replace("→", ">").replace("－", ">").replace("—", ">").split(">")
        if token.strip()
    ]
    norm = {
        "C": "C",
        "F": "F",
        "B": "B",
        "P": "P",
        "FRONT": "F",
        "FRONTSTAGE": "F",
        "BACK": "B",
        "BACKSTAGE": "B",
        "CUSTOMER": "C",
        "CLIENT": "C",
        "CUST": "C",
        "SUPPORT": "P",
        "SUP": "P",
        "PROCESS": "P",
        "PROC": "P",
    }
    allowed_roles = {"C", "F", "B", "P"}
    flow_seq = []
    for token in flow_tokens:
        key = token.upper()
        code = norm.get(key)
        if code is None and key:
            code = norm.get(key[0])
        if code is None and key:
            code = key[0]
        if code not in allowed_roles:
            raise ValueError(f"Unsupported flow code '{token}' (expected one of {sorted(allowed_roles)})")
        flow_seq.append(code)

    act_seq = actions.replace("→", ">").split(">")
    act_seq = [a.strip() for a in act_seq if a.strip()]
    if len(flow_seq) != len(act_seq):
        if len(flow_seq) < len(act_seq):
            flow_seq += [""] * (len(act_seq) - len(flow_seq))
        else:
            act_seq += [""] * (len(flow_seq) - len(act_seq))
    edges = [(i, i + 1) for i in range(len(flow_seq) - 1)]
    return step, flow_seq, act_seq, edges


def _parse_inline_labeled(line: str):
    # Normalize full-width forms and arrows
    line = unicodedata.normalize("NFKC", line)
    # Split into step and the labeled sequence by first whitespace
    if not line.strip():
        raise ValueError("Empty line")
    stripped = line.strip()
    if ":" in stripped:
        step_part, labeled_part = stripped.split(":", 1)
        step = step_part.strip()
        labeled = labeled_part.strip()
    else:
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            raise ValueError(
                "Inline-labeled format requires 'Step:FAction/...' または 'Step FAction/...'"
            )
        step, labeled = parts
    # Use '/' or '>' or '→' as separators
    labeled = labeled.replace("→", "/").replace(">", "/")

    segments = []
    separators = []
    buf = []
    i = 0
    while i < len(labeled):
        ch = labeled[i]
        if ch == "/" or ch == "|":
            next_is_slash = i + 1 < len(labeled) and labeled[i + 1] == "/"
            segment = "".join(buf).strip()
            if not segment:
                raise ValueError("Missing role/action between separators in inline-labeled input")
            segments.append(segment)
            if ch == "|":
                separators.append("|")
                buf = []
                i += 1
                continue
            separators.append("//" if next_is_slash else "/")
            buf = []
            i += 2 if next_is_slash else 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if not tail:
        raise ValueError("Inline-labeled input must end with a role/action segment")
    segments.append(tail)

    parsed_segments = []
    for seg in segments:
        # Expect leading C/F/B/P (case-insensitive) then the action label
        role = seg[0].upper()
        if role not in {"C", "F", "B", "P"}:
            raise ValueError(f"Invalid role prefix in segment: '{seg}' (expected C/F/B/P)")
        action = seg[1:].strip()
        parsed_segments.append((role, action))

    flow_seq = [role for role, _ in parsed_segments]
    act_seq = [action for _, action in parsed_segments]

    edges = []
    for idx in range(len(parsed_segments) - 1):
        sep = separators[idx]
        if sep != "|":
            edges.append((idx, idx + 1))
        if sep == "//":
            branch_target = idx + 2
            if branch_target >= len(parsed_segments):
                raise ValueError("Double slash '//' must be followed by another role/action segment")
            edges.append((idx, branch_target))

    return step, flow_seq, act_seq, edges


def parse_line(line: str):
    # Heuristic: if the line contains two commas, treat as legacy CSV.
    # Otherwise, parse as inline-labeled.
    comma_count = line.count(",")
    if comma_count >= 2:
        try:
            return _parse_legacy(line)
        except Exception:
            # Fall through to inline parsing if legacy parse fails
            pass
    return _parse_inline_labeled(line)


def draw_page(pdf, step, flow_seq, act_seq, edges, font_prop=None):
    lanes = [("Customer", "C"), ("Front", "F"), ("Back", "B"), ("Process", "P")]
    lane_base_y = {"C": 3.0, "F": 2.2, "B": 1.4, "P": 0.6}

    n = len(flow_seq)

    # Physical dimensions (A4 landscape) and target margins [mm]
    page_width_mm = 297.0
    page_height_mm = 210.0
    margin_mm = 10.0
    content_width_mm = page_width_mm - 2 * margin_mm
    content_height_mm = page_height_mm - 2 * margin_mm

    # Figure setup aligned to 10mm margins on all sides
    fig = plt.figure(
        figsize=(page_width_mm / 25.4, page_height_mm / 25.4)
    )  # Convert mm -> inch
    fig.subplots_adjust(
        left=margin_mm / page_width_mm,
        right=1 - margin_mm / page_width_mm,
        bottom=margin_mm / page_height_mm,
        top=1 - margin_mm / page_height_mm,
    )
    ax = fig.add_subplot(111)
    ax.set_xlim(0.0, content_width_mm)
    ax.set_ylim(0.0, content_height_mm)
    ax.axis("off")

    # Map legacy vertical coordinates into physical mm space.
    legacy_bottom = 0.6
    legacy_top = 4.0
    top_padding_mm = 3.0
    bottom_padding_mm = 3.0
    usable_height_mm = content_height_mm - top_padding_mm - bottom_padding_mm
    scale_y = usable_height_mm / (legacy_top - legacy_bottom)
    offset_y = bottom_padding_mm - scale_y * legacy_bottom

    def map_y(val: float) -> float:
        return scale_y * val + offset_y

    title_y = map_y(4.0)
    recap_y = map_y(3.7)
    lane_y = {code: map_y(val) for code, val in lane_base_y.items()}

    # Horizontal span (place lane labels near left edge, points across full width)
    lane_label_x = 0.0
    lane_label_offset_mm = 0.0
    action_label_offset_mm = 6.0

    def _text_width_mm(text: str, font_prop_candidate: fm.FontProperties, size: float) -> float:
        prop = font_prop_candidate.copy() if font_prop_candidate is not None else fm.FontProperties()
        prop.set_size(size)
        try:
            path = TextPath((0, 0), text, prop=prop)
            width_points = path.get_extents().width
        except Exception:
            width_points = size * max(len(text), 1) * 0.6
        return width_points * 25.4 / 72.0

    lane_label_prop = font_prop.copy() if font_prop is not None else fm.FontProperties()
    lane_label_prop.set_size(12)
    max_label_width_mm = max(
        (_text_width_mm(label, lane_label_prop, 12) for label, _ in lanes),
        default=0.0,
    )

    lane_left_mm = lane_label_x + max_label_width_mm + 10.0
    lane_right_mm = content_width_mm

    if n == 0:
        xs = []
    elif n == 1:
        xs = [(lane_left_mm + lane_right_mm) / 2]
    else:
        spacing = (lane_right_mm - lane_left_mm) / (n - 1)
        xs = [lane_left_mm + i * spacing for i in range(n)]

    # Title
    ax.text(
        0.0,
        title_y,
        f"Step: {step}",
        fontsize=16,
        ha="left",
        va="center",
        fontproperties=font_prop,
    )

    # Recap in inline-labeled style (e.g., Fアクション / Bアクション / Sアクション)
    segments = []
    for r, a in zip(flow_seq, act_seq):
        label = f"{r} {a}" if a else r
        segments.append(label)
    recap = " / ".join(segments)
    ax.text(
        0.0,
        recap_y,
        recap,
        fontsize=10,
        ha="left",
        va="center",
        fontproperties=font_prop,
    )

    # Lanes
    for label, code in lanes:
        y = lane_y[code]
        ax.hlines(y, lane_left_mm, lane_right_mm, linewidth=1, color="#1f77b4")
        ax.text(
            lane_label_x,
            y + lane_label_offset_mm,
            label,
            fontsize=12,
            ha="left",
            va="center",
            fontproperties=font_prop,
        )

    # Points and arrows
    node_positions = {}
    for idx, (x, role, act) in enumerate(zip(xs, flow_seq, act_seq)):
        y = lane_y.get(role, 0.0)
        node_x = x
        node_positions[idx] = (node_x, y)
        ax.plot([node_x], [y], marker="o")
        wrapped = textwrap.fill(act, width=14)
        ax.text(
            node_x,
            y + action_label_offset_mm,
            wrapped,
            fontsize=9,
            ha="center",
            va="bottom",
            fontproperties=font_prop,
        )

    def _connection_style(start_idx: int, end_idx: int, sy: float, ey: float) -> str:
        if end_idx - start_idx <= 1 and abs(sy - ey) > 1e-6:
            return "arc3,rad=0.0"
        if end_idx - start_idx <= 1 and abs(sy - ey) <= 1e-6:
            return "arc3,rad=0.2"
        rad = 0.25 if sy <= ey else -0.25
        return f"arc3,rad={rad}"

    for start, end in edges:
        if start >= len(flow_seq) or end >= len(flow_seq):
            continue
        sx, sy = node_positions[start]
        ex, ey = node_positions[end]
        connection_style = _connection_style(start, end, sy, ey)
        ax.annotate(
            "",
            xy=(ex, ey),
            xytext=(sx, sy),
            arrowprops=dict(arrowstyle="->", connectionstyle=connection_style),
        )

    pdf.savefig(fig)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", nargs="?", help="Input text file path")
    parser.add_argument(
        "outfile",
        nargs="?",
        help="Output PDF path (defaults to sbp.pdf)",
    )
    parser.add_argument(
        "--in",
        dest="infile",
        help="Input text file path (deprecated; positional argument preferred)",
    )
    parser.add_argument("--out", dest="outfile", help="Output PDF path")
    args = parser.parse_args()

    infile = args.infile
    if infile is None:
        parser.error("Input file path is required (positional argument or --in).")
    outfile = args.outfile if args.outfile is not None else "sbp.pdf"

    # Ensure Unicode-capable PDF embedding to avoid ASCII-only glyph names in Type 3 fonts
    # Use TrueType (Type 42) embedding which generally handles CJK text better.
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["ps.fonttype"] = 42
    matplotlib.rcParams["pdf.use14corefonts"] = False

    # Apply platform-specific default family fallbacks
    families = []
    if sys.platform == "darwin":
        families = [
            "Hiragino Sans",
            "Hiragino Kaku Gothic ProN",
            "Hiragino Maru Gothic ProN",
            "AppleGothic",
        ]
    elif os.name == "nt":
        families = ["Yu Gothic", "Meiryo", "MS Gothic"]
    else:
        families = [
            "Noto Sans CJK JP",
            "IPAPGothic",
            "VL PGothic",
            "TakaoGothic",
            "DejaVu Sans",
        ]
    current = matplotlib.rcParams.get("font.sans-serif", [])
    matplotlib.rcParams["font.sans-serif"] = families + list(current)

    with open(infile, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    with PdfPages(outfile) as pdf:
        for line in lines:
            step, flow_seq, act_seq, edges = parse_line(line)
            draw_page(pdf, step, flow_seq, act_seq, edges)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()
