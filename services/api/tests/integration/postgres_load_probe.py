"""Opt-in local ASGI/PostgreSQL read load; not deployed TLS/network capacity evidence."""

import hashlib
import json
import math
import platform
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.main import app
from fastapi.testclient import TestClient
from postgres_recovery import fingerprint
from sqlalchemy.orm import Session
from test_project_control_api import bootstrap_project
from test_queue_performance import seed_queue_workload


def exercise_queue_read_load(engine, tmp_path):
    with TestClient(app) as client:
        org, project, headers = bootstrap_project(client, "queue-load-probe")
        with Session(engine) as session:
            seed_queue_workload(session, uuid.UUID(org), uuid.UUID(project))
        before = fingerprint(engine)
        base = f"/api/v1/projects/{project}/decision-center"
        paths = (
            "/queue",
            "/review-queues?as_of=2026-10-26T12:00:00Z",
            "/exports/decision-queue.csv",
        )
        digests = {}
        for path in paths:
            response = client.get(base + path, headers=headers)
            assert response.status_code == 200, response.text
            digests[path] = hashlib.sha256(response.content).hexdigest()
            if path == "/queue":
                assert len(response.json()) == 50
                assert all(item["recommended_disposition"] is None for item in response.json())

        def read(index):
            path = paths[index % len(paths)]
            started = time.perf_counter()
            response = client.get(base + path, headers=headers)
            elapsed = time.perf_counter() - started
            assert response.status_code == 200, response.text
            assert hashlib.sha256(response.content).hexdigest() == digests[path]
            return path, elapsed

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(read, range(96)))
        elapsed = time.perf_counter() - started
        assert fingerprint(engine) == before
    latencies = {}
    for path in paths:
        values = sorted(duration for route, duration in results if route == path)
        latencies[path] = {
            "requests": len(values),
            "p50_seconds": values[math.ceil(len(values) * 0.5) - 1],
            "p95_seconds": values[math.ceil(len(values) * 0.95) - 1],
            "max_seconds": values[-1],
        }
    manifest = {
        "profile": "LOCAL-QUEUE-READ-1.0.0",
        "transport": "ASGI TestClient with real PostgreSQL",
        "python": platform.python_version(),
        "platform": platform.system(),
        "work_packages": 10,
        "decision_cases": 50,
        "workers": 4,
        "requests": 96,
        "elapsed_seconds": elapsed,
        "requests_per_second": len(results) / elapsed,
        "latencies": latencies,
        "payloads_identical": True,
        "database_unchanged": True,
        "local_regression_budgets": {"route_p95_seconds": 3, "total_seconds": 60},
    }
    (tmp_path / "queue-read-load.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    assert elapsed < 60, manifest
    assert all(item["p95_seconds"] < 3 for item in latencies.values()), manifest
