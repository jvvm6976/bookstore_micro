"""
Generate synthetic user behavior data for AI Service assignment.

Output columns:
- user_id
- product_id
- action
- timestamp

Usage:
    python scripts/generate_data_1000.py
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ACTIONS = [
    "view",
    "click",
    "search",
    "add_to_cart",
    "remove_from_cart",
    "add_to_wishlist",
    "remove_from_wishlist",
    "checkout",
    "purchase",
    "rate",
]

TRANSITIONS = {
    "view": [("click", 0.48), ("search", 0.20), ("add_to_wishlist", 0.12), ("add_to_cart", 0.14), ("view", 0.06)],
    "click": [("view", 0.24), ("add_to_cart", 0.35), ("search", 0.18), ("add_to_wishlist", 0.15), ("click", 0.08)],
    "search": [("view", 0.45), ("click", 0.32), ("add_to_cart", 0.10), ("search", 0.08), ("add_to_wishlist", 0.05)],
    "add_to_cart": [("checkout", 0.42), ("remove_from_cart", 0.20), ("purchase", 0.18), ("view", 0.10), ("add_to_cart", 0.10)],
    "remove_from_cart": [("view", 0.30), ("search", 0.25), ("add_to_cart", 0.30), ("remove_from_cart", 0.05), ("add_to_wishlist", 0.10)],
    "add_to_wishlist": [("view", 0.32), ("add_to_cart", 0.34), ("remove_from_wishlist", 0.14), ("search", 0.14), ("add_to_wishlist", 0.06)],
    "remove_from_wishlist": [("search", 0.34), ("view", 0.30), ("add_to_wishlist", 0.20), ("add_to_cart", 0.12), ("remove_from_wishlist", 0.04)],
    "checkout": [("purchase", 0.58), ("remove_from_cart", 0.12), ("view", 0.10), ("checkout", 0.10), ("add_to_cart", 0.10)],
    "purchase": [("rate", 0.36), ("view", 0.30), ("search", 0.20), ("add_to_cart", 0.08), ("purchase", 0.06)],
    "rate": [("view", 0.42), ("search", 0.26), ("click", 0.17), ("add_to_cart", 0.10), ("rate", 0.05)],
}

PERSONA_SEEDS = ["view", "search", "click", "view", "search"]

PERSONAS = {
    # Heavy exploration first, then converts later in session.
    "explorer": {
        "start": ["search", "view", "click"],
        "mid": ["view", "click", "add_to_wishlist", "add_to_cart"],
        "end": ["checkout", "purchase", "rate"],
        "purchase_prob": 0.55,
    },
    # Quicker conversion path, stronger purchase loop.
    "decisive": {
        "start": ["view", "click", "add_to_cart"],
        "mid": ["add_to_cart", "checkout", "purchase"],
        "end": ["purchase", "rate", "view"],
        "purchase_prob": 0.78,
    },
    # Often hesitates around cart/wishlist.
    "hesitant": {
        "start": ["search", "view", "add_to_wishlist"],
        "mid": ["add_to_cart", "remove_from_cart", "add_to_wishlist", "remove_from_wishlist"],
        "end": ["view", "search", "click"],
        "purchase_prob": 0.28,
    },
    # High retention: repeat purchase and post-purchase rating.
    "loyal": {
        "start": ["view", "click", "add_to_cart"],
        "mid": ["checkout", "purchase", "view"],
        "end": ["purchase", "rate", "search"],
        "purchase_prob": 0.86,
    },
}

PERSONA_WEIGHTS = [0.34, 0.22, 0.24, 0.20]

SESSION_TEMPLATES = {
    "explorer": [
        ["search", "view", "click", "view", "add_to_wishlist", "add_to_cart", "checkout", "purchase", "rate"],
        ["search", "view", "click", "search", "view", "add_to_cart", "checkout", "purchase"],
    ],
    "decisive": [
        ["view", "click", "add_to_cart", "checkout", "purchase", "rate"],
        ["view", "click", "add_to_cart", "checkout", "purchase", "view", "add_to_cart", "purchase"],
    ],
    "hesitant": [
        ["search", "view", "add_to_wishlist", "view", "add_to_cart", "remove_from_cart", "search", "view", "add_to_cart", "checkout"],
        ["search", "view", "click", "add_to_cart", "remove_from_cart", "add_to_wishlist", "remove_from_wishlist", "view"],
    ],
    "loyal": [
        ["view", "click", "add_to_cart", "checkout", "purchase", "rate", "view", "add_to_cart", "purchase"],
        ["view", "click", "add_to_cart", "checkout", "purchase", "view", "click", "add_to_cart", "checkout", "purchase", "rate"],
    ],
}


def weighted_action(rng: random.Random) -> str:
    # Initial behavior distribution before transition dynamics kick in.
    return rng.choices(
        population=ACTIONS,
        weights=[30, 20, 16, 11, 6, 5, 3, 4, 3, 2],
        k=1,
    )[0]


def next_action(prev_action: str, rng: random.Random) -> str:
    if prev_action not in TRANSITIONS:
        return weighted_action(rng)
    candidates = TRANSITIONS[prev_action]
    return rng.choices(
        population=[x[0] for x in candidates],
        weights=[x[1] for x in candidates],
        k=1,
    )[0]


def next_action_with_state(
    prev_action: str,
    session_step: int,
    session_len: int,
    persona: str,
    rng: random.Random,
    has_checkout: bool,
    has_purchase: bool,
) -> str:
    profile = PERSONAS[persona]

    progress = session_step / max(session_len, 1)
    if progress < 0.35:
        stage_pool = profile["start"]
    elif progress < 0.8:
        stage_pool = profile["mid"]
    else:
        stage_pool = profile["end"]

    # Blend stage-specific intent with generic transition dynamics.
    # Higher stage weight reduces label noise but still keeps realism.
    if rng.random() < 0.80:
        action = rng.choice(stage_pool)
    else:
        action = next_action(prev_action, rng)

    # Enforce realistic ordering around checkout/purchase/rate.
    if action == "purchase" and not has_checkout and rng.random() < 0.90:
        action = "checkout"
    if action == "rate" and not has_purchase and rng.random() < 0.96:
        action = "view"

    # Persona-level conversion tendency in later part of a session.
    if progress > 0.62 and not has_purchase and rng.random() < profile["purchase_prob"] * 0.28:
        action = "purchase" if has_checkout else "checkout"

    return action


def synthesize_session_actions(persona: str, sess_len: int, rng: random.Random) -> list[str]:
    template = rng.choice(SESSION_TEMPLATES[persona])
    actions: list[str] = []

    while len(actions) < sess_len:
        actions.extend(template)
    actions = actions[:sess_len]

    # Controlled noise keeps realism without destroying sequence signal.
    for i in range(len(actions)):
        if rng.random() < 0.09:
            prev_a = actions[i - 1] if i > 0 else actions[i]
            actions[i] = next_action(prev_a, rng)

    # Rule-based cleanup for plausible session order.
    has_checkout = False
    has_purchase = False
    has_wishlist = False
    for i, action in enumerate(actions):
        if action == "remove_from_cart" and i > 0 and "add_to_cart" not in actions[:i]:
            actions[i] = "add_to_cart"
            action = actions[i]
        if action == "remove_from_wishlist" and not has_wishlist:
            actions[i] = "add_to_wishlist"
            action = actions[i]
        if action == "purchase" and not has_checkout:
            actions[i] = "checkout"
            action = actions[i]
        if action == "rate" and not has_purchase:
            actions[i] = "view"
            action = actions[i]

        if action == "add_to_wishlist":
            has_wishlist = True
        if action == "checkout":
            has_checkout = True
        if action == "purchase":
            has_purchase = True

    return actions


def generate_rows(
    n_users: int,
    min_events: int,
    max_events: int,
    n_products: int,
    days_back: int,
    seed: int,
) -> list[list[str]]:
    rng = random.Random(seed)
    now = datetime.now()
    rows: list[list[str]] = []

    for user_idx in range(1, n_users + 1):
        user_id = f"U{user_idx:04d}"
        n_events = rng.randint(min_events, max_events)
        user_product_focus = rng.randint(1, n_products)
        persona = rng.choices(list(PERSONAS.keys()), weights=PERSONA_WEIGHTS, k=1)[0]
        current_action = rng.choice(PERSONA_SEEDS)

        # Build a realistic increasing user timeline.
        start_ts = now - timedelta(days=rng.randint(1, days_back), seconds=rng.randint(0, 86399))
        current_ts = start_ts

        # Multiple micro-sessions per user, each with stage progression.
        n_sessions = rng.randint(2, 6)
        planned = []
        remaining = n_events
        for i in range(n_sessions):
            if i == n_sessions - 1:
                planned.append(max(1, remaining))
            else:
                cap = max(1, remaining - (n_sessions - i - 1))
                sess = rng.randint(1, min(12, cap))
                planned.append(sess)
                remaining -= sess

        for sess_len in planned:
            session_actions = synthesize_session_actions(persona, sess_len, rng)

            for sess_step, action in enumerate(session_actions):

                # Keep some product consistency per user and within sessions.
                if rng.random() < 0.84:
                    product_id_num = user_product_focus + rng.randint(-2, 2)
                else:
                    product_id_num = rng.randint(1, n_products)
                product_id_num = max(1, min(n_products, product_id_num))
                product_id = f"P{product_id_num:04d}"

                # In-session events happen closer in time.
                step_minutes = rng.randint(1, 55) if sess_step > 0 else rng.randint(5, 120)
                current_ts = current_ts + timedelta(minutes=step_minutes)

                rows.append(
                    [
                        user_id,
                        product_id,
                        action,
                        current_ts.replace(microsecond=0).isoformat(sep=" "),
                    ]
                )

                current_action = action

            # Gap between sessions.
            current_ts = current_ts + timedelta(hours=rng.randint(3, 36))

    rows.sort(key=lambda r: r[3])
    return rows


def write_csv(output_path: Path, rows: list[list[str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "product_id", "action", "timestamp"])
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large user behavior dataset for assignment")
    parser.add_argument("--users", type=int, default=5000)
    parser.add_argument("--min-events", type=int, default=12)
    parser.add_argument("--max-events", type=int, default=35)
    parser.add_argument("--products", type=int, default=300)
    parser.add_argument("--days-back", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20260420)
    parser.add_argument(
        "--output",
        type=str,
        default="data/data_user5000.csv",
        help="Path relative to recommender-ai-service",
    )
    args = parser.parse_args()

    if args.users <= 0:
        raise ValueError("--users must be > 0")
    if args.min_events <= 0 or args.max_events < args.min_events:
        raise ValueError("Require 0 < min-events <= max-events")

    service_root = Path(__file__).resolve().parents[1]
    output_path = service_root / args.output

    rows = generate_rows(
        n_users=args.users,
        min_events=args.min_events,
        max_events=args.max_events,
        n_products=args.products,
        days_back=args.days_back,
        seed=args.seed,
    )
    write_csv(output_path, rows)

    action_counts = Counter(r[2] for r in rows)
    unique_users = len({r[0] for r in rows})
    unique_products = len({r[1] for r in rows})

    print(f"Created: {output_path}")
    print(f"Rows: {len(rows)} | Users: {unique_users} | Products: {unique_products}")
    print("Action distribution:")
    for action in ACTIONS:
        print(f"  - {action:11s}: {action_counts.get(action, 0)}")


if __name__ == "__main__":
    main()
