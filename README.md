# Gym Assistant

Personal AI training coach — local LLM on your laptop, voice-accessible from iPhone at any gym.

## Stack

- **Backend**: FastAPI + Ollama + SQLite
- **Frontend**: Vanilla-JS PWA (no build step)
- **Transport**: Tailscale (laptop ↔ iPhone, any network)
- **Voice**: Web Speech API — STT and TTS happen on-device on iPhone

## Quick start

### 1. Install Ollama and pull a model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
ollama serve          # port 11434
```

### 2. Install Python deps

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set a bearer token (optional but recommended)

```bash
export GYM_BEARER_TOKEN="pick-something-long"
```

Leave unset (or `changeme`) to skip auth in dev mode.

### 4. Run the server

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser to test locally.

### 5. Tailscale (reach it from the gym)

1. Install Tailscale on laptop and iPhone — same account.
2. On the laptop: `tailscale up`
3. Find your laptop's Tailscale hostname: `tailscale status`
4. On iPhone Safari: visit `http://<laptop-name>:8000`
5. Tap **Share → Add to Home Screen** → done, it's an app now.

### 6. Keep the laptop awake

**macOS**: `caffeinate -i -w $(pgrep uvicorn)`  
**Linux**: `systemd-inhibit uvicorn server.main:app --host 0.0.0.0 --port 8000`  
**Windows**: `powercfg /change standby-timeout-ac 0`

## Customise your goals

Edit `data/goals.txt` — it's injected into every prompt.

## Daily summary cron

```bash
# Add to crontab -e:
0 23 * * * cd /path/to/gym-assistant && .venv/bin/python scripts/daily_summary.py
```

Appends a journal entry to `data/journal.txt`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/chat` | Streaming LLM chat |
| POST | `/log/set` | Manually log a set |
| DELETE | `/log/set/last` | Undo last set |
| POST | `/log/meal` | Log a meal |
| GET | `/summary` | Today's workout + diet |

## Model swap

```bash
ollama pull qwen2.5:7b
export OLLAMA_MODEL=qwen2.5:7b
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GYM_BEARER_TOKEN` | `changeme` | API auth token |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama address |
| `OLLAMA_MODEL` | `llama3:8b` | Model to use |
| `GYM_DB_PATH` | `data/gym.db` | SQLite path |
| `GYM_GOALS_FILE` | `data/goals.txt` | Goals injected into prompt |
