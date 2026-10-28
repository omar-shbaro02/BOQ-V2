"""Reject high-confidence credential material in tracked and candidate repository files."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "OpenAI API key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})"),
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\r?\n"
        rb"[A-Za-z0-9+/=\r\n]{64,}-----END "
    ),
}


def inspect_content(path: str, content: bytes) -> list[str]:
    filename = Path(path).name
    if (
        filename in {"auth.json", "credentials.json"}
        or filename == ".env"
        or (filename.startswith(".env.") and filename != ".env.example")
    ):
        return [f"{path}: credential/configuration file is not a repository artifact"]
    findings = []
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            line = content.count(b"\n", 0, match.start()) + 1
            findings.append(f"{path}:{line}: {label} material")
    return findings


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    findings, count = [], 0
    for raw in sorted(set(result.stdout.split(b"\0"))):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        target = ROOT / relative
        if not target.is_file():
            continue
        findings.extend(inspect_content(relative, target.read_bytes()))
        count += 1
    if findings:
        print("Credential check failed (matched values are intentionally redacted):")
        print("\n".join(findings))
        return 1
    print(f"Credential check passed: {count} repository files; no high-confidence key patterns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
