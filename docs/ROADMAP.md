# Jarvis roadmap — from Phase 1 to (as close as possible to) movie JARVIS

This is an honest, engineering-grounded roadmap. Movie-JARVIS-complete is
years of work by a team; this document breaks it into shippable phases that
each make the system meaningfully more capable than the previous.

Priority order (non-negotiable): **trust > permissions > memory > safety > reliability > autonomy > intelligence > UI**.

---

## Phase 1 — Voice Assistant Core (this release)

- [x] Wake word ("hey jarvis") via openWakeWord
- [x] Whisper STT with VAD
- [x] LLM reasoning (OpenAI + Ollama fallback)
- [x] ElevenLabs TTS (pyttsx3 fallback)
- [x] Short-term + long-term memory (SQLite + Chroma)
- [x] Tool-using agent with confirmation boundary
- [x] Windows computer control: apps, websites, volume, media, screenshot, input
- [x] FastAPI server endpoint for future remote/mobile clients
- [x] Audit log of every action

## Phase 2 — Memory & Personality Depth

- [ ] Rolling conversation summarizer (end-of-session → `Conversation.summary`)
- [ ] Memory relationship graph (people, places, projects, commitments)
- [ ] Importance decay + consolidation job
- [ ] "Trust memory": track which sources / users authorized which actions
- [ ] Emotional tone detection in STT output → feeds system prompt
- [ ] Persona consistency checker (detects and resists drift)

## Phase 3 — Proactive Planner

- [ ] Scheduler service (APScheduler) with persistent jobs
- [ ] Goal → plan decomposition (LangGraph or CrewAI)
- [ ] Recurring task intelligence ("every morning do X")
- [ ] Deadline & reminder engine
- [ ] Proactive-opportunity detector (notices when help is obviously needed)

## Phase 4 — Vision & Screen Understanding

- [ ] Webcam pipeline (OpenCV) — on-demand, never on by default
- [ ] Face recognition for known household members
- [ ] YOLO object detection
- [ ] Screen OCR + layout understanding for "see what I'm seeing" flows
- [ ] Scene state machine ("kitchen, night, user at stove")

## Phase 5 — Knowledge / RAG

- [ ] Document ingestion pipeline (PDF, DOCX, MD, code)
- [ ] Citation engine ("source: file.pdf p. 14")
- [ ] Trust ranking on sources
- [ ] Hallucination guard: verify claims against retrieved context
- [ ] Email / notes / codebase indexers

## Phase 6 — Smart Home / IoT

- [ ] Home Assistant bridge (long-lived token in `.env`)
- [ ] Device registry + per-device permissions
- [ ] Fail-safe overrides (e.g., never turn off essential devices)
- [ ] Room-aware behavior (lights dimmed when user asleep, etc.)

## Phase 7 — Multi-Agent Team

- [ ] Specialized agents: researcher, coder, security-auditor, PA, finance
- [ ] Shared blackboard / message bus
- [ ] Conflict resolution + priority routing
- [ ] Per-agent capability scopes

## Phase 8 — Mobile Client

- [ ] React Native or Flutter app
- [ ] Speaks to `jarvis serve` over TLS
- [ ] On-device wake word (Porcupine) → stream audio to server for STT
- [ ] Push notifications for proactive messages

## Phase 9 — Security Hardening

- [ ] Voice + face auth for sensitive tools (`requires_identity=True`)
- [ ] Prompt-injection defenses (retrieved content is isolated, labeled)
- [ ] Tool allow-lists per role (guest / user / admin)
- [ ] Signed + encrypted memory export/import

## Phase 10 — Self-Improvement (bounded)

- [ ] Feedback capture per turn (implicit signals + explicit "that was wrong")
- [ ] Mistake-pattern detector → suggests prompt / tool fixes
- [ ] ALL behavior changes require human approval in an "improvement PR"
- [ ] No unsupervised learning that modifies policies

## Phase 11+ — Beyond

The movie-JARVIS items that are genuinely speculative at current tech maturity:

- **World model / simulation-before-action**: research-grade; start with rule-based world state + causal graphs.
- **Robotics**: lives in a separate robot stack (ROS 2); Jarvis becomes its operator, not the controller.
- **Scientific discovery**: domain-specific tool integrations (Wolfram, SymPy, sim packages). Not general "invention."
- **Strategic long-term optimization**: constrained to well-scoped domains (calendar, finances, home energy), not open-ended life planning.
- **AGI plug-in slot**: our `LLMClient` abstraction already makes it trivial to swap brains. When a better model appears, replace one file.

---

## Explicit non-goals

- Not a replacement for human judgment on legal, medical, or financial decisions.
- Not an always-on microphone uploading raw audio anywhere — all STT/wake-word happens locally.
- Not a vehicle for bypassing 2FA, scraping credentials, or any defensive-security-violating behavior.
- Not marketed or shipped as "AGI." It is a coordination layer over current-gen models.
