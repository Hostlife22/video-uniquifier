"""Experimental local worker API for NestJS/BullMQ; no publishing endpoints."""

from __future__ import annotations

import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from video_uniquifier.core.reels.config import PackagingRules, ReelsRules
from video_uniquifier.core.reels.jobs import JobManager
from video_uniquifier.core.reels.runtime import ReelsError, confined_path
from video_uniquifier.web.middleware.upload_limit import ContentLengthLimitMiddleware

_ARTIFACTS = frozenset({"output.mp4", "preview.mp4", "safe-area.png", "scenes.json"})


def build_reels_app(
    root: Path, presets: dict[str, ReelsRules] | None = None, *,
    asset_root: Path | None = None, api_token: str | None = None,
    max_pending_jobs: int = 32,
) -> FastAPI:
    """Run one local API process. CPU admissions also protect independent CLI workers."""
    configured = presets or {"facebook_reels_drama_v1": ReelsRules()}
    if any(key != rules.preset_id for key, rules in configured.items()):
        raise ValueError("preset registry keys must match preset_id")
    manager = JobManager(root, configured, asset_root or Path.cwd(),
                         max_pending_jobs=max_pending_jobs)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        manager.close()

    app = FastAPI(title="Local Reels worker", version="1", lifespan=lifespan)
    app.state.reels_jobs = manager
    limit = max(r.worker.max_input_mb for r in configured.values()) * 1024 * 1024
    app.add_middleware(ContentLengthLimitMiddleware, max_bytes=limit + 1024 * 1024)

    @app.middleware("http")
    async def authenticate(request: Request, call_next: Any) -> Any:
        if api_token is not None and not secrets.compare_digest(
            request.headers.get("authorization", ""), f"Bearer {api_token}",
        ):
            return JSONResponse(status_code=401, content={"detail": "Worker token required."})
        return await call_next(request)

    @app.exception_handler(ReelsError)
    async def domain_error(_request: Request, error: ReelsError) -> JSONResponse:
        status = 429 if error.code == "queue_full" else 409
        return JSONResponse(status_code=status, content={"error": {
            "code": error.code, "message": str(error), "retryable": error.retryable,
        }})

    def known_job(identifier: str) -> dict[str, Any]:
        try:
            return manager.snapshot(identifier)
        except KeyError as exc:
            raise HTTPException(404, "Unknown job.") from exc

    @app.get("/api/video-presets")
    def presets_route() -> list[dict[str, Any]]:
        return [{"preset_id": key, "schema_version": rules.schema_version,
                 "effective_rules": rules.model_dump(mode="json")}
                for key, rules in configured.items()]

    @app.post("/api/video-jobs", status_code=202)
    async def create_job(
        file: Annotated[UploadFile, File()],
        preset_id: Annotated[str, Form()] = "facebook_reels_drama_v1",
        packaging: Annotated[str | None, Form()] = None,
    ) -> dict[str, Any]:
        if preset_id not in configured:
            raise HTTPException(422, "Unknown preset_id.")
        rules = configured[preset_id].model_copy(deep=True)
        if packaging is not None:
            try:
                rules.packaging = PackagingRules.model_validate(json.loads(packaging))
            except (ValueError, ValidationError) as exc:
                raise HTTPException(422, "Invalid packaging configuration.") from exc
        filename = file.filename or ""
        if Path(filename).name != filename or "\\" in filename or "\x00" in filename:
            raise HTTPException(422, "Upload filename must be a basename.")
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in rules.worker.allow_input_extensions:
            raise HTTPException(422, "Unsupported video extension.")
        identifier = uuid4().hex
        destination = manager.uploads / f"{identifier}.{suffix}"
        total = 0
        try:
            with destination.open("xb") as handle:
                while block := await file.read(1024 * 1024):
                    total += len(block)
                    if total > rules.worker.max_input_mb * 1024 * 1024:
                        raise HTTPException(413, "Uploaded file exceeds this preset's size limit.")
                    handle.write(block)
            if total == 0:
                raise HTTPException(422, "Empty input file.")
            manager.submit(destination, rules, job_id=identifier)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return manager.snapshot(identifier)

    @app.get("/api/video-jobs/{identifier}")
    def status_route(identifier: str) -> dict[str, Any]:
        return known_job(identifier)

    @app.post("/api/video-jobs/{identifier}/cancel")
    def cancel_route(identifier: str) -> dict[str, Any]:
        known_job(identifier)
        return manager.cancel(identifier)

    @app.post("/api/video-jobs/{identifier}/retry", status_code=202)
    def retry_route(identifier: str) -> dict[str, Any]:
        known_job(identifier)
        return manager.snapshot(manager.retry(identifier))

    @app.get("/api/video-jobs/{identifier}/report")
    def report_route(identifier: str) -> FileResponse:
        known_job(identifier)
        try:
            path = manager.report_path(identifier)
        except ReelsError as exc:
            if exc.code != "storage_path":
                raise
            raise HTTPException(404, "Report unavailable.") from exc
        if not path.is_file():
            raise HTTPException(404, "No report was written before the worker restarted.")
        return FileResponse(path, media_type="application/json", filename="report.json")

    @app.get("/api/video-jobs/{identifier}/files/{filename}")
    def artifact_route(identifier: str, filename: str) -> FileResponse:
        record = known_job(identifier)
        if record["status"] != "success" or filename not in _ARTIFACTS:
            raise HTTPException(404, "Artifact unavailable.")
        try:
            path = confined_path(manager.root, manager.root / "results" / identifier / filename)
        except ReelsError as exc:
            raise HTTPException(404, "Artifact unavailable.") from exc
        if not path.is_file():
            raise HTTPException(404, "Artifact unavailable.")
        return FileResponse(path, filename=filename)

    return app
