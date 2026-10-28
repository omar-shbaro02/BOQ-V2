import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_secrets", Path(__file__).resolve().parents[3] / "scripts/check_secrets.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


@pytest.mark.parametrize(
    "content",
    [
        b"AKIA" + b"A" * 16,
        b"sk-proj-" + b"x" * 50,
        b"ghp_" + b"A" * 36,
        b"-----BEGIN PRIVATE KEY-----\n" + b"A" * 80 + b"\n-----END PRIVATE KEY-----",
    ],
)
def test_credential_material_is_detected_without_echoing_values(content):
    findings = CHECKER.inspect_content("settings.txt", b"before\n" + content)
    assert findings and "settings.txt:2:" in findings[0]
    assert content.decode() not in "\n".join(findings)


def test_sensitive_files_are_denied_and_empty_examples_are_allowed():
    for name in (".env", ".env.production", "auth.json", "credentials.json"):
        assert CHECKER.inspect_content(name, b"content")
    assert not CHECKER.inspect_content(".env.example", b"VAI_OPENAI_API_KEY=\n")
