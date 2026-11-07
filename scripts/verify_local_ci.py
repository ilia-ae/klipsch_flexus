#!/usr/bin/env python3
"""Verify signed local CI evidence for one commit.

This is the remote verifier GitHub Actions runs, and the same code path
``scripts/local_ci.py verify`` uses on the owner's Mac. Standard library only.

It never imports, executes or checks out anything from the tested commit: the
commit, its tree and its ``.ci/local-ci.json`` are read as git objects (data).
Trust comes only from the allowed signers handed to it (the repository
variable ``LOCAL_CI_ALLOWED_SIGNERS`` on GitHub), never from the repository.

A commit passes when all of this holds:

1. the commit is signed by an allowed signer for ``code@ilia.ae``
   (``git verify-commit``), unless ``--allow-external`` accepts evidence the
   owner made for a pull request head someone else wrote;
2. ``refs/notes/local-ci`` holds a note for the commit: one line of canonical
   JSON evidence followed by exactly one SSH signature;
3. the signature verifies with ``ssh-keygen -Y verify -I code@ilia.ae`` in the
   dedicated namespace ``klipsch-flexus-local-ci@ilia.ae`` (so a git commit or
   tag signature, namespace ``git``, can never be replayed as evidence);
4. the evidence names this repository, this commit and its tree, the policy
   blob at this commit, and every step that policy requires, in order, with
   the same command, passed with exit code 0; a step's optional ``summary``
   is a short plain string, present only where the policy declares one;
5. with ``--tag``: the tag is annotated, points at the commit and is signed by
   an allowed signer (``git tag -s``).

``--write-badges DIR`` (push to main only) then writes shields.io endpoint
badges, the verified evidence and its signature into DIR, built by
``badge_files`` from the verified note alone.

Usage: python3 -I scripts/verify_local_ci.py --sha <40-hex> [--tag vX.Y.Z]
       [--allow-external] [--fetch origin --wait 180] [--write-badges DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPOSITORY = "ilia-ae/klipsch_flexus"
PRINCIPAL = "code@ilia.ae"
NAMESPACE = "klipsch-flexus-local-ci@ilia.ae"
NOTES_REF = "refs/notes/local-ci"
POLICY_PATH = ".ci/local-ci.json"
SCHEMA = "klipsch-flexus-local-ci/2"
POLICY_SCHEMA = 2
HINT = "run make ci && make ci-publish"

MAX_NOTE_BYTES = 256 * 1024
MAX_POLICY_BYTES = 64 * 1024
SHA_RE = re.compile(r"[0-9a-f]{40}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
STEP_ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
# A step summary (e.g. "183 passed", "fresh, upgrade, minimum") is signed
# evidence that ends up in badges and Markdown: short, plain ASCII, no markup.
MAX_SUMMARY = 120
SUMMARY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,:;/()+%=_-]*")  # length: valid_summary
MAX_SUMMARY_PATTERN = 400
SIGNATURE_RE = re.compile(
    rb"-----BEGIN SSH SIGNATURE-----\n(?:[A-Za-z0-9+/=]{1,76}\n){1,64}-----END SSH SIGNATURE-----\n"
)

COMMIT_TRUST = ("owner", "external")
STEP_STATUSES = ("passed", "failed", "timeout", "error")
EVIDENCE_KEYS = frozenset(
    {
        "schema",
        "repository",
        "commit",
        "tree",
        "policy_sha256",
        "commit_signature",
        "steps",
        "tools",
        "host",
        "created_at",
        "result",
    }
)
STEP_KEYS = frozenset({"id", "command", "status", "exit_code", "duration_ms", "log_sha256", "log_bytes", "summary"})
HOST_KEYS = frozenset({"os", "release", "arch", "python"})
POLICY_STEP_KEYS = frozenset({"id", "command", "timeout", "description", "summary"})
SUMMARY_SPEC_KEYS = frozenset({"pattern", "format"})
SIGNATURE_STATES = {
    "N": "unsigned",
    "U": "signed by a key that is not an allowed signer",
    "B": "carries a bad signature",
    "E": "carries a signature that cannot be checked",
    "X": "carries an expired signature",
    "Y": "is signed by an expired key",
    "R": "is signed by a revoked key",
}


class Rejected(Exception):
    """The evidence or the commit does not meet the policy."""


def ssh_keygen() -> str:
    return shutil.which("ssh-keygen") or "ssh-keygen"


def git(
    repo: str | os.PathLike, *args: str, check: bool = True, data: bytes | None = None
) -> subprocess.CompletedProcess:
    """Run git on ``repo``; signature checks use plain ssh-keygen, never a configured helper."""
    command = ["git", "-C", str(repo), "-c", f"gpg.ssh.program={ssh_keygen()}", "-c", "gpg.program=gpg", *args]
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if check and result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip().splitlines()
        raise Rejected(f"git {args[0]} failed: {detail[-1] if detail else 'exit ' + str(result.returncode)}")
    return result


def git_text(repo: str | os.PathLike, *args: str) -> str:
    return git(repo, *args).stdout.decode().strip()


def canonical(value: object) -> bytes:
    """The one byte encoding evidence is signed in."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise Rejected(f"duplicate key {key!r} in JSON")
        result[key] = value
    return result


def _no_floats(text: str) -> object:
    raise Rejected(f"non-integer number {text!r} in evidence")


def load_canonical(raw: bytes) -> dict:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_no_duplicates,
            parse_float=_no_floats,
            parse_constant=_no_floats,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise Rejected(f"evidence is not valid JSON: {error}") from None
    if not isinstance(value, dict):
        raise Rejected("evidence is not a JSON object")
    if canonical(value) != raw:
        raise Rejected("evidence is not canonical JSON (sorted keys, no whitespace, ASCII)")
    return value


def valid_summary(value: object) -> bool:
    """A summary: short, plain ASCII from a safe charset, single spaces, no padding."""
    return (
        isinstance(value, str)
        and len(value) <= MAX_SUMMARY
        and SUMMARY_RE.fullmatch(value) is not None
        and " ".join(value.split()) == value
    )


def summary_spec(spec: object, step_id: str) -> tuple[re.Pattern, string.Template | None]:
    """Validate a policy step's ``summary``: a regex and an optional $group template."""
    where = f"{POLICY_PATH} step {step_id} summary"
    if not isinstance(spec, dict) or "pattern" not in spec or set(spec) - SUMMARY_SPEC_KEYS:
        raise Rejected(f"{where} must be {{pattern, format?}}")
    pattern, template = spec["pattern"], spec.get("format")
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_SUMMARY_PATTERN:
        raise Rejected(f"{where} has an invalid pattern")
    try:
        compiled = re.compile(pattern, re.MULTILINE)
    except re.error as error:
        raise Rejected(f"{where} pattern does not compile: {error}") from None
    if template is None:
        return compiled, None
    if not isinstance(template, str) or not template or len(template) > MAX_SUMMARY:
        raise Rejected(f"{where} has an invalid format")
    parsed = string.Template(template)
    if not parsed.is_valid() or not set(parsed.get_identifiers()) <= set(compiled.groupindex):
        raise Rejected(f"{where} format must use only $name groups of its pattern")
    return compiled, parsed


def load_policy(raw: bytes) -> dict:
    """Validate the CI policy (data only) and return it."""
    if len(raw) > MAX_POLICY_BYTES:
        raise Rejected(f"{POLICY_PATH} is too large")
    try:
        policy = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, ValueError) as error:
        raise Rejected(f"{POLICY_PATH} is not valid JSON: {error}") from None
    if not isinstance(policy, dict) or policy.get("schema") != POLICY_SCHEMA:
        raise Rejected(f"{POLICY_PATH} has an unknown schema")
    if policy.get("repository") != REPOSITORY:
        raise Rejected(f"{POLICY_PATH} is for another repository")
    steps = policy.get("steps")
    if not isinstance(steps, list) or not steps:
        raise Rejected(f"{POLICY_PATH} requires no steps")
    seen = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) - POLICY_STEP_KEYS:
            raise Rejected(f"{POLICY_PATH} has a malformed step")
        step_id, command = step.get("id"), step.get("command")
        if not isinstance(step_id, str) or not STEP_ID_RE.fullmatch(step_id) or step_id in seen:
            raise Rejected(f"{POLICY_PATH} has an invalid or duplicate step id {step_id!r}")
        if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command):
            raise Rejected(f"{POLICY_PATH} step {step_id} has no command")
        timeout = step.get("timeout", 1800)
        if type(timeout) is not int or timeout <= 0:
            raise Rejected(f"{POLICY_PATH} step {step_id} has an invalid timeout")
        if "summary" in step:
            summary_spec(step["summary"], step_id)
        seen.add(step_id)
    tools = policy.get("tools", {})
    if not isinstance(tools, dict) or not all(
        isinstance(cmd, list) and cmd and all(isinstance(a, str) for a in cmd) for cmd in tools.values()
    ):
        raise Rejected(f"{POLICY_PATH} has malformed tools")
    return policy


def normalize_allowed_signers(text: str) -> str:
    """The allowed signers without blank lines and comments; Rejected when empty."""
    text = text.replace("\r\n", "\n").strip()
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise Rejected("no allowed signers configured (repository variable LOCAL_CI_ALLOWED_SIGNERS is empty)")
    return "\n".join(lines) + "\n"


def write_allowed_signers(text: str, folder: str) -> str:
    """Write the trusted allowed signers to a private temp file."""
    content = normalize_allowed_signers(text)
    path = os.path.join(folder, "allowed_signers")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def verify_commit_signature(repo: str | os.PathLike, sha: str, allowed: str) -> None:
    config = f"gpg.ssh.allowedSignersFile={allowed}"
    state = git(repo, "-c", config, "log", "-1", "--format=%G?%x00%GS", sha).stdout.decode().strip()
    status, _, signer = state.partition("\0")
    if status != "G":
        reason = SIGNATURE_STATES.get(status, f"has signature state {status!r}")
        raise Rejected(f"commit {sha} {reason}; commits must be signed with git commit -S by {PRINCIPAL}")
    if signer != PRINCIPAL:
        raise Rejected(f"commit {sha} is signed by {signer!r}, not {PRINCIPAL}")
    if git(repo, "-c", config, "verify-commit", sha, check=False).returncode != 0:
        raise Rejected(f"git verify-commit rejected {sha}")


def verify_tag(repo: str | os.PathLike, tag: str, sha: str, allowed: str) -> None:
    if not TAG_RE.fullmatch(tag):
        raise Rejected(f"invalid tag name {tag!r}")
    ref = f"refs/tags/{tag}"
    kind = git(repo, "cat-file", "-t", ref, check=False)
    if kind.returncode != 0:
        raise Rejected(f"tag {tag} not found")
    if kind.stdout.decode().strip() != "tag":
        raise Rejected(f"tag {tag} is not an annotated tag; releases must be created with git tag -s")
    target = git_text(repo, "rev-parse", f"{ref}^{{commit}}")
    if target != sha:
        raise Rejected(f"tag {tag} points at {target}, not {sha}")
    result = git(repo, "-c", f"gpg.ssh.allowedSignersFile={allowed}", "verify-tag", "--raw", ref, check=False)
    output = result.stderr.decode(errors="replace")
    if result.returncode != 0 or f'Good "git" signature for {PRINCIPAL} with' not in output:
        raise Rejected(f"tag {tag} is not signed by an allowed signer for {PRINCIPAL}; use git tag -s")


def read_note(repo: str | os.PathLike, sha: str) -> bytes | None:
    listed = git(repo, "notes", "--ref", NOTES_REF, "list", sha, check=False)
    if listed.returncode != 0:
        return None
    blob = listed.stdout.decode().strip()
    if not SHA_RE.fullmatch(blob):
        raise Rejected(f"unexpected note object for {sha}")
    if int(git_text(repo, "cat-file", "-s", blob)) > MAX_NOTE_BYTES:
        raise Rejected(f"local CI note for {sha} is too large")
    return git(repo, "cat-file", "blob", blob).stdout


def parse_note(note: bytes) -> tuple[bytes, bytes, dict]:
    """Split a note into (evidence bytes, armored signature, evidence)."""
    if len(note) > MAX_NOTE_BYTES:
        raise Rejected("local CI note is too large")
    evidence, newline, signature = note.partition(b"\n")
    if not newline or not evidence:
        raise Rejected("local CI note is malformed")
    if not SIGNATURE_RE.fullmatch(signature):
        raise Rejected("local CI note must be one JSON line followed by exactly one SSH signature and nothing else")
    return evidence, signature, load_canonical(evidence)


def verify_signature(evidence: bytes, signature: bytes, allowed: str) -> None:
    with tempfile.TemporaryDirectory(prefix="klipsch-flexus-sig-") as folder:
        path = os.path.join(folder, "evidence.sig")
        with open(path, "wb") as handle:
            handle.write(signature)
        result = subprocess.run(
            [ssh_keygen(), "-Y", "verify", "-f", allowed, "-I", PRINCIPAL, "-n", NAMESPACE, "-s", path],
            input=evidence,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        raise Rejected(f"evidence signature is not a valid {NAMESPACE} signature by an allowed key for {PRINCIPAL}")


def _require_str(value: object, what: str, limit: int = 500) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise Rejected(f"evidence field {what} is malformed")
    return value


def _require_int(value: object, what: str) -> int:
    if type(value) is not int or value < 0:
        raise Rejected(f"evidence field {what} is malformed")
    return value


def validate_evidence(evidence: dict, sha: str, tree: str, policy_raw: bytes, *, allow_external: bool = False) -> None:
    """Check signed evidence against the commit and the policy at that commit."""
    keys = set(evidence)
    if keys != EVIDENCE_KEYS:
        extra, missing = sorted(keys - EVIDENCE_KEYS), sorted(EVIDENCE_KEYS - keys)
        raise Rejected(f"evidence has unexpected fields {extra} / lacks fields {missing}")
    if evidence["schema"] != SCHEMA:
        raise Rejected(f"evidence schema {evidence['schema']!r} is not {SCHEMA}")
    if evidence["repository"] != REPOSITORY:
        raise Rejected(f"evidence is for repository {evidence['repository']!r}")
    if evidence["commit"] != sha:
        raise Rejected(f"stale evidence: it was made for commit {evidence['commit']!r}, not {sha}")
    if evidence["tree"] != tree:
        raise Rejected(f"stale evidence: it was made for tree {evidence['tree']!r}, not {tree}")
    if evidence["policy_sha256"] != hashlib.sha256(policy_raw).hexdigest():
        raise Rejected(f"evidence was made under a different {POLICY_PATH}")
    if evidence["commit_signature"] not in COMMIT_TRUST:
        raise Rejected("evidence field commit_signature is malformed")
    if evidence["commit_signature"] == "external" and not allow_external:
        raise Rejected("evidence attests an external (pull request) commit; it is not accepted for main or tags")

    created = _require_str(evidence["created_at"], "created_at")
    if not TIMESTAMP_RE.fullmatch(created):
        raise Rejected("evidence field created_at is malformed")
    try:
        created_at = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        raise Rejected("evidence field created_at is malformed") from None
    if created_at > datetime.now(UTC) + timedelta(minutes=10):
        raise Rejected("evidence is dated in the future")

    host = evidence["host"]
    if not isinstance(host, dict) or set(host) != HOST_KEYS:
        raise Rejected("evidence field host is malformed")
    for key, value in host.items():
        _require_str(value, f"host.{key}", 200)
    tools = evidence["tools"]
    if not isinstance(tools, dict) or len(tools) > 64:
        raise Rejected("evidence field tools is malformed")
    for key, value in tools.items():
        _require_str(key, "tools key", 64)
        _require_str(value, f"tools.{key}")

    policy = load_policy(policy_raw)
    required = [(step["id"], step["command"]) for step in policy["steps"]]
    summarized = {step["id"] for step in policy["steps"] if "summary" in step}
    steps = evidence["steps"]
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise Rejected("evidence field steps is malformed")
    ids = [step.get("id") for step in steps]
    missing = [step_id for step_id, _ in required if step_id not in ids]
    if missing:
        raise Rejected(f"evidence lacks required step(s): {', '.join(missing)}")
    if ids != [step_id for step_id, _ in required]:
        raise Rejected("evidence steps do not match the policy (extra, duplicate or reordered steps)")
    for step, (step_id, command) in zip(steps, required, strict=True):
        if set(step) != STEP_KEYS:
            raise Rejected(f"evidence step {step_id} has unexpected or missing fields")
        if step["command"] != command:
            raise Rejected(f"evidence step {step_id} ran {step['command']!r}, the policy requires {command!r}")
        status, code = step["status"], step["exit_code"]
        if status not in STEP_STATUSES:
            raise Rejected(f"evidence step {step_id} has an unknown status")
        if code is not None and type(code) is not int:
            raise Rejected(f"evidence step {step_id} has a malformed exit code")
        _require_int(step["duration_ms"], f"{step_id}.duration_ms")
        _require_int(step["log_bytes"], f"{step_id}.log_bytes")
        if not isinstance(step["log_sha256"], str) or not HEX64_RE.fullmatch(step["log_sha256"]):
            raise Rejected(f"evidence step {step_id} has a malformed log digest")
        text = step["summary"]
        if text is not None and (step_id not in summarized or not valid_summary(text)):
            raise Rejected(
                f"evidence step {step_id} has a malformed summary (at most {MAX_SUMMARY} plain characters, "
                "only for steps whose policy declares one)"
            )
        if status != "passed" or code != 0:
            raise Rejected(f"required step {step_id} did not pass ({status}, exit code {code})")
    if evidence["result"] != "passed":
        raise Rejected(f"local CI result is {evidence['result']!r}")


def verify(
    repo: str | os.PathLike,
    sha: str,
    allowed_signers: str,
    *,
    allow_external: bool = False,
    note: bytes | None = None,
    tag: str | None = None,
) -> dict:
    """Verify everything for ``sha``; return the evidence or raise Rejected."""
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise Rejected(f"expected a full 40-character commit SHA, got {sha!r}")
    if git(repo, "cat-file", "-t", sha, check=False).stdout.decode().strip() != "commit":
        raise Rejected(f"commit {sha} is not in this repository (fetch it first)")
    with tempfile.TemporaryDirectory(prefix="klipsch-flexus-verify-") as folder:
        allowed = write_allowed_signers(allowed_signers, folder)
        if not allow_external:
            verify_commit_signature(repo, sha, allowed)
        if tag is not None:
            verify_tag(repo, tag, sha, allowed)
        if note is None:
            note = read_note(repo, sha)
        if note is None:
            raise Rejected(f"no signed local CI evidence for {sha}: {HINT}")
        raw, signature, evidence = parse_note(note)
        verify_signature(raw, signature, allowed)
        if evidence.get("commit_signature") == "owner" and allow_external:
            verify_commit_signature(repo, sha, allowed)
        tree = git_text(repo, "rev-parse", f"{sha}^{{tree}}")
        policy = git(repo, "cat-file", "blob", f"{sha}:{POLICY_PATH}", check=False)
        if policy.returncode != 0:
            raise Rejected(f"commit {sha} has no {POLICY_PATH}")
        validate_evidence(evidence, sha, tree, policy.stdout, allow_external=allow_external)
    return evidence


def fetch(repo: str, remote: str, sha: str, wait: int) -> None:
    """CI only: fetch the commit if needed, then wait for its note to appear."""
    if git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode != 0:
        git(repo, "fetch", "--no-tags", "--quiet", remote, sha)
    deadline = time.monotonic() + wait
    while True:
        git(repo, "fetch", "--no-tags", "--quiet", "--force", remote, f"{NOTES_REF}:{NOTES_REF}", check=False)
        if read_note(repo, sha) is not None:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        print(f"no local CI note for {sha} yet; retrying for {int(remaining)} more seconds", flush=True)
        time.sleep(min(15.0, remaining))


def summary(evidence: dict, sha: str, tag: str | None) -> str:
    lines = [
        f"### Signed local CI verified for `{sha}`" + (f" (tag `{tag}`)" if tag else ""),
        "",
        f"Signed by `{PRINCIPAL}` at {evidence['created_at']} on "
        f"{evidence['host']['os']} {evidence['host']['arch']}; commit signature: {evidence['commit_signature']}.",
        "",
        "| step | status | duration | summary | command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in evidence["steps"]:
        command = " ".join(step["command"]).replace("|", "\\|")
        lines.append(
            f"| {step['id']} | {step['status']} | {step['duration_ms'] / 1000:.1f} s | {step['summary'] or ''} "
            f"| `{command}` |"
        )
    lines += ["", "| tool | version |", "| --- | --- |"]
    lines += [f"| {name} | {value.replace('|', '/')} |" for name, value in sorted(evidence["tools"].items())]
    return "\n".join(lines) + "\n"


# Test-result badges (shields.io endpoint JSON), written to the ci-results
# branch by .github/workflows/local-ci.yaml after a verified push to main.
# (file name, label, evidence step, tools key of the Home Assistant version)
BADGES = (
    ("pytest-latest", "pytest", "pytest-latest", "homeassistant-latest"),
    ("pytest-min", "pytest", "pytest-min", "homeassistant-min"),
    ("hassfest", "hassfest", "hassfest", None),
    ("molecule", "molecule", "molecule", None),
)
BADGE_COLOR = "brightgreen"
HA_VERSION_RE = re.compile(r"(\d{4})\.(\d{1,2})(?:\.\d+)?(?:[a-z0-9.]*)")
CI_RESULTS_README = f"""# ci-results

Written by the workflow "Verify signed local CI" (.github/workflows/local-ci.yaml)
after it verified the owner's signed local CI evidence for a push to main.
Do not edit: every update replaces this branch with one new commit.

- badges/*.json: shields.io endpoint badges, built from the verified evidence.
- evidence/<sha>.json and .sig: the signed evidence (exact bytes) and its SSH
  signature; latest.json is the newest verified commit on main.
- allowed_signers: the trust root the workflow verified with
  (repository variable LOCAL_CI_ALLOWED_SIGNERS).

Check a signature (principal {PRINCIPAL}, namespace {NAMESPACE}):

    ssh-keygen -Y verify -f allowed_signers -I {PRINCIPAL} -n {NAMESPACE} \\
      -s evidence/latest.json.sig < evidence/latest.json

scripts/verify_local_ci.py in {REPOSITORY} also checks that the evidence
matches the commit, its tree and its policy (see docs/TESTING.md).
"""


def _endpoint(label: str, message: str) -> bytes:
    """One shields.io endpoint badge (https://shields.io/badges/endpoint-badge)."""
    badge = {"schemaVersion": 1, "label": label, "message": message, "color": BADGE_COLOR}
    return json.dumps(badge, sort_keys=True, ensure_ascii=True).encode() + b"\n"


def badge_files(note: bytes, allowed_signers: str) -> dict[str, bytes]:
    """Map relative path -> content for the ci-results branch. Pure: no I/O.

    ``note`` must already have passed ``verify`` for an owner-signed commit.
    Every value comes from that evidence: summaries the verifier accepted
    (safe charset, length-capped), the Home Assistant version only when it
    looks like one, the commit SHA and the timestamp, all JSON-encoded here.
    """
    raw, signature, evidence = parse_note(note)
    if evidence.get("commit_signature") != "owner" or evidence.get("result") != "passed":
        raise Rejected("badges are written only for passed evidence of an owner-signed commit")
    sha, created = evidence["commit"], evidence["created_at"]
    if not SHA_RE.fullmatch(sha) or not TIMESTAMP_RE.fullmatch(created):
        raise Rejected("evidence commit or created_at is malformed")
    steps = {step["id"]: step for step in evidence["steps"]}
    files: dict[str, bytes] = {}
    for name, label, step_id, ha_tool in BADGES:
        step = steps.get(step_id)
        if step is None or step["status"] != "passed":
            continue
        summary = step["summary"]
        parts = summary.split(", ") if valid_summary(summary) else ["passed"]
        if ha_tool:
            match = HA_VERSION_RE.fullmatch(str(evidence["tools"].get(ha_tool, "")))
            if match:
                parts.insert(0, f"HA {match.group(1)}.{int(match.group(2))}")
        files[f"badges/{name}.json"] = _endpoint(label, " \u00b7 ".join(parts))
    files["badges/signed.json"] = _endpoint("local CI", f"signed \u00b7 {sha[:7]} \u00b7 {created[:10]}")
    for stem in ("latest", sha):
        files[f"evidence/{stem}.json"] = raw  # the exact signed bytes (no trailing newline)
        files[f"evidence/{stem}.json.sig"] = signature
    files["allowed_signers"] = normalize_allowed_signers(allowed_signers).encode()
    files["README.md"] = CI_RESULTS_README.encode()
    return files


def write_files(directory: str | os.PathLike, files: dict[str, bytes]) -> None:
    root = Path(directory).resolve()
    for relative, content in sorted(files.items()):
        target = (root / relative).resolve()
        if root not in target.parents:
            raise Rejected(f"refusing to write outside {root}: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--sha", required=True, help="full commit SHA to verify")
    parser.add_argument("--repo", default=".", help="git repository holding the commit and notes")
    parser.add_argument("--tag", help="also require this annotated tag, signed, pointing at the commit")
    parser.add_argument("--allow-external", action="store_true", help="accept owner evidence for a non-owner PR head")
    parser.add_argument("--allowed-signers-file", help="default: the LOCAL_CI_ALLOWED_SIGNERS environment variable")
    parser.add_argument("--fetch", metavar="REMOTE", help="fetch the commit and refs/notes/local-ci from REMOTE")
    parser.add_argument("--wait", type=int, default=0, help="seconds to keep re-fetching a missing note")
    parser.add_argument(
        "--write-badges", metavar="DIR", help="after verification, write badges + evidence for the ci-results branch"
    )
    args = parser.parse_args(argv)

    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    try:
        if args.allowed_signers_file:
            allowed = Path(args.allowed_signers_file).read_text(encoding="utf-8")
        else:
            allowed = os.environ.get("LOCAL_CI_ALLOWED_SIGNERS", "")
        if not SHA_RE.fullmatch(args.sha):
            raise Rejected(f"expected a full 40-character commit SHA, got {args.sha!r}")
        if args.write_badges and args.allow_external:
            raise Rejected("--write-badges needs strictly verified (owner-signed) evidence, not --allow-external")
        if args.fetch:
            fetch(args.repo, args.fetch, args.sha, args.wait)
        note = read_note(args.repo, args.sha)
        evidence = verify(args.repo, args.sha, allowed, allow_external=args.allow_external, note=note, tag=args.tag)
        if args.write_badges:
            write_files(args.write_badges, badge_files(note, allowed))
    except (Rejected, OSError) as error:
        print(f"::error::{error}" if in_actions else f"local CI verification FAILED: {error}", file=sys.stderr)
        return 1
    passed = sum(step["status"] == "passed" for step in evidence["steps"])
    print(
        f"local CI verified: {args.sha} tree {evidence['tree']}; {passed}/{len(evidence['steps'])} steps passed; "
        f"evidence signed {evidence['created_at']} ({evidence['commit_signature']} commit)"
    )
    if in_actions and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(summary(evidence, args.sha, args.tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
