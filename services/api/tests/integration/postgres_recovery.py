"""Logical recovery evidence for the disposable migration cluster and synthetic artifacts."""

import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from app.database import get_db
from app.main import app
from app.storage import LocalEvidenceStore, get_evidence_store
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


def fingerprint(engine, exclude_audit_id=None):
    tables = {}
    with engine.connect() as connection:
        for table in sorted(inspect(connection).get_table_names(schema="public")):
            quoted = engine.dialect.identifier_preparer.quote(table)
            digest, count = hashlib.sha256(), 0
            audit_filter = (
                " WHERE t.event_id != :exclude"
                if table == "audit_event" and exclude_audit_id
                else ""
            )
            for row in connection.execute(
                text(f"SELECT to_jsonb(t)::text FROM public.{quoted} t{audit_filter} ORDER BY 1"),
                {"exclude": exclude_audit_id} if audit_filter else {},
            ).scalars():
                digest.update(row.encode("utf-8") + b"\n")
                count += 1
            tables[table] = {"rows": count, "sha256": digest.hexdigest()}
        indexes = (
            connection.execute(
                text("SELECT indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexdef")
            )
            .scalars()
            .all()
        )
        triggers = connection.execute(
            text(
                "SELECT pg_get_triggerdef(t.oid), pg_get_functiondef(t.tgfoid) "
                "FROM pg_trigger t JOIN pg_class c ON t.tgrelid=c.oid "
                "JOIN pg_namespace n ON c.relnamespace=n.oid "
                "WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1"
            )
        ).all()
    return {"tables": tables, "indexes": indexes, "triggers": [list(row) for row in triggers]}


def exercise_logical_recovery(engine, tmp_path, deck_base, deck_headers, deck_id):
    # Explicitly reject accidental use against a developer or production database.
    url = engine.url
    assert url.host == "127.0.0.1" and url.database == "vai_remediation"
    assert url.password is None
    runtime = Path(os.environ["VAI_TEST_POSTGRES_BIN"])
    suffix = ".exe" if os.name == "nt" else ""
    restored_name = "vai_restore_" + uuid.uuid4().hex
    restored_url = url.set(database=restored_name)
    dump_path = tmp_path / "synthetic-recovery.dump"
    backup = LocalEvidenceStore(tmp_path / "backup-objects")
    restored_store = LocalEvidenceStore(tmp_path / "restored-objects")
    source_store = LocalEvidenceStore(tmp_path)
    before = fingerprint(engine)
    assert before["tables"]["audit_event"]["rows"] > 0
    with engine.connect() as connection:
        original_audit_ids = set(
            connection.execute(text("SELECT event_id FROM audit_event")).scalars()
        )
        objects = connection.execute(
            text(
                "SELECT storage_key, sha256 FROM evidence_artifact "
                "UNION ALL SELECT storage_key, content_hash FROM presentation_artifact"
            )
        ).all()
    assert len(objects) >= 2
    for key, digest in objects:
        content = source_store.get(key)
        assert hashlib.sha256(content).hexdigest() == digest
        backup.put(key, content)
    started = time.perf_counter()

    def run_tool(name, arguments):
        result = subprocess.run(
            [str(runtime / (name + suffix)), *arguments],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    run_tool(
        "pg_dump",
        [
            "--format=custom",
            "--file",
            str(dump_path),
            "--dbname",
            url.set(drivername="postgresql").render_as_string(),
        ],
    )
    backup_seconds = time.perf_counter() - started
    restored = None
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f'CREATE DATABASE "{restored_name}"'))
    previous_db = app.dependency_overrides.get(get_db)
    previous_store = app.dependency_overrides.get(get_evidence_store)
    try:
        started = time.perf_counter()
        run_tool(
            "pg_restore",
            [
                "--exit-on-error",
                "--no-owner",
                "--dbname",
                restored_url.set(drivername="postgresql").render_as_string(),
                str(dump_path),
            ],
        )
        restored = create_engine(restored_url)
        assert fingerprint(restored) == before

        def restored_db():
            with Session(restored) as session:
                yield session

        app.dependency_overrides[get_db] = restored_db
        app.dependency_overrides[get_evidence_store] = lambda: restored_store
        content_url = f"{deck_base}/presentations/{deck_id}/content"
        with TestClient(app) as client:
            # Database restoration alone cannot make missing or damaged bytes valid.
            assert client.get(content_url, headers=deck_headers).status_code == 503
            for key, digest in objects:
                content = backup.get(key)
                assert hashlib.sha256(content).hexdigest() == digest
                restored_store.put(key, content)
            with restored.connect() as connection:
                deck_key = connection.scalar(
                    text("SELECT storage_key FROM presentation_artifact WHERE id=:id"),
                    {"id": uuid.UUID(deck_id)},
                )
            exact_content = restored_store.get(deck_key)
            restored_store.put(deck_key, exact_content + b"damaged")
            assert client.get(content_url, headers=deck_headers).status_code == 409
            restored_store.put(deck_key, exact_content)
            response = client.get(content_url, headers=deck_headers)
            assert response.status_code == 200, response.text
            assert response.content == exact_content
            assert (
                client.get(
                    content_url,
                    headers={
                        **deck_headers,
                        "X-VAI-Organization-ID": str(uuid.uuid4()),
                    },
                ).status_code
                == 403
            )
        for table, column in (
            ("audit_event", "event_id"),
            ("project_context_record", "id"),
            ("presentation_artifact", "id"),
        ):
            commands = [f"UPDATE {table} SET {column}={column}", f"DELETE FROM {table}"]
            if table == "audit_event":
                commands.append("TRUNCATE audit_event")
            for command in commands:
                for protected_engine in (engine, restored):
                    with protected_engine.connect() as connection:
                        with pytest.raises(DBAPIError, match="append.only|immutable"):
                            connection.execute(text(command))
                        connection.rollback()
        with restored.connect() as connection:
            added_audits = [
                row
                for row in connection.execute(
                    text("SELECT event_id, action, object_id, actor_id FROM audit_event")
                ).mappings()
                if row["event_id"] not in original_audit_ids
            ]
        assert len(added_audits) == 1
        access_audit = added_audits[0]
        assert access_audit["action"] == "PRESENTATION_REVIEW_DOWNLOAD"
        assert access_audit["object_id"] == deck_id
        assert access_audit["actor_id"] == deck_headers["X-VAI-Actor-ID"]
        assert fingerprint(restored, exclude_audit_id=access_audit["event_id"]) == before
        assert fingerprint(engine) == before
        manifest = {
            "kind": "isolated-logical-recovery",
            "database": before,
            "objects": [{"storage_key": key, "sha256": digest} for key, digest in objects],
            "dump_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
            "backup_seconds": backup_seconds,
            "restore_and_verification_seconds": time.perf_counter() - started,
            "missing_content_denied": True,
            "tampered_content_denied": True,
            "foreign_tenant_denied": True,
            "immutable_guards_preserved": True,
            "recovery_access_audit_event_id": str(access_audit["event_id"]),
        }
        (tmp_path / "recovery-manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    finally:
        for dependency, previous in ((get_db, previous_db), (get_evidence_store, previous_store)):
            if previous is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = previous
        if restored is not None:
            restored.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text(f'DROP DATABASE "{restored_name}" WITH (FORCE)'))
