import os
import json
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from server.db import init_db, log_set, log_meal, delete_last_set, get_today_workout, get_today_meals, get_week_summary
from server.ollama_client import chat_stream_async, is_ollama_running, list_models
from server.context import build_context
from server.parsers import extract_log_block, apply_log

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
BEARER_TOKEN = os.environ.get("GYM_BEARER_TOKEN", "changeme")
security = HTTPBearer(auto_error=False)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"


def require_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if BEARER_TOKEN == "changeme":
        return  # dev mode — skip auth
    if not credentials or not secrets.compare_digest(credentials.credentials, BEARER_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Gym Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class LogSetRequest(BaseModel):
    exercise: str
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    sets: int = 1
    rpe: Optional[int] = None
    notes: Optional[str] = None


class LogMealRequest(BaseModel):
    meal_type: str = "snack"
    description: str
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "ollama": is_ollama_running()}


@app.get("/models")
def models(_=Depends(require_auth)):
    return {"models": list_models()}


@app.post("/chat")
async def chat(req: ChatRequest, _=Depends(require_auth)):
    """Stream the model's response. Side-effect: auto-commits <<LOG>> blocks."""
    if not is_ollama_running():
        raise HTTPException(503, detail="Ollama is not running on localhost:11434")

    ctx = build_context()
    system_template = SYSTEM_PROMPT_PATH.read_text()
    system_content = system_template.format(**ctx)

    messages = [{"role": "system", "content": system_content}]
    messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    full_response: list[str] = []

    async def generate():
        async for chunk in chat_stream_async(messages):
            full_response.append(chunk)
            yield chunk

        complete = "".join(full_response)
        _, payload = extract_log_block(complete)
        if payload:
            try:
                confirmation = apply_log(payload)
                yield f"\n__LOG_COMMITTED__{json.dumps({'ok': True, 'detail': confirmation, 'payload': payload})}"
            except Exception as exc:
                yield f"\n__LOG_COMMITTED__{json.dumps({'ok': False, 'detail': str(exc), 'payload': payload})}"

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/log/set")
def api_log_set(req: LogSetRequest, _=Depends(require_auth)):
    ids = log_set(req.exercise, req.weight_kg, req.reps, req.sets, req.rpe, req.notes)
    return {"logged": len(ids), "ids": ids}


@app.delete("/log/set/last")
def api_undo_last_set(_=Depends(require_auth)):
    ok = delete_last_set()
    if not ok:
        raise HTTPException(404, detail="No sets to undo")
    return {"deleted": True}


@app.post("/log/meal")
def api_log_meal(req: LogMealRequest, _=Depends(require_auth)):
    meal_id = log_meal(req.meal_type, req.description, req.calories, req.protein_g, req.carbs_g, req.fat_g)
    return {"id": meal_id}


@app.get("/summary")
def summary(_=Depends(require_auth)):
    return {
        "today_workout": get_today_workout(),
        "today_meals": get_today_meals(),
        "week_summary": get_week_summary(),
    }


# ---------------------------------------------------------------------------
# Serve the PWA — must be last so API routes take precedence
# ---------------------------------------------------------------------------
CLIENT_DIR = Path(__file__).parent.parent / "client"
if CLIENT_DIR.exists():
    app.mount("/", StaticFiles(directory=str(CLIENT_DIR), html=True), name="pwa")
