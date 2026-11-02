"""Fail if any file about to be committed (or tracked) contains something that looks like
a secret. Used by the local pre-commit hook and by CI.

Usage:
  python scripts/check_secrets.py --staged     # files staged for commit (pre-commit hook)
  python scripts/check_secrets.py --tracked    # every tracked file (CI)
  python scripts/check_secrets.py --dir PATH --public   # any directory about to be published
--public also blocks confidential business material: paths named like the product
strategy, and any line whose fingerprint (SHA-256 of the normalised line) is listed in
~/.config/deliverytwin/private_fingerprints.txt (kept OUTSIDE every repository; it holds
hashes only, never text). Never prints the matched secret, only the file, line and rule.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys

PATTERNS = {
    "openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "env_assignment": re.compile(r"(?i)^\s*(OPENAI|ANTHROPIC|HF|HUGGINGFACE)_[A-Z_]*(KEY|TOKEN)\s*=\s*\S{8,}"),
}
FORBIDDEN_PATHS = re.compile(r"(^|/)\.env($|\.)(?!example)")
CONFIDENTIAL_PATHS = re.compile(r"(?i)(product[_ -]?strategy|(^|/)docs/product/)")
FINGERPRINTS = os.path.expanduser("~/.config/deliverytwin/private_fingerprints.txt")


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*_#>|\-]", " ", line)).strip().lower()


def _fingerprints() -> set[str]:
    if not os.path.exists(FINGERPRINTS):
        return set()
    with open(FINGERPRINTS) as f:
        return {x.strip() for x in f if x.strip()}


def _dir_files(root: str) -> list[str]:
    skip = {".git", "node_modules", ".next", ".venv", ".vercel"}
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in skip]
        out += [os.path.relpath(os.path.join(d, f), root) for f in files]
    return out


def _files(mode: str) -> list[str]:
    # -z: NUL-separated, unquoted paths (non-ASCII names are otherwise quoted and the
    # blob lookup silently fails; Codex review G3).
    if mode == "staged":
        cmd = ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"]
    else:
        cmd = ["git", "ls-files", "-z"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return [f.decode("utf-8", errors="surrogateescape") for f in out.split(b"\0") if f]


class UnreadableFile(RuntimeError):
    pass


def _content(path: str, mode: str) -> str:
    if mode == "staged":
        r = subprocess.run(["git", "show", f":{path}"], check=False, capture_output=True)
        if r.returncode != 0:  # fail closed: an unreadable staged blob is not "clean"
            raise UnreadableFile(path)
        data = r.stdout
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data.decode("utf-8", errors="ignore")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--tracked", action="store_true")
    g.add_argument("--dir", help="scan every file under this directory")
    ap.add_argument("--public", action="store_true",
                    help="also block confidential business material (see module doc)")
    a = ap.parse_args()
    mode = "staged" if a.staged else ("dir" if a.dir else "tracked")
    fps = _fingerprints() if a.public else set()
    if a.public and not fps:
        print("Public check: fingerprint file missing; only path rules apply.", file=sys.stderr)
    problems = []
    paths = _dir_files(a.dir) if a.dir else _files(mode)
    for path in paths:
        if a.public and CONFIDENTIAL_PATHS.search(path):
            problems.append(f"{path}: confidential business document must never be published")
            continue
        if FORBIDDEN_PATHS.search(path):
            problems.append(f"{path}: environment file must never be committed")
            continue
        try:
            content = (_content(os.path.join(a.dir, path), "tracked") if a.dir
                       else _content(path, mode))
        except (UnreadableFile, OSError):
            problems.append(f"{path}: could not read content to scan")
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            for name, pat in PATTERNS.items():
                if pat.search(line):
                    problems.append(f"{path}:{lineno}: looks like a secret ({name})")
            if fps:
                n = _norm(line)
                if len(n) >= 60 and hashlib.sha256(n.encode()).hexdigest()[:24] in fps:
                    problems.append(f"{path}:{lineno}: matches confidential strategy text")
    if problems:
        print("Secret check FAILED:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print(f"Secret check passed ({mode}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
