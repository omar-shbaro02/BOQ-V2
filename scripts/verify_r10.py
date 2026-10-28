"""Collect current R10 engineering evidence without declaring human or pilot acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = (
    "Automated engineering evidence only. PASS is scoped to the named check. "
    "Local and synthetic checks do not establish deployed-provider acceptance, "
    "human usability, Phase 12 completion, Phase 13 entry or pilot authorization."
)
EXTERNAL = [
    ("live-identity", "Actual identity provider, provisioning and deployed TLS/forwarding", "20"),
    (
        "live-storage-scanner",
        "Actual S3 IAM/retention and maintained private malware scanner",
        "20",
    ),
    ("staging-load-soak", "Representative deployed load/soak with agreed objectives", "22"),
    ("staging-disaster-recovery", "Deployed disaster recovery with accountable RPO/RTO", "21"),
    ("operator-sessions", "Representative PM/planner sessions including BS-001–BS-010", "15"),
    ("manual-accessibility", "Human keyboard and assistive-technology acceptance", "22"),
    (
        "pilot-approval",
        "Release finding adjudication and explicit accountable pilot approval",
        "19",
    ),
]


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def redact(text: str, environment: dict[str, str]) -> str:
    for key, value in environment.items():
        if len(value) >= 8 and re.search(
            r"secret|password|token|api_key|encryption_keys", key, re.I
        ):
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)\S+", r"\1[REDACTED]", text)
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)


def stop_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=15,
            )
    else:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=3)
        # The parent may have exited while a grandchild still owns inherited pipes.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=15)


def process_options(environment: dict[str, str]) -> dict:
    options = {"cwd": ROOT, "env": environment}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    return options


def junit_counts(path: Path) -> dict:
    cases = ET.parse(path).getroot().findall(".//testcase")
    if not cases:
        raise ValueError("No test cases were recorded")
    skipped = [
        f"{case.get('classname')}.{case.get('name')}"
        for case in cases
        if case.find("skipped") is not None
    ]
    return {
        "tests": len(cases),
        "skipped": skipped,
        "failures": sum(
            case.find("failure") is not None or case.find("error") is not None for case in cases
        ),
    }


def playwright_counts(path: Path) -> dict:
    stats = json.loads(path.read_text(encoding="utf-8"))["stats"]
    if stats.get("expected", 0) < 1:
        raise ValueError("No browser tests passed")
    if any(stats.get(key, 0) for key in ("unexpected", "flaky", "skipped")):
        raise ValueError(f"Browser checks failed, retried or skipped: {stats}")
    return stats


def source_state() -> dict:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT)

    digest = hashlib.sha256()
    files = sorted(
        set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0"))
        - {b""}
    )
    for name in files:
        path = ROOT / os.fsdecode(name)
        digest.update(name + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b"DELETED")
    return {
        "captured_at": timestamp(),
        "commit": git("rev-parse", "HEAD").decode().strip(),
        "dirty": bool(git("status", "--porcelain")),
        "candidate_files": len(files),
        "candidate_tree_sha256": digest.hexdigest(),
    }


class Runner:
    def __init__(self, directory: Path, environment: dict[str, str]):
        self.directory, self.environment = directory, environment
        self.results: list[dict] = []

    def missing(
        self, identifier: str, title: str, reason: str, selected: bool = True, scope: str = "local"
    ) -> None:
        self.results.append(
            {
                "id": identifier,
                "title": title,
                "status": "NOT RUN",
                "reason": reason,
                "selected": selected,
                "scope": scope,
            }
        )
        print(f"NOT RUN  {identifier}: {reason}", flush=True)

    def run(
        self,
        identifier: str,
        title: str,
        command: list[str],
        *,
        timeout: int = 600,
        environment: dict[str, str] | None = None,
        validator=None,
        scope="local",
    ) -> dict:
        started = time.monotonic()
        env = {**self.environment, **(environment or {})}
        result = {
            "id": identifier,
            "title": title,
            "selected": True,
            "scope": scope,
            "started_at": timestamp(),
            "command": command,
            "status": "FAIL",
        }
        print(f"RUN      {identifier}", flush=True)
        output, process = "", None
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **process_options(env)
            )
            try:
                raw, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                stop_tree(process)
                raw, _ = process.communicate(timeout=15)
                raise TimeoutError(
                    f"Exceeded {timeout}s; terminated owned process tree: "
                    + raw.decode(errors="replace")[-2000:]
                ) from None
            output = raw.decode(errors="replace")
            result["exit_code"] = process.returncode
            if process.returncode:
                result["reason"] = f"Command exited {process.returncode}; inspect log"
            else:
                result["details"] = validator() if validator else {}
                result["status"] = "PASS"
        except (OSError, ValueError, KeyError, ET.ParseError, subprocess.SubprocessError) as error:
            result["reason"] = redact(str(error), env)
        except KeyboardInterrupt:
            if process is not None:
                stop_tree(process)
            result["reason"] = "Interrupted; partial evidence is not a pass"
            raise
        finally:
            result["duration_seconds"] = round(time.monotonic() - started, 3)
            result["log"] = f"{identifier}.log"
            (self.directory / result["log"]).write_text(redact(output, env), encoding="utf-8")
            self.results.append(result)
            print(f"{result['status']:<8} {identifier}", flush=True)
        return result


def pytest_validation(path: Path, *, optional_skips: bool = False) -> dict:
    counts = junit_counts(path)
    unexpected_skips = [
        name
        for name in counts["skipped"]
        if not optional_skips
        or not any(
            f"{module}." in name
            for module in ("test_live_adapters", "test_project_context_postgres")
        )
    ]
    if counts["failures"] or unexpected_skips or counts["tests"] == len(counts["skipped"]):
        raise ValueError(f"Failed or skipped required tests: {counts}")
    return counts


def report(directory: Path, results: list[dict], source: dict) -> dict:
    selected = [item for item in results if item["selected"]]
    execution = (
        "FAIL"
        if any(item["status"] == "FAIL" for item in selected)
        else "NOT RUN"
        if not selected or any(item["status"] == "NOT RUN" for item in selected)
        else "PASS"
    )
    data = {
        "schema_version": "R10-VERIFICATION-1.0.0",
        "generated_at": timestamp(),
        "notice": NOTICE,
        "source": source,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "selected_checks_status": execution,
        "r10_status": "FAIL" if execution == "FAIL" else "NOT RUN",
        "checks": results,
    }
    data["evidence_files"] = [
        {
            "path": path.relative_to(directory).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        and path.name not in {"report.json", "report.md"}
        and "postgres/data" not in path.relative_to(directory).as_posix()
    ]
    (directory / "report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    lines = [
        "# R10 verification evidence",
        "",
        NOTICE,
        "",
        f"Selected automated checks: **{execution}**. R10 acceptance: **{data['r10_status']}**.",
        "",
        f"Commit: `{source.get('commit', 'unavailable')}`; "
        f"working tree SHA-256: `{source.get('candidate_tree_sha256', 'unavailable')}`.",
        "",
        "| Check | Scope | Result | Evidence / reason |",
        "| --- | --- | --- | --- |",
    ]
    for item in results:
        detail = f"[log]({item['log']})" if "log" in item else ""
        detail += " " + item.get("reason", "")
        lines.append(
            f"| {item['title']} | {item['scope']} | **{item['status']}** | "
            + detail.replace("|", "\\|").replace("\n", " ")
            + " |"
        )
    lines += [
        "",
        "JSON includes test counts/skips, commands, timings and artifact hashes.",
        "Human and deployment requirements remain NOT RUN; external attestations are not "
        "accepted automatically by this local runner.",
        "",
    ]
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return data


def free_ports(ports: list[int]) -> bool:
    for port in ports:
        with socket.socket() as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                return False
    return True


def result_exit_code(data: dict, require_complete: bool = False) -> int:
    status = data["r10_status" if require_complete else "selected_checks_status"]
    return {"PASS": 0, "FAIL": 1, "NOT RUN": 2}[status]


def browser_check(runner: Runner, python: str, node: str, *, oidc: bool = False) -> None:
    identifier = "https-identity" if oidc else "browser-accessibility"
    title = (
        "Synthetic HTTPS identity and proxy"
        if oidc
        else "Browser journeys and automated accessibility"
    )
    ports = [8012, 3012, 3013] if oidc else [8011, 3011]
    if not free_ports(ports):
        runner.missing(identifier, title, f"Required isolated ports {ports} are occupied")
        return
    if not oidc and not shutil.which("pdftotext", path=runner.environment.get("PATH")):
        runner.missing(
            identifier, title, "Poppler pdftotext is required for the PDF browser journey"
        )
        return
    cli = ROOT / "node_modules/@playwright/test/cli.js"
    if not cli.is_file():
        runner.missing(identifier, title, "Install repository Node dependencies first")
        return
    config = runner.directory / f"{identifier}.config.ts"
    output = runner.directory / f"{identifier}.json"
    tests = ROOT / ("tests/browser-oidc" if oidc else "tests/browser")
    config.write_text(
        f'import base from "../../playwright{".oidc" if oidc else ""}.config";\n'
        + "export default { ...base, webServer: [], "
        + f"testDir: {json.dumps(str(tests))}, "
        + f"outputDir: {json.dumps(str(runner.directory / (identifier + '-results')))}, "
        + 'reporter: [["list"], ["json", { outputFile: '
        + json.dumps(str(output))
        + " }]] };\n",
        encoding="utf-8",
    )
    commands = (
        [[python, "scripts/e2e_oidc.py"]]
        if oidc
        else [
            [python, "scripts/e2e_api.py"],
            [
                node,
                "apps/web/node_modules/next/dist/bin/next",
                "dev",
                "apps/web",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3011",
            ],
        ]
    )
    env = {**runner.environment, "NEXT_PUBLIC_VAI_API_URL": "http://127.0.0.1:8011"}
    children, handles = [], []
    try:
        for index, command in enumerate(commands):
            handle = (runner.directory / f"{identifier}-server-{index}.log").open("wb")
            handles.append(handle)
            children.append(
                subprocess.Popen(
                    command, stdout=handle, stderr=subprocess.STDOUT, **process_options(env)
                )
            )
        deadline = time.monotonic() + 180
        urls = (
            ["https://127.0.0.1:3012"]
            if oidc
            else ["http://127.0.0.1:8011/health", "http://127.0.0.1:3011/bootstrap"]
        )
        ready = False
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                break
            try:
                for url in urls:
                    with urllib.request.urlopen(
                        url, timeout=2, context=ssl._create_unverified_context() if oidc else None
                    ) as response:
                        if response.status != 200:
                            raise OSError("Isolated service is not ready")
                ready = True
                if ready:
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.5)
        if not ready:
            runner.results.append(
                {
                    "id": identifier,
                    "title": title,
                    "status": "FAIL",
                    "scope": "local",
                    "selected": True,
                    "reason": "Isolated server failed to become ready; inspect server logs",
                }
            )
        else:
            runner.run(
                identifier,
                title,
                [node, str(cli), "test", f"--config={config}"],
                validator=lambda: playwright_counts(output),
                timeout=900,
            )
    finally:
        for child in reversed(children):
            try:
                stop_tree(child)
            except (OSError, subprocess.SubprocessError) as error:
                runner.results.append(
                    {
                        "id": f"{identifier}-cleanup",
                        "title": title + " cleanup",
                        "status": "FAIL",
                        "scope": "local",
                        "selected": True,
                        "reason": redact(str(error), env),
                    }
                )
        for handle in handles:
            handle.close()
        for index in range(len(handles)):
            log = runner.directory / f"{identifier}-server-{index}.log"
            log.write_text(
                redact(log.read_text(encoding="utf-8", errors="replace"), env), encoding="utf-8"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--skip-postgres", action="store_true")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Return nonzero while any overall R10 acceptance gate remains open",
    )
    parser.add_argument(
        "--postgres-bin",
        default=(
            "dist/portable-smoke-final/vai-local-evaluation-windows-portable/runtime/postgresql/bin"
        ),
    )
    parser.add_argument(
        "--online-audits", action="store_true", help="Query dependency advisory services"
    )
    parser.add_argument(
        "--live-ai", action="store_true", help="Opt into the potentially paid live AI smoke test"
    )
    args = parser.parse_args(argv)
    directory = (
        ROOT
        / ".test-tmp"
        / ("r10-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    )
    directory.mkdir(parents=True)
    environment = {
        **os.environ,
        "VAI_OPENAI_API_KEY": "",
        "VAI_OPENAI_AGENTS_ENABLED": "false",
        "VAI_TEST_POSTGRES_URL": "",
        "VAI_TEST_POSTGRES_BIN": "",
        "VAI_TEST_LOAD_PROFILE": "0",
    }
    poppler = (
        ROOT
        / "dist/portable-smoke-final/vai-local-evaluation-windows-portable"
        / "runtime/poppler/Library/bin"
    )
    if (poppler / "pdftotext.exe").is_file():
        environment["PATH"] = str(poppler) + os.pathsep + environment.get("PATH", "")
    if os.name == "nt" and not environment.get("PLAYWRIGHT_CHANNEL"):
        chrome = (
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
            / "Google/Chrome/Application/chrome.exe"
        )
        if chrome.is_file():
            environment["PLAYWRIGHT_CHANNEL"] = "chrome"
    runner = Runner(directory, environment)
    python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    node, npm = shutil.which("node"), shutil.which("npm.cmd" if os.name == "nt" else "npm")
    source = source_state()
    try:
        if not python.is_file():
            runner.missing(
                "toolchain", "Repository Python toolchain", "Run repository bootstrap first"
            )
        else:
            py = str(python)
            runner.run(
                "generated", "Generated contracts", [py, "scripts/generate_contracts.py", "--check"]
            )
            runner.run("secrets", "Repository credential scan", [py, "scripts/check_secrets.py"])
            junit = directory / "api-tests.xml"
            runner.run(
                "api-regressions",
                "API, governance, connected scenario and adapter regressions",
                [
                    py,
                    "-m",
                    "pytest",
                    "--basetemp",
                    str(directory / "pytest"),
                    "-o",
                    f"cache_dir={directory / 'cache'}",
                    f"--junitxml={junit}",
                    "--tb=short",
                ],
                validator=lambda: pytest_validation(junit, optional_skips=True),
            )
            for identifier, command in (
                ("python-lint", [py, "-m", "ruff", "check", "services/api", "scripts"]),
                (
                    "python-format",
                    [py, "-m", "ruff", "format", "--check", "services/api", "scripts"],
                ),
                ("python-compile", [py, "-m", "compileall", "-q", "services/api/app", "scripts"]),
            ):
                runner.run(identifier, identifier.replace("-", " ").title(), command)
            for identifier, script in (("web-lint", "lint:web"), ("web-types", "typecheck:web")):
                if npm:
                    runner.run(
                        identifier, identifier.replace("-", " ").title(), [npm, "run", script]
                    )
                else:
                    runner.missing(identifier, script, "npm is unavailable")
            for oidc in (False, True):
                if args.skip_browser or not node:
                    runner.missing(
                        "https-identity" if oidc else "browser-accessibility",
                        "Synthetic HTTPS identity" if oidc else "Browser and accessibility",
                        "Disabled by --skip-browser"
                        if args.skip_browser
                        else "Node is unavailable",
                        selected=not args.skip_browser,
                    )
                else:
                    browser_check(runner, py, node, oidc=oidc)
            # Restore the normal build after the synthetic OIDC harness's special proxy build.
            if npm:
                runner.run("web-build", "Production web build", [npm, "run", "build:web"])
            else:
                runner.missing("web-build", "Production web build", "npm is unavailable")
            pg = ROOT / args.postgres_bin
            if args.skip_postgres or os.name != "nt" or not (pg / "pg_ctl.exe").is_file():
                runner.missing(
                    "postgres",
                    "Migrated PostgreSQL, races, recovery and local read load",
                    "Disabled by --skip-postgres"
                    if args.skip_postgres
                    else "Requires Windows portable PostgreSQL; use documents 21–22 on other hosts",
                    selected=not args.skip_postgres,
                )
            elif not free_ports([55441]):
                runner.missing(
                    "postgres", "Isolated PostgreSQL rehearsal", "Port 55441 is occupied"
                )
            else:

                def validate_pg():
                    counts = pytest_validation(directory / "postgres/pytest.xml")
                    for name in (
                        "connected-manifest.json",
                        "recovery-manifest.json",
                        "queue-read-load.json",
                    ):
                        if not list((directory / "postgres/pytest").rglob(name)):
                            raise ValueError(f"Required PostgreSQL evidence missing: {name}")
                    return counts

                try:
                    runner.run(
                        "postgres",
                        "Migrated PostgreSQL, races, recovery and local read load",
                        [
                            "powershell.exe",
                            "-NoProfile",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                            "scripts/rehearse_remediation.ps1",
                            "-PostgresBin",
                            str(pg),
                            "-EvidenceDirectory",
                            str(directory / "postgres"),
                            "-DowngradeTarget",
                            "0031_audit_append_only",
                            "-RunLoadProbe",
                        ],
                        validator=validate_pg,
                        timeout=600,
                    )
                finally:
                    # A forced timeout cannot rely on PowerShell's finally to stop detached PG.
                    cluster = directory / "postgres/data"
                    if (cluster / "postmaster.pid").is_file():
                        runner.run(
                            "postgres-cleanup",
                            "Stop owned temporary PostgreSQL cluster",
                            [
                                str(pg / "pg_ctl.exe"),
                                "-D",
                                str(cluster),
                                "stop",
                                "-m",
                                "fast",
                                "-w",
                            ],
                            timeout=30,
                        )
            for identifier, title, command in (
                (
                    "npm-audit",
                    "Node dependency advisory audit",
                    [npm, "audit", "--audit-level=high"],
                ),
                (
                    "python-audit",
                    "Python dependency advisory audit",
                    [
                        py,
                        "-m",
                        "pip_audit",
                        "-r",
                        "services/api/requirements.lock",
                        "--no-deps",
                        "--disable-pip",
                    ],
                ),
            ):
                available = (
                    npm
                    if identifier == "npm-audit"
                    else (
                        args.online_audits
                        and subprocess.run(
                            [
                                py,
                                "-c",
                                "import importlib.util; "
                                "found = importlib.util.find_spec('pip_audit'); "
                                "raise SystemExit(0 if found else 1)",
                            ],
                            capture_output=True,
                            check=False,
                            timeout=10,
                        ).returncode
                        == 0
                    )
                )
                if args.online_audits and available:
                    runner.run(identifier, title, command, scope="online")
                else:
                    runner.missing(
                        identifier,
                        title,
                        "Requires --online-audits and installed audit tool",
                        selected=args.online_audits,
                        scope="online",
                    )
            if args.live_ai and os.environ.get("VAI_OPENAI_API_KEY"):
                live_xml = directory / "live-ai.xml"
                runner.run(
                    "live-ai",
                    "Live AI boundary smoke test",
                    [
                        py,
                        "-m",
                        "pytest",
                        "services/api/tests/test_live_adapters.py",
                        "--live-adapters",
                        f"--junitxml={live_xml}",
                    ],
                    environment={"VAI_OPENAI_API_KEY": os.environ["VAI_OPENAI_API_KEY"]},
                    validator=lambda: pytest_validation(live_xml),
                    scope="online",
                )
            else:
                runner.missing(
                    "live-ai",
                    "Live AI boundary smoke test",
                    "Requires explicit --live-ai and VAI_OPENAI_API_KEY; may incur charges",
                    selected=args.live_ai,
                    scope="online",
                )
    except (KeyboardInterrupt, OSError, ValueError, subprocess.SubprocessError) as error:
        runner.results.append(
            {
                "id": "runner",
                "title": "Runner completion",
                "status": "FAIL",
                "selected": True,
                "scope": "local",
                "reason": redact(str(error), environment),
            }
        )
    finally:
        for identifier, title, document in EXTERNAL:
            runner.missing(
                identifier,
                title,
                f"Requires accountable external evidence; see document {document}",
                selected=False,
                scope="human"
                if identifier in {"operator-sessions", "manual-accessibility", "pilot-approval"}
                else "staging",
            )
        data = report(directory, runner.results, source)
        print(f"Evidence report: {directory / 'report.md'}", flush=True)
        print(
            f"Selected checks: {data['selected_checks_status']}; R10: {data['r10_status']}",
            flush=True,
        )
    return result_exit_code(data, args.require_complete)


if __name__ == "__main__":
    raise SystemExit(main())
