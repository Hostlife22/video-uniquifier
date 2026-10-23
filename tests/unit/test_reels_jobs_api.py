from __future__ import annotations

import threading
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")
from fastapi.testclient import TestClient

from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.jobs import JobManager
from video_uniquifier.core.reels.runtime import ReelsError, atomic_json
from video_uniquifier.web.reels import build_reels_app


def wait_status(client, identifier, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/video-jobs/{identifier}")
        if response.json()["status"] in expected:
            return response.json()
        time.sleep(0.01)
    pytest.fail(f"job did not reach {expected}")


@pytest.fixture
def local_api(tmp_path, monkeypatch):
    ready = threading.Event()

    def fake_process(source, rules, root, *, job_id, asset_root, cancel_token, on_status):
        on_status("processing", 0.2)
        while not ready.wait(0.01):
            if cancel_token.is_cancelled():
                raise ReelsError("cancelled", "User cancelled task")
        if cancel_token.is_cancelled():
            raise ReelsError("cancelled", "User cancelled task")
        directory = root / "results" / job_id
        directory.mkdir(parents=True)
        (directory / "output.mp4").write_bytes(b"processed")
        atomic_json(directory / "report.json", {"job_id": job_id, "preset_id": rules.preset_id,
                                               "status": "success"})
        on_status("success", 1.0)
        return directory

    monkeypatch.setattr("video_uniquifier.core.reels.jobs.process_video", fake_process)
    rules = ReelsRules.model_validate({"worker": {"max_cpu_jobs": 1, "max_input_mb": 1}})
    app = build_reels_app(tmp_path / "jobs", {rules.preset_id: rules},
                          asset_root=tmp_path, api_token="test-token", max_pending_jobs=2)
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        yield client, app.state.reels_jobs, ready
        ready.set()


def upload(client, name="drama.mp4", **data):
    return client.post("/api/video-jobs", files={"file": (name, b"source")}, data=data)


def test_presets_upload_poll_report_and_allowlisted_downloads(local_api):
    client, manager, ready = local_api
    assert client.get("/api/video-presets").json()[0]["effective_rules"]["video"]["crf"] == 21
    response = upload(client)
    assert response.status_code == 202
    identifier = response.json()["job_id"]
    pending = wait_status(client, identifier, {"processing"})
    assert pending["output_url"] is None
    assert client.get(pending["report_url"]).status_code == 409
    ready.set()
    result = wait_status(client, identifier, {"success"})
    assert result["progress"] == 1
    assert client.get(result["output_url"]).content == b"processed"
    assert client.get(result["report_url"]).json()["job_id"] == identifier
    assert client.get(f"/api/video-jobs/{identifier}/files/encode.log").status_code == 404
    assert len(list(manager.uploads.iterdir())) == 1
    assert all(path.name != "drama.mp4" for path in manager.uploads.iterdir())


def test_queued_cancel_running_cancel_and_retry_preserve_failure_reasons(local_api):
    client, _manager, ready = local_api
    first = upload(client).json()["job_id"]
    wait_status(client, first, {"processing"})
    second = upload(client).json()["job_id"]
    assert upload(client).status_code == 429
    assert client.post(f"/api/video-jobs/{second}/cancel").json()["status"] == "cancelled"
    report = client.get(f"/api/video-jobs/{second}/report").json()
    assert report["error"]["code"] == "cancelled"
    client.post(f"/api/video-jobs/{first}/cancel")
    assert wait_status(client, first, {"cancelled"})["error"]["code"] == "cancelled"
    assert client.get(f"/api/video-jobs/{first}/files/output.mp4").status_code == 404
    retried = client.post(f"/api/video-jobs/{second}/retry")
    assert retried.status_code == 202
    third = retried.json()["job_id"]
    assert third != second
    ready.set()
    assert wait_status(client, third, {"success"})["progress"] == 1
    assert client.post(f"/api/video-jobs/{third}/retry").status_code == 409


@pytest.mark.parametrize("name, data", [
    ("../escape.mp4", {}), ("a\\escape.mp4", {}), ("movie.exe", {}),
    ("movie.mp4", {"preset_id": "unknown"}),
    ("movie.mp4", {"packaging": '{"enabled":true,"logo":{"source":"../secret.png"}}'}),
    ("movie.mp4", {"packaging": '{"ffmpeg":"arbitrary"}'}),
])
def test_api_rejects_invalid_presets_paths_and_commands(local_api, name, data):
    client, manager, _ready = local_api
    assert upload(client, name, **data).status_code == 422
    assert not list(manager.uploads.iterdir())


def test_auth_missing_job_oversized_and_empty_uploads(local_api):
    client, _manager, _ready = local_api
    assert client.get("/api/video-presets", headers={"Authorization": "wrong"}).status_code == 401
    assert client.get("/api/video-jobs/unknown").status_code == 404
    assert client.post("/api/video-jobs/unknown/cancel").status_code == 404
    assert client.post("/api/video-jobs", headers={"Content-Length": str(4 * 1024 * 1024)},
                       content=b"").status_code == 413
    assert client.post("/api/video-jobs", files={"file": ("empty.mp4", b"")}).status_code == 422
    assert client.post("/api/video-jobs", files={"file": ("big.mp4", b"x" * (1024 * 1024 + 1))}
                       ).status_code == 413


def test_manager_confines_paths_and_restores_interrupted_states(tmp_path):
    rules = ReelsRules()
    root = tmp_path / "jobs"
    root.mkdir()
    identifier = "a" * 32
    atomic_json(root / "jobs.json", {"jobs": [{"job_id": identifier, "status": "processing",
                                              "updated_at": 1}]})
    manager = JobManager(root, {rules.preset_id: rules}, tmp_path)
    try:
        record = manager.snapshot(identifier)
        assert record["status"] == "failed"
        assert record["error"]["code"] == "worker_restarted"
        with pytest.raises(ReelsError, match="Upload"):
            manager.retry(identifier)
        with pytest.raises(ReelsError, match="upload root"):
            manager.submit(tmp_path / "outside.mp4", rules)
    finally:
        manager.close()


def test_presets_have_consistent_ids(tmp_path):
    with pytest.raises(ValueError, match="preset_id"):
        build_reels_app(tmp_path, {"wrong": ReelsRules()})
