"""Fail when repository source appears to contain a real credential."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".next",
    ".venv",
    "node_modules",
    "work",
    "outputs",
    "test-results",
    "playwright-report",
    "__pycache__",
}
SKIP_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".pdf", ".pyc", ".db"}
SAFE_MARKERS = ("CHANGE_ME", "TestOnly", "test-only", "example", "<", "${", "")

PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Twilio account SID": re.compile(r"\bAC[a-fA-F0-9]{32}\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|password|token|auth[_-]?token)\b\s*[:=]\s*[\"']?([^\s\"',}]+)"
)


def source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


findings: list[str] = []
for path in source_files():
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    relative = path.relative_to(ROOT)
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{relative}:{line}: {label}")
    if "tests" not in relative.parts:
        for match in ASSIGNMENT.finditer(text):
            value = match.group(1)
            if value and not any(
                marker and marker.lower() in value.lower() for marker in SAFE_MARKERS
            ):
                if len(value) >= 12 and "settings." not in value and "payload." not in value:
                    line = text.count("\n", 0, match.start()) + 1
                    findings.append(f"{relative}:{line}: credential-like assignment")

if findings:
    print("Potential credentials detected:")
    print("\n".join(sorted(set(findings))))
    sys.exit(1)

print("Secret scan passed: no credential signatures detected.")
