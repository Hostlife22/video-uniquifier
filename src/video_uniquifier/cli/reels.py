"""Local Reels delivery CLI, deliberately separate from the stable video-uniq CLI."""

from __future__ import annotations

import json
import os
import signal
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
import yaml

from video_uniquifier.core.reels.config import ReelsRules, load_rules
from video_uniquifier.core.reels.native import default_profile_path, validate_native_profile
from video_uniquifier.core.reels.processor import inspect_source, prepare_plan, process_video
from video_uniquifier.core.reels.runtime import ReelsError
from video_uniquifier.core.runner import CancelToken

app = typer.Typer(help="Local Reels delivery for owned/licensed video. No publishing or AI.")


@app.command("schema")
def schema_command() -> None:
    """Print the independent business JSON Schema for editors and API clients."""
    typer.echo(json.dumps(ReelsRules.model_json_schema(), ensure_ascii=False, indent=2))


def _rules(path: Path | None) -> ReelsRules:
    return load_rules(path) if path else ReelsRules()


def _fail(error: Exception) -> None:
    code = error.code if isinstance(error, ReelsError) else "invalid_configuration"
    typer.echo(json.dumps({"status": "failed", "error": {"code": code, "message": str(error)}},
                          ensure_ascii=False), err=True)
    raise typer.Exit(130 if code == "cancelled" else 2)


@app.command("validate")
def validate_command(
    rules: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    profile: Annotated[Path | None, typer.Option("--profile")] = None,
) -> None:
    """Validate the business YAML and native transform parameter schemas."""
    try:
        business = load_rules(rules)
        native = validate_native_profile(profile or default_profile_path())
        typer.echo(json.dumps({"status": "valid", "native_profile": native.name,
                              "effective_rules": business.model_dump(mode="json")},
                             ensure_ascii=False, indent=2))
    except (OSError, ValueError, yaml.YAMLError, ReelsError) as error:
        _fail(error)


@app.command("preflight")
def preflight_command(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    rules: Annotated[Path | None, typer.Option("--rules")] = None,
    profile: Annotated[Path | None, typer.Option("--profile")] = None,
) -> None:
    """Check actual input and the derived native plan without encoding."""
    try:
        business = _rules(rules)
        base = validate_native_profile(profile or default_profile_path())
        with tempfile.TemporaryDirectory(prefix="reels_preflight_") as folder:
            plan, findings = prepare_plan(inspect_source(source, business), business,
                                          base, Path(folder))
        typer.echo(json.dumps({"status": "passed", "native_profile": plan.profile.model_dump(),
                              "findings": findings}, ensure_ascii=False, indent=2))
    except Exception as error:
        _fail(error)


@app.command("run")
def run_command(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    root: Annotated[Path, typer.Option("--root")] = Path("reels-jobs"),
    rules: Annotated[Path | None, typer.Option("--rules")] = None,
    profile: Annotated[Path | None, typer.Option("--profile")] = None,
    asset_root: Annotated[Path | None, typer.Option("--asset-root")] = None,
    job_id: Annotated[str | None, typer.Option("--job-id")] = None,
    json_events: Annotated[bool, typer.Option("--json-events")] = False,
) -> None:
    """Process one file. SIGINT/SIGTERM cooperatively cancel all child processes."""
    token = CancelToken()
    previous = {sig: signal.signal(sig, lambda _sig, _frame: token.cancel())
                for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        business = _rules(rules)
        job_id = job_id or uuid4().hex

        def notify(status: str, progress: float) -> None:
            if json_events:
                typer.echo(json.dumps({"job_id": job_id, "status": status,
                                       "progress": progress}))

        result = process_video(source, business, root, job_id=job_id,
                               asset_root=asset_root or (rules.parent if rules else Path.cwd()),
                               profile_path=profile, cancel_token=token, on_status=notify)
        typer.echo(json.dumps({"job_id": result.name, "status": "success",
                              "result_directory": str(result.resolve())}))
    except Exception as error:
        _fail(error)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@app.command("serve")
def serve_command(
    root: Annotated[Path, typer.Option("--root")] = Path("reels-jobs"),
    rules: Annotated[Path | None, typer.Option("--rules")] = None,
    asset_root: Annotated[Path | None, typer.Option("--asset-root")] = None,
    port: Annotated[int, typer.Option("--port", min=1024, max=65535)] = 8765,
) -> None:
    """Serve the internal worker API on loopback; NestJS owns the public API/queue."""
    try:
        import uvicorn

        from video_uniquifier.web.reels import build_reels_app
        business = _rules(rules)
        application = build_reels_app(root, {business.preset_id: business},
                                      asset_root=asset_root or (
                                          rules.parent if rules else Path.cwd()),
                                      api_token=os.environ.get("VIDEO_REELS_API_TOKEN"))
        uvicorn.run(application, host="127.0.0.1", port=port, workers=1)
    except ImportError as error:
        _fail(ValueError(f"Install the [web,scene] extras: {error}"))
    except (OSError, ValueError, yaml.YAMLError, ReelsError) as error:
        _fail(error)


if __name__ == "__main__":
    app()
