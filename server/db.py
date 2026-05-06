import sqlite3
import os
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional

DB_PATH = os.environ.get("GYM_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "gym.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER REFERENCES workouts(id),
    exercise TEXT NOT NULL,
    weight_kg REAL,
    reps INTEGER,
    rpe INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    meal_type TEXT,
    description TEXT,
    calories INTEGER,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def get_or_create_today_workout() -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM workouts WHERE date = ?", (today,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO workouts (date) VALUES (?)", (today,))
        return cur.lastrowid


def log_set(exercise: str, weight_kg: Optional[float], reps: Optional[int],
            sets_count: int = 1, rpe: Optional[int] = None, notes: Optional[str] = None) -> list[int]:
    workout_id = get_or_create_today_workout()
    inserted_ids = []
    with get_conn() as conn:
        for _ in range(sets_count):
            cur = conn.execute(
                "INSERT INTO sets (workout_id, exercise, weight_kg, reps, rpe, notes) VALUES (?,?,?,?,?,?)",
                (workout_id, exercise.lower().strip(), weight_kg, reps, rpe, notes),
            )
            inserted_ids.append(cur.lastrowid)
    return inserted_ids


def log_meal(meal_type: str, description: str, calories: Optional[int] = None,
             protein_g: Optional[float] = None, carbs_g: Optional[float] = None,
             fat_g: Optional[float] = None) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO meals (date, meal_type, description, calories, protein_g, carbs_g, fat_g) VALUES (?,?,?,?,?,?,?)",
            (today, meal_type, description, calories, protein_g, carbs_g, fat_g),
        )
        return cur.lastrowid


def delete_last_set() -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM sets ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM sets WHERE id = ?", (row["id"],))
        return True


def get_today_workout() -> dict:
    today = date.today().isoformat()
    with get_conn() as conn:
        workout = conn.execute("SELECT * FROM workouts WHERE date = ?", (today,)).fetchone()
        if not workout:
            return {"date": today, "sets": []}
        sets = conn.execute(
            "SELECT exercise, weight_kg, reps, rpe, notes, created_at FROM sets WHERE workout_id = ? ORDER BY created_at",
            (workout["id"],),
        ).fetchall()
        return {
            "date": today,
            "notes": workout["notes"],
            "sets": [dict(s) for s in sets],
        }


def get_week_summary() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT w.date, s.exercise, COUNT(*) as set_count,
                   MAX(s.weight_kg) as max_weight, SUM(s.reps) as total_reps
            FROM sets s
            JOIN workouts w ON s.workout_id = w.id
            WHERE w.date >= date('now', '-7 days')
            GROUP BY w.date, s.exercise
            ORDER BY w.date DESC, s.exercise
        """).fetchall()
        return [dict(r) for r in rows]


def get_today_meals() -> list[dict]:
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT meal_type, description, calories, protein_g, carbs_g, fat_g FROM meals WHERE date = ? ORDER BY created_at",
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_sets(exercise: str, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.weight_kg, s.reps, s.rpe, w.date
            FROM sets s JOIN workouts w ON s.workout_id = w.id
            WHERE s.exercise LIKE ?
            ORDER BY w.date DESC, s.created_at DESC
            LIMIT ?
        """, (f"%{exercise.lower()}%", limit)).fetchall()
        return [dict(r) for r in rows]
