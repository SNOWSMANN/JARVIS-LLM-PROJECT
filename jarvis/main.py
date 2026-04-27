"""Main event loop — wake → listen → think → speak.

Usage:
    python -m jarvis                 # voice loop
    python -m jarvis text            # text REPL (no mic / speakers)
    python -m jarvis once "<text>"   # single turn, prints reply
    python -m jarvis serve           # run the FastAPI server
"""

from __future__ import annotations

import signal
import sys

import typer
from rich.console import Console
from rich.panel import Panel

from jarvis.agent import Agent
from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.observability import get_logger, setup_logging
from jarvis.tools.builtin import register_builtin_tools

app = typer.Typer(add_completion=False, no_args_is_help=False, invoke_without_command=True)
console = Console()
log = get_logger(__name__)


def _bootstrap() -> tuple[MemoryStore, Agent]:
    setup_logging()
    memory = MemoryStore()
    memory.start()
    register_builtin_tools(memory)
    agent = Agent(memory=memory)
    return memory, agent


@app.callback()
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        voice_loop()


@app.command()
def voice_loop() -> None:
    """Wake-word-driven voice loop. This is the main Jarvis experience."""
    memory, agent = _bootstrap()

    console.print(
        Panel.fit(
            f"[bold cyan]{settings.jarvis_name}[/bold cyan] is online.\n"
            f"Say [bold]'hey jarvis'[/bold] to wake me up.  Ctrl+C to exit.",
            border_style="cyan",
        )
    )

    from jarvis.voice import Speaker, SpeechRecognizer, WakeWordListener

    wake = WakeWordListener()
    stt = SpeechRecognizer()
    speaker = Speaker()

    def _shutdown(*_a) -> None:  # noqa: ANN002
        console.print("\n[dim]Shutting down.[/dim]")
        wake.stop()
        memory.end_conversation(agent.conversation_id)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    speaker.say(f"At your service, {settings.jarvis_user_name}.")

    for _ in wake.listen():
        console.print("[yellow]Wake word detected. Listening...[/yellow]")
        try:
            user_text = stt.record_and_transcribe()
        except Exception as e:  # noqa: BLE001
            log.error("STT failed: {}", e)
            speaker.say("I didn't catch that.")
            continue

        if not user_text:
            speaker.say("I didn't catch that.")
            continue

        console.print(f"[bold]You:[/bold] {user_text}")
        resp = agent.handle(user_text)
        console.print(f"[bold cyan]{settings.jarvis_name}:[/bold cyan] {resp.text}")

        if resp.text.strip():
            try:
                speaker.say(resp.text)
            except Exception as e:  # noqa: BLE001
                log.error("TTS failed: {}", e)


@app.command()
def text() -> None:
    """Text REPL for testing without mic/speakers."""
    memory, agent = _bootstrap()
    console.print(
        Panel.fit(
            f"[bold cyan]{settings.jarvis_name}[/bold cyan] text mode.  "
            "Type 'exit' to quit.",
            border_style="cyan",
        )
    )
    try:
        while True:
            user_text = console.input("[bold]You:[/bold] ").strip()
            if not user_text:
                continue
            if user_text.lower() in {"exit", "quit"}:
                break
            resp = agent.handle(user_text)
            console.print(f"[bold cyan]{settings.jarvis_name}:[/bold cyan] {resp.text}")
    finally:
        memory.end_conversation(agent.conversation_id)


@app.command()
def once(message: str) -> None:
    """Run a single turn and print the reply."""
    _memory, agent = _bootstrap()
    resp = agent.handle(message)
    console.print(resp.text)


@app.command()
def serve() -> None:
    """Run the FastAPI server."""
    import uvicorn

    setup_logging()
    memory = MemoryStore()
    memory.start()
    register_builtin_tools(memory)

    from jarvis.server import build_app

    application = build_app(memory=memory)
    uvicorn.run(
        application,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    app()
