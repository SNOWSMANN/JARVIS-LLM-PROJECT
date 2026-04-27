# Jarvis

A voice-first personal AI operating system, inspired by JARVIS from Iron Man.

> **Not a chatbot.** This is an architecture for a trusted personal AI: wake word, voice, memory, reasoning, tool-using agent, and OS-level computer control — designed to grow module-by-module toward the JARVIS vision.

**Phase 1 (this release)**: Windows voice assistant with wake word, STT, LLM reasoning, TTS, persistent memory, multi-tool agent, and computer control. Talk to it. It talks back. It remembers you. It opens apps, controls volume, searches the web, and runs other tools safely.

**Phase 2+ (roadmap)**: smart home, vision, multi-agent team, robotics, self-improvement, mobile clients. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## What it does today

- **"Hey Jarvis"** wake word (offline, on-device, via openWakeWord)
- **Whisper** speech recognition with WebRTC VAD end-of-utterance detection
- **OpenAI** (primary) + **Ollama** (optional local fallback) reasoning
- **ElevenLabs** voice (primary) + **pyttsx3** fallback
- **Persistent memory** — SQLite + Chroma vector DB; short-term window + long-term importance-ranked facts; semantic recall on every turn
- **Tool-using agent** with a safe confirmation boundary for destructive actions
- **Windows computer control**: open apps, open websites, web search, get time, system info, set volume, media keys, screenshot, type text, press keys
- **FastAPI server** (`python -m jarvis serve`) so a mobile / web client can reuse the same brain
- **Audit log** of every action (trust > permissions > memory > intelligence)

## Priority order

```
trust > permissions > memory > safety > reliability > autonomy > intelligence > UI
```

If these ever conflict, the higher priority wins.

---

## Quickstart (Windows)

### 1. Install

Open PowerShell **in this repo's folder** and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

This installs Python deps, ffmpeg (for MP3 playback of ElevenLabs audio), and creates a `.env`.

### 2. Add your API keys

Open `.env` and fill in:

```
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB   # default: "Adam" (JARVIS-ish); change to any voice_id
```

### 3. Run

```powershell
.\.venv\Scripts\Activate.ps1

# Full voice loop — say "hey jarvis"
python -m jarvis

# Or text REPL for quick testing without a mic
python -m jarvis text

# Or one-shot
python -m jarvis once "what time is it"

# Or run as a server (for mobile / remote clients)
python -m jarvis serve
```

On the **first** voice run, openWakeWord downloads the `hey_jarvis` model (~few MB) and faster-whisper downloads the `base.en` model (~140 MB). This is a one-time setup.

---

## Quickstart (Linux / macOS, for dev)

Primary target is Windows, but the codebase runs on Linux and macOS for development:

```bash
./scripts/install_linux.sh
source .venv/bin/activate
python -m jarvis text
```

Some computer-control tools are Windows-only (volume via pycaw, typing via pyautogui). The `GenericController` provides best-effort equivalents where available.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MAIN EVENT LOOP                            │
│                   (jarvis/main.py :: voice_loop)                    │
└──────────────┬──────────────────────────────────────────────────────┘
               │
        ┌──────▼──────┐     ┌──────────────┐     ┌──────────────────┐
        │  Wake Word  │ ──▶ │    STT       │ ──▶ │     Agent        │
        │ (openWW)    │     │  (Whisper +  │     │  (LLM + tools +  │
        │             │     │   WebRTC VAD)│     │   memory)        │
        └─────────────┘     └──────────────┘     └────────┬─────────┘
                                                          │
                                      ┌───────────────────┼──────────────────┐
                                      │                   │                  │
                                ┌─────▼────┐       ┌──────▼─────┐     ┌──────▼──────┐
                                │  Memory  │       │   Tools    │     │   Control   │
                                │ SQLite + │       │  (web,     │     │  (Windows / │
                                │  Chroma  │       │  system,   │     │   generic)  │
                                │          │       │  memory)   │     │             │
                                └──────────┘       └────────────┘     └─────────────┘
                                                          │
                                                   ┌──────▼──────┐
                                                   │   TTS       │
                                                   │(ElevenLabs /│
                                                   │  pyttsx3)   │
                                                   └─────────────┘

               ┌────────────────────────────────────────────────────┐
               │  FastAPI server (jarvis/server) — for Phase 2      │
               │  mobile / web clients. Same agent brain, HTTP API. │
               └────────────────────────────────────────────────────┘
```

### Module map

| Path | Purpose |
|---|---|
| `jarvis/config/` | `.env`-backed pydantic settings |
| `jarvis/observability/` | structured logging + audit sink |
| `jarvis/core/types.py` | shared data types (turns, tool calls, results) |
| `jarvis/memory/` | SQLite (conversations, turns, memories, audit) + Chroma vector store |
| `jarvis/agent/` | LLM client (OpenAI + Ollama fallback), personality, orchestrator |
| `jarvis/tools/` | tool registry + built-in tools |
| `jarvis/control/` | OS-specific computer control (Windows primary, generic fallback) |
| `jarvis/voice/` | wake word, STT, TTS |
| `jarvis/server/` | FastAPI HTTP API for future clients |
| `jarvis/main.py` | CLI entrypoint: voice loop, text REPL, one-shot, server |

---

## Safety & trust

- **Audit log**: every tool call is recorded in SQL and `logs/audit.log`.
- **Confirmation gate**: tools flagged `requires_confirmation=True` (e.g. `type_text`) are skipped unless the user's current utterance contains an explicit consent phrase, or the agent is running at `trust_level="high"`.
- **Local-first**: SQLite + on-disk Chroma. No data leaves your machine except LLM + TTS API calls.
- **API key in .env**: never commit your `.env`. `.gitignore` already excludes it.

---

## Extending

### Add a tool

```python
from jarvis.tools import default_registry
from jarvis.tools.registry import Tool

default_registry.register(
    Tool(
        name="send_email",
        description="Send an email via SMTP.",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
        func=send_email_impl,
        requires_confirmation=True,   # will ask the user first
        category="communication",
    )
)
```

Tools are automatically surfaced to the LLM as OpenAI-style function schemas.

### Swap the LLM / TTS / STT

All three are behind thin adapters (`agent/llm.py`, `voice/tts.py`, `voice/stt.py`). Point them at Anthropic, local Llama, Deepgram, Azure, whatever.

### Point at Postgres instead of SQLite

Change `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql+psycopg://jarvis:jarvis@localhost:5432/jarvis
```

A ready-to-go Postgres + Redis `docker-compose.yml` is included.

---

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full phased plan toward movie-JARVIS capability: vision, smart home, multi-agent team, planner/scheduler, robotics, mobile, self-improvement.

---

## License

MIT.
