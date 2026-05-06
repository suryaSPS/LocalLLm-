import json
import re
from typing import Optional

# Sentinel pattern: <<LOG>> ... <</LOG>>
_LOG_PATTERN = re.compile(r"<<LOG>>\s*(.*?)\s*<</LOG>>", re.DOTALL | re.IGNORECASE)


def extract_log_block(text: str) -> tuple[str, Optional[dict]]:
    """
    Returns (clean_text, log_payload) where clean_text has the <<LOG>> block stripped
    and log_payload is the parsed dict (or None if absent/malformed).
    """
    match = _LOG_PATTERN.search(text)
    if not match:
        return text, None

    raw_json = match.group(1).strip()
    clean_text = _LOG_PATTERN.sub("", text).strip()

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        obj_match = re.search(r"\{.*\}", raw_json, re.DOTALL)
        if obj_match:
            try:
                payload = json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                return clean_text, None
        else:
            return clean_text, None

    return clean_text, payload


def apply_log(payload: dict) -> str:
    """Execute a parsed log payload against the DB. Returns a human-readable confirmation."""
    from server.db import log_set, log_meal

    log_type = payload.get("type", "")

    if log_type == "set":
        exercise = payload.get("exercise", "unknown")
        weight_kg = payload.get("weight_kg")
        reps = payload.get("reps")
        sets_count = int(payload.get("sets", 1))
        rpe = payload.get("rpe")
        ids = log_set(exercise, weight_kg, reps, sets_count, rpe)
        return f"Logged {sets_count}x{reps} {exercise} @ {weight_kg}kg (id={ids})"

    if log_type == "meal":
        meal_type = payload.get("meal_type", "snack")
        description = payload.get("description", "")
        meal_id = log_meal(
            meal_type=meal_type,
            description=description,
            calories=payload.get("calories"),
            protein_g=payload.get("protein_g"),
            carbs_g=payload.get("carbs_g"),
            fat_g=payload.get("fat_g"),
        )
        return f"Logged meal: {description} (id={meal_id})"

    return f"Unknown log type: {log_type}"
