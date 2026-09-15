import os
import sys
import time
import threading
import webbrowser
import typer
import uvicorn

# Ensure repository root and core directory are in sys.path for CLI execution anywhere
current_file_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(os.path.dirname(current_file_dir))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
core_dir = os.path.dirname(current_file_dir)
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

app = typer.Typer(
    name="agentsentrix",
    help="AgentSentrix Platform CLI — Unified Security Gateway & Threat Command Center"
)

@app.command("up")
def up(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind server"),
    port: int = typer.Option(7777, "--port", "-p", help="Port number for AgentSentrix server"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Automatically open dashboard in web browser"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn hot-reload mode")
):
    """Start the AgentSentrix platform and serve the single-process 3D command dashboard."""
    url = f"http://{host}:{port}"
    typer.secho(f"\n[+] Starting AgentSentrix Platform Security Gateway at {url}", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"    * API Endpoints : {url}/health, {url}/events, {url}/graph")
    typer.secho(f"    * Dashboard UI  : {url}\n", fg=typer.colors.GREEN)

    if open_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    # Import app factory cleanly across installed package vs local dev path
    try:
        from agentsentrix.server.app import create_app
    except ModuleNotFoundError:
        from core.agentsentrix.server.app import create_app

    app_instance = create_app()

    try:
        uvicorn.run(app_instance, host=host, port=port, reload=reload)
    except (KeyboardInterrupt, SystemExit):
        typer.secho("\n[+] AgentSentrix Platform Security Gateway stopped cleanly.", fg=typer.colors.YELLOW)

@app.command("version")
def version():
    """Display AgentSentrix version information."""
    typer.echo("AgentSentrix v0.1.0")

@app.command("status")
def status():
    """Check health and status of AgentSentrix gateway."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:7777/health", timeout=2.0) as resp:
            typer.secho("AgentSentrix gateway is RUNNING at http://127.0.0.1:7777", fg=typer.colors.GREEN, bold=True)
    except Exception:
        typer.secho("AgentSentrix gateway is STOPPED or unreachable on port 7777", fg=typer.colors.YELLOW)

@app.command("record")
def record(
    output: str = typer.Option("data/seed/demo_session.jsonl", "--output", "-o", help="Target output .jsonl trace file"),
    delay_ms: float = typer.Option(800.0, "--delay-ms", help="Step delay in milliseconds")
):
    """Record a full live 4-agent simulation session into an offline-ready trace file (.jsonl)."""
    import asyncio
    import json
    try:
        from sim.runner import SimulationRunner
    except ModuleNotFoundError:
        typer.secho("Error importing SimulationRunner.", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.secho(f"\n[+] Recording live simulation trace into '{output}'...", fg=typer.colors.CYAN, bold=True)
    runner = SimulationRunner()
    res = asyncio.run(runner.run_scenario(step_delay_ms=delay_ms))

    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for evt in res.events:
            f.write(json.dumps(evt) + "\n")

    typer.secho(f"✓ Recorded {len(res.events)} telemetry events to '{output}'", fg=typer.colors.GREEN, bold=True)

@app.command("replay")
def replay(
    file: str = typer.Argument("data/seed/demo_session.jsonl", help="Path to recorded session trace .jsonl file"),
    speed: float = typer.Option(1.0, "--speed", "-s", help="Replay speed multiplier (e.g. 1.5)"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind server"),
    port: int = typer.Option(7777, "--port", "-p", help="Port number for server & dashboard"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Automatically open web browser")
):
    """Replay a recorded session trace through the live bus and 3D dashboard (works 100% offline)."""
    if not os.path.exists(file):
        typer.secho(f"Error: Replay trace file '{file}' not found.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    url = f"http://{host}:{port}"
    typer.secho(f"\n[+] Starting AgentSentrix Offline Replay Engine at {url}", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"    * Trace File    : {file}")
    typer.secho(f"    * Speed Factor  : x{speed}")
    typer.secho(f"    * Dashboard UI  : {url}\n", fg=typer.colors.GREEN)

    if open_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    try:
        from agentsentrix.server.app import create_app
    except ModuleNotFoundError:
        from core.agentsentrix.server.app import create_app

    app_instance = create_app(replay_file=file, speed=speed)

    try:
        uvicorn.run(app_instance, host=host, port=port)
    except (KeyboardInterrupt, SystemExit):
        typer.secho("\n[+] AgentSentrix Replay Engine stopped cleanly.", fg=typer.colors.YELLOW)

def main():
    app()

if __name__ == "__main__":
    main()
