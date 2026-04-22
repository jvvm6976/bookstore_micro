"""Build KB_Graph assets for Assignment 2b.
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "recommender-ai-service" / "data" / "data_user5000.csv"
OUT_DIR = ROOT / "report_assets" / "2b"
CYPHER_PATH = OUT_DIR / "kb_graph_import.cypher"
SAMPLE_CSV_PATH = OUT_DIR / "kb_20_lines.csv"
GRAPH_IMG_PATH = OUT_DIR / "kb_graph_overview.png"
STATS_PATH = OUT_DIR / "kb_graph_stats.json"

@dataclass
class EventRow:
    user_id: str
    product_id: str
    action: str
    timestamp: str


def safe_name(value: str) -> str:
    return value.replace("'", "\\'")

def load_rows(path: Path) -> List[EventRow]:
    rows: List[EventRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(EventRow(row["user_id"], row["product_id"], row["action"], row["timestamp"]))
    return rows

def pick_sample_rows(rows: List[EventRow], sample_size: int = 20) -> List[EventRow]:
    if len(rows) <= sample_size: return rows
    step = max(len(rows) // sample_size, 1)
    return [rows[i] for i in range(0, len(rows), step)][:sample_size]

def build_sessions(sample_rows: List[EventRow]) -> List[List[int]]:
    parsed = [(datetime.fromisoformat(r.timestamp), idx) for idx, r in enumerate(sample_rows)]
    parsed.sort()
    sessions: List[List[int]] = []
    current: List[int] = []
    prev_ts = None
    for ts, idx in parsed:
        if prev_ts is None or (ts - prev_ts).total_seconds() <= 7200:
            current.append(idx)
        else:
            sessions.append(current)
            current = [idx]
        prev_ts = ts
    if current: sessions.append(current)
    return sessions

def write_sample_csv(sample_rows: List[EventRow]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with SAMPLE_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "product_id", "action", "timestamp"])
        for row in sample_rows:
            writer.writerow([row.user_id, row.product_id, row.action, row.timestamp])

def write_cypher(rows: List[EventRow]) -> None:
    lines = ["// KB Graph import for AI Service assignment 2b"]
    lines.append("UNWIND [")
    for idx, row in enumerate(rows, start=1):
        comma = "," if idx < len(rows) else ""
        session_id = f"S{((idx - 1) // 2) + 1:02d}"
        lines.append(
            "  {"
            f"event_id: 'E{idx:02d}', session_id: '{session_id}', user_id: '{safe_name(row.user_id)}', "
            f"product_id: '{safe_name(row.product_id)}', action: '{safe_name(row.action)}', "
            f"timestamp: '{safe_name(row.timestamp)}'"
            f"}}{comma}"
        )
    lines.append("] AS row")
    lines.append("MERGE (u:User {user_id: row.user_id})")
    lines.append("MERGE (s:Session {session_id: row.session_id})")
    lines.append("MERGE (e:Event {event_id: row.event_id})")
    lines.append("MERGE (p:Product {product_id: row.product_id})")
    lines.append("MERGE (a:Action {name: row.action})")
    lines.append("SET e.timestamp = row.timestamp")
    lines.append("MERGE (u)-[:HAS_SESSION]->(s)")
    lines.append("MERGE (s)-[:HAS_EVENT]->(e)")
    lines.append("MERGE (e)-[:TARGETS_PRODUCT]->(p)")
    lines.append("MERGE (e)-[:TRIGGERS_ACTION]->(a)")
    lines.append("MERGE (u)-[:INTERACTED_WITH]->(p)")
    lines.append("")
    lines.append("// Add sequential links between events in each session")
    lines.append("MATCH (s:Session)-[:HAS_EVENT]->(e:Event)")
    lines.append("WITH s, e ORDER BY e.event_id")
    lines.append("WITH s, collect(e) AS events")
    lines.append("FOREACH(i IN CASE WHEN size(events) > 1 THEN range(0, size(events)-2) ELSE [] END |")
    lines.append("  MERGE (events[i])-[:NEXT_EVENT]->(events[i+1])")
    lines.append(")")
    CYPHER_PATH.write_text("\n".join(lines), encoding="utf-8")

def build_graph(sample_rows: List[EventRow]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(21, 12))
    ax.set_xlim(0, 21)
    ax.set_ylim(-0.6, 12.2)
    ax.axis("off")
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")

    ax.text(10.5, 11.7, "KB Graph Overview from 20 Sample Behavior Rows", ha="center", va="center", fontsize=18, fontweight="bold", color="#0f172a")
    ax.text(10.5, 11.3, "Unified orthogonal layout (single graph, high density)", ha="center", va="center", fontsize=10, color="#475569")
    ax.text(10.5, 11.06, "User -> Session -> Event -> Product / Action + INTERACTED_WITH + NEXT_EVENT", ha="center", va="center", fontsize=10, color="#475569")

    column_x = {
        "User": 2.0,
        "Session": 5.4,
        "Event": 9.0,
        "Product": 12.8,
        "Action": 16.8,
    }

    node_colors = {
        "User": "#dbeafe",
        "Session": "#e0f2fe",
        "Event": "#dcfce7",
        "Product": "#fde68a",
        "Action": "#fecaca",
    }

    def add_node(
        x: float,
        y: float,
        label: str,
        color: str,
        width: float = 1.3,
        height: float = 0.46,
        font_size: int = 9,
    ) -> None:
        patch = FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.03,rounding_size=0.06",
            linewidth=1.4,
            edgecolor="#1f2937",
            facecolor=color,
            zorder=3,
        )
        ax.add_patch(patch)
        ax.text(x, y, label, ha="center", va="center", fontsize=font_size, color="#102030", zorder=4)

    def draw_orthogonal(start: Tuple[float, float], end: Tuple[float, float], bend_x: float, color: str = "#64748b") -> None:
        sx, sy = start
        ex, ey = end
        ax.plot([sx, bend_x], [sy, sy], color=color, linewidth=1.25, zorder=1)
        ax.plot([bend_x, bend_x], [sy, ey], color=color, linewidth=1.25, zorder=1)
        ax.plot([bend_x, ex - 0.08], [ey, ey], color=color, linewidth=1.25, zorder=1)
        ax.plot([ex], [ey], marker=">", markersize=4.2, color=color, zorder=2)

    for title, x in column_x.items():
        ax.text(x, 10.45, title, ha="center", va="bottom", fontsize=11, fontweight="bold", color="#1f2937")

    ordered_rows = sample_rows[:10]
    y_positions = [10.05, 9.2, 8.35, 7.5, 6.65, 5.8, 4.95, 4.1, 3.25, 2.4]
    event_points: list[Tuple[float, float]] = []

    for idx, (row, y) in enumerate(zip(ordered_rows, y_positions), start=1):
        session_label = f"S{((idx - 1) // 2) + 1:02d}"
        event_label = f"E{idx:02d}\n{row.action}"
        add_node(column_x["User"], y, row.user_id, node_colors["User"], width=1.5)
        add_node(column_x["Session"], y, session_label, node_colors["Session"], width=1.3)
        add_node(column_x["Event"], y, event_label, node_colors["Event"], width=1.75, height=0.60)
        add_node(column_x["Product"], y, row.product_id, node_colors["Product"], width=1.45)
        action_w = max(1.7, min(3.1, 0.09 * len(row.action) + 0.95))
        add_node(column_x["Action"], y, row.action, node_colors["Action"], width=action_w, font_size=8)
        event_points.append((column_x["Event"], y))

        draw_orthogonal((column_x["User"] + 0.84, y), (column_x["Session"] - 0.72, y), bend_x=3.45)
        draw_orthogonal((column_x["Session"] + 0.74, y), (column_x["Event"] - 0.96, y), bend_x=7.1)
        draw_orthogonal((column_x["Event"] + 0.95, y), (column_x["Product"] - 0.84, y), bend_x=10.95)
        draw_orthogonal((column_x["Event"] + 0.95, y - 0.12), (column_x["Action"] - 1.05, y - 0.12), bend_x=14.35)

        # Dedicated lower rail for INTERACTED_WITH, separated from main links.
        draw_orthogonal(
            (column_x["User"] + 0.84, y - 0.28),
            (column_x["Product"] - 0.84, y - 0.28),
            bend_x=8.95,
            color="#8b5cf6",
        )

    # NEXT_EVENT in each session pair, routed on right-side rail to avoid crossing other edges.
    for i in range(len(event_points) - 1):
        x1, y1 = event_points[i]
        x2, y2 = event_points[i + 1]
        if (i // 2) == ((i + 1) // 2):
            rail_x = column_x["Action"] + 1.45
            ax.plot([x1 + 1.02, rail_x], [y1, y1], color="#ef4444", linewidth=1.12, zorder=1)
            ax.plot([rail_x, rail_x], [y1, y2], color="#ef4444", linewidth=1.12, zorder=1)
            ax.plot([rail_x, x2 + 1.02], [y2, y2], color="#ef4444", linewidth=1.12, zorder=1)
            ax.plot([x2 + 1.14], [y2], marker=">", markersize=4.1, color="#ef4444", zorder=2)

    summary_box = FancyBboxPatch((0.6, 0.22), 10.2, 1.45, boxstyle="round,pad=0.04,rounding_size=0.08", linewidth=1.2, edgecolor="#334155", facecolor="#ffffff")
    ax.add_patch(summary_box)
    ax.text(0.95, 1.46, "Graph notes", fontsize=11, fontweight="bold", color="#0f172a")
    ax.text(0.95, 1.20, "• Unified single graph (no split clusters)", fontsize=9, color="#334155")
    ax.text(0.95, 0.95, "• 10 dense flows with orthogonal routing and dedicated rails", fontsize=9, color="#334155")
    ax.text(0.95, 0.70, "• Relations: HAS_SESSION, HAS_EVENT, TARGETS_PRODUCT, TRIGGERS_ACTION", fontsize=9, color="#334155")
    ax.text(0.95, 0.45, "• Extended: INTERACTED_WITH and NEXT_EVENT without overlap", fontsize=9, color="#334155")

    legend_items = [
        Patch(facecolor=node_colors["User"], edgecolor="#1f2937", label="User"),
        Patch(facecolor=node_colors["Session"], edgecolor="#1f2937", label="Session"),
        Patch(facecolor=node_colors["Event"], edgecolor="#1f2937", label="Event"),
        Patch(facecolor=node_colors["Product"], edgecolor="#1f2937", label="Product"),
        Patch(facecolor=node_colors["Action"], edgecolor="#1f2937", label="Action"),
        Patch(facecolor="#ffffff", edgecolor="#8b5cf6", label="INTERACTED_WITH"),
        Patch(facecolor="#ffffff", edgecolor="#ef4444", label="NEXT_EVENT"),
    ]
    ax.legend(handles=legend_items, loc="lower center", ncol=7, frameon=False, bbox_to_anchor=(0.5, 0.03), fontsize=9)

    fig.savefig(GRAPH_IMG_PATH, dpi=180, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

def write_stats(rows: List[EventRow], sample_rows: List[EventRow], sessions: List[List[int]]) -> None:
    action_counts = Counter(row.action for row in sample_rows)
    estimated_nodes = (len({row.user_id for row in sample_rows})
        + len({row.product_id for row in sample_rows})
        + len({row.action for row in sample_rows})
        + len(sample_rows)
        + len(sessions))
    estimated_edges = len(sample_rows) * 5
    stats = {
        "total_rows": len(rows),
        "sample_rows": len(sample_rows),
        "unique_users_sample": len({row.user_id for row in sample_rows}),
        "unique_products_sample": len({row.product_id for row in sample_rows}),
        "unique_actions_sample": len({row.action for row in sample_rows}),
        "sample_sessions": len(sessions),
        "estimated_nodes": estimated_nodes,
        "estimated_edges": estimated_edges,
        "action_counts_sample": dict(action_counts),
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2), encoding="utf-8")

def main() -> int:
    if not DATA_PATH.exists(): return 1
    rows = load_rows(DATA_PATH)
    sample_rows = pick_sample_rows(rows, 20)
    sessions = build_sessions(sample_rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_sample_csv(sample_rows)
    write_cypher(sample_rows)
    build_graph(sample_rows)
    write_stats(rows, sample_rows, sessions)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
