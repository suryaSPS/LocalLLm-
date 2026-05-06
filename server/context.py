import os
from server.db import get_today_workout, get_week_summary, get_today_meals

GOALS_FILE = os.environ.get("GYM_GOALS_FILE", os.path.join(os.path.dirname(__file__), "..", "data", "goals.txt"))

_DEFAULT_GOALS = """
- Build strength: progressive overload on squat, bench, deadlift, OHP
- Protein target: 160g/day
- Cut to 80kg, currently ~84kg
- Training split: Push / Pull / Legs, 4 days/week
""".strip()


def _load_goals() -> str:
    try:
        with open(GOALS_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return _DEFAULT_GOALS


def _format_today_workout(data: dict) -> str:
    if not data["sets"]:
        return "No sets logged yet today."
    lines = []
    for s in data["sets"]:
        parts = [s["exercise"]]
        if s["weight_kg"]:
            parts.append(f"{s['weight_kg']}kg")
        if s["reps"]:
            parts.append(f"x{s['reps']}")
        if s["rpe"]:
            parts.append(f"RPE {s['rpe']}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _format_week_summary(rows: list[dict]) -> str:
    if not rows:
        return "No workout data in the last 7 days."
    by_date: dict[str, list[str]] = {}
    for r in rows:
        entry = f"{r['exercise']}: {r['set_count']} sets, max {r['max_weight']}kg, {r['total_reps']} total reps"
        by_date.setdefault(r["date"], []).append(entry)
    lines = []
    for d in sorted(by_date, reverse=True):
        lines.append(d)
        lines.extend(f"  {e}" for e in by_date[d])
    return "\n".join(lines)


def _format_meals(meals: list[dict]) -> str:
    if not meals:
        return "No meals logged today."
    lines = []
    total_cal = total_protein = 0
    for m in meals:
        line = f"[{m['meal_type'] or 'meal'}] {m['description']}"
        extras = []
        if m["calories"]:
            extras.append(f"{m['calories']} kcal")
            total_cal += m["calories"]
        if m["protein_g"]:
            extras.append(f"{m['protein_g']}g protein")
            total_protein += m["protein_g"]
        if extras:
            line += f" ({', '.join(extras)})"
        lines.append(line)
    lines.append(f"Totals: ~{total_cal} kcal, ~{total_protein:.0f}g protein")
    return "\n".join(lines)


def build_context() -> dict:
    today_workout = get_today_workout()
    week_summary = get_week_summary()
    today_meals = get_today_meals()
    goals = _load_goals()

    return {
        "today_workout": _format_today_workout(today_workout),
        "week_summary": _format_week_summary(week_summary),
        "today_meals": _format_meals(today_meals),
        "goals": goals,
    }
